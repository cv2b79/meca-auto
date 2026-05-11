#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║         MECA AUTO — Script de sauvegarde automatique        ║
# ║  Sauvegarde PostgreSQL + vérification + rotation + log      ║
# ║  Usage : ./scripts/backup.sh                                ║
# ║  Cron   : 0 2 * * * /opt/meca-auto/scripts/backup.sh       ║
# ╚══════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────
APP_DIR="/opt/meca-auto"
BACKUP_DIR="/opt/meca-auto/backups"
LOG_FILE="/opt/meca-auto/backups/backup.log"
RETENTION_DAYS=30        # Garder les sauvegardes des 30 derniers jours
MIN_SIZE_KB=10           # Taille minimale acceptable d'un dump (Ko)
DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="${BACKUP_DIR}/mecaauto_${DATE}.sql.gz"
ENV_BACKUP="${BACKUP_DIR}/env_${DATE}.tar.gz"

# ── Charger les variables d'environnement ─────────────────────
if [ -f "${APP_DIR}/.env" ]; then
    while IFS='=' read -r key value; do
        # Ignorer les commentaires et lignes vides
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue
        # Exporter seulement les noms de variables valides (lettres, chiffres, _)
        [[ "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] || continue
        export "$key=$value"
    done < "${APP_DIR}/.env"
fi

# Extraire les paramètres PostgreSQL depuis DATABASE_URL
# Format : postgresql://user:password@host:port/dbname
if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERREUR: DATABASE_URL non définie dans .env" | tee -a "$LOG_FILE"
    exit 1
fi

DB_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:/]*\).*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

# ── Fonctions ──────────────────────────────────────────────────
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

notify_error() {
    local msg="$1"
    log "❌ ERREUR : $msg"
    # Notification par email si SMTP configuré
    if [ -n "${SMTP_HOST:-}" ] && [ -n "${SMTP_USER:-}" ]; then
        python3 "${APP_DIR}/scripts/notify_backup.py" "ECHEC" "$msg" 2>/dev/null || true
    fi
    exit 1
}

notify_success() {
    local msg="$1"
    log "✅ $msg"
    if [ -n "${SMTP_HOST:-}" ] && [ -n "${SMTP_USER:-}" ]; then
        python3 "${APP_DIR}/scripts/notify_backup.py" "OK" "$msg" 2>/dev/null || true
    fi
}

# ── Préparation ────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "🚀 Début de la sauvegarde"

# ── Étape 1 : Dump PostgreSQL ──────────────────────────────────
log "▶ Dump PostgreSQL → ${BACKUP_FILE}"
PGPASSWORD="$DB_PASS" pg_dump \
    -h "$DB_HOST" \
    -p "${DB_PORT:-5432}" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-password \
    --format=plain \
    --clean \
    --if-exists \
    | gzip > "$BACKUP_FILE" \
    || notify_error "pg_dump a échoué (code: $?)"

# ── Étape 2 : Vérification taille ─────────────────────────────
SIZE_KB=$(du -k "$BACKUP_FILE" | cut -f1)
log "▶ Taille du dump : ${SIZE_KB} Ko"

if [ "$SIZE_KB" -lt "$MIN_SIZE_KB" ]; then
    notify_error "Dump trop petit (${SIZE_KB} Ko < ${MIN_SIZE_KB} Ko minimum) — suspect"
fi

# ── Étape 3 : Vérification intégrité gzip ─────────────────────
log "▶ Vérification intégrité gzip..."
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    notify_error "Fichier gzip corrompu : ${BACKUP_FILE}"
fi

# ── Étape 4 : Vérification contenu SQL ────────────────────────
log "▶ Vérification contenu SQL..."
TABLE_COUNT=$(zcat "$BACKUP_FILE" | grep -c "^CREATE TABLE" || true)
log "   Tables trouvées dans le dump : ${TABLE_COUNT}"

if [ "$TABLE_COUNT" -lt 5 ]; then
    notify_error "Dump suspect : seulement ${TABLE_COUNT} table(s) trouvée(s)"
fi

# ── Étape 5 : Sauvegarde du .env ──────────────────────────────
log "▶ Sauvegarde de la configuration (.env)..."
tar -czf "$ENV_BACKUP" -C "$APP_DIR" .env 2>/dev/null || log "   ⚠️  Impossible de sauvegarder .env"

# ── Étape 6 : Comparaison avec la veille ──────────────────────
PREV_BACKUP=$(ls -t "${BACKUP_DIR}"/mecaauto_*.sql.gz 2>/dev/null | sed -n '2p')
if [ -n "$PREV_BACKUP" ]; then
    PREV_SIZE=$(du -k "$PREV_BACKUP" | cut -f1)
    if [ "$PREV_SIZE" -gt 0 ]; then
        RATIO=$(echo "scale=2; $SIZE_KB * 100 / $PREV_SIZE" | bc)
        log "▶ Comparaison avec la veille : aujourd'hui ${SIZE_KB} Ko / hier ${PREV_SIZE} Ko (${RATIO}%)"
        # Alerte si le dump est 50% plus petit que la veille
        if (( $(echo "$RATIO < 50" | bc -l) )); then
            log "   ⚠️  ATTENTION : dump nettement plus petit que la veille (${RATIO}%)"
        fi
    fi
fi

# ── Étape 7 : Rotation des anciennes sauvegardes ──────────────
log "▶ Rotation : suppression des sauvegardes > ${RETENTION_DAYS} jours..."
DELETED=$(find "$BACKUP_DIR" -name "mecaauto_*.sql.gz" -mtime "+${RETENTION_DAYS}" -print -delete | wc -l)
find "$BACKUP_DIR" -name "env_*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
log "   ${DELETED} ancienne(s) sauvegarde(s) supprimée(s)"

# ── Étape 8 : Résumé ──────────────────────────────────────────
NB_BACKUPS=$(ls "${BACKUP_DIR}"/mecaauto_*.sql.gz 2>/dev/null | wc -l)
OLDEST=$(ls -t "${BACKUP_DIR}"/mecaauto_*.sql.gz 2>/dev/null | tail -1 | xargs -I{} basename {} .sql.gz | sed 's/mecaauto_//')
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

notify_success "Sauvegarde réussie — ${SIZE_KB} Ko, ${TABLE_COUNT} tables, ${NB_BACKUPS} backup(s) conservé(s) (plus ancien: ${OLDEST:-?}), espace total: ${TOTAL_SIZE}"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
