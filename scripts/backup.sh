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
RETENTION_DAYS=30        # Valeur par défaut (surchargée par backup.conf)
MIN_SIZE_KB=2            # Taille minimale acceptable d'un dump (Ko)

# Charger la config NAS générée depuis l'interface d'administration
CONF_FILE="${APP_DIR}/scripts/backup.conf"
BACKUP_NAS_IP=""
BACKUP_NAS_SHARE=""
BACKUP_NAS_USER=""
BACKUP_NAS_PASS=""
BACKUP_NAS_FOLDER="meca-auto"
if [ -f "$CONF_FILE" ]; then
    # shellcheck source=/dev/null
    source "$CONF_FILE"
    # backup.conf peut écraser RETENTION_DAYS
    if [ -n "${RETENTION_DAYS:-}" ]; then : ; fi
fi

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

# SMTP : les réglages de l'interface (backup.conf) priment sur le .env
export SMTP_HOST="${BACKUP_SMTP_HOST:-${SMTP_HOST:-}}"
export SMTP_PORT="${BACKUP_SMTP_PORT:-${SMTP_PORT:-587}}"
export SMTP_USER="${BACKUP_SMTP_USER:-${SMTP_USER:-}}"
export SMTP_PASSWORD="${BACKUP_SMTP_PASSWORD:-${SMTP_PASSWORD:-}}"
export SMTP_FROM="${BACKUP_SMTP_FROM:-${SMTP_FROM:-}}"
export EMAIL_DDFPT="${BACKUP_EMAIL_DDFPT:-${EMAIL_DDFPT:-}}"

# Lancement manuel (bouton de l'interface, via sudo) ou automatique (cron root)
MANUEL="${SUDO_USER:+oui}"

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

# ── Étape 7 : Copie vers le NAS ───────────────────────────────
if [ -n "${BACKUP_NAS_IP:-}" ] && [ -n "${BACKUP_NAS_SHARE:-}" ]; then
    NAS_MOUNT="/mnt/meca-nas-backup"
    log "▶ Copie NAS → //${BACKUP_NAS_IP}/${BACKUP_NAS_SHARE}/${BACKUP_NAS_FOLDER:-meca-auto}"
    mkdir -p "$NAS_MOUNT"

    # Fichier credentials temporaire (évite le mot de passe dans la liste des processus)
    CREDS_TMP=$(mktemp)
    chmod 600 "$CREDS_TMP"
    echo "username=${BACKUP_NAS_USER:-}" >> "$CREDS_TMP"
    echo "password=${BACKUP_NAS_PASS:-}" >> "$CREDS_TMP"

    # Options SMB — vers=3.0,sec=ntlmssp requis pour Synology DSM 7
    MOUNT_OPTS="credentials=${CREDS_TMP},vers=3.0,sec=ntlmssp,uid=$(id -u),gid=$(id -g),iocharset=utf8"

    if mount -t cifs "//${BACKUP_NAS_IP}/${BACKUP_NAS_SHARE}" "$NAS_MOUNT" \
            -o "${MOUNT_OPTS}" 2>/dev/null; then
        NAS_DEST="${NAS_MOUNT}/${BACKUP_NAS_FOLDER:-meca-auto}"
        mkdir -p "$NAS_DEST"
        cp "$BACKUP_FILE" "$NAS_DEST/"
        cp "$ENV_BACKUP"  "$NAS_DEST/" 2>/dev/null || true
        # Rotation sur le NAS aussi
        find "$NAS_DEST" -name "mecaauto_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
        umount "$NAS_MOUNT" 2>/dev/null || true
        rm -f "$CREDS_TMP"
        log "   ✅ Copie NAS réussie → ${NAS_DEST}"
    else
        rm -f "$CREDS_TMP"
        log "   ⚠️  Impossible de monter le NAS (vérifier IP/partage/credentials)"
    fi
else
    log "▶ Copie NAS ignorée (NAS non configuré)"
fi

# ── Étape 8 : Copies chiffrées hors du Pi (USB, Nuage, email) ─
# Une destination en échec est signalée mais ne bloque ni les autres ni la sauvegarde.
DEST_RESUME=""
dest() { DEST_RESUME="${DEST_RESUME}${DEST_RESUME:+, }$1"; }

copie_usb() {
    local dev mnt monte_ici=""
    dev=$(blkid -L MECABACKUP 2>/dev/null || true)
    if [ -z "$dev" ]; then
        log "   ⚠️  Clé USB « MECABACKUP » non branchée"; dest "USB absente"; return
    fi
    mnt=$(findmnt -n -o TARGET "$dev" 2>/dev/null | head -1 || true)
    if [ -z "$mnt" ]; then
        mnt="/mnt/meca-usb"; mkdir -p "$mnt"
        if ! mount "$dev" "$mnt" 2>/dev/null; then
            log "   ⚠️  Impossible de monter la clé USB ($dev)"; dest "USB erreur"; return
        fi
        monte_ici="oui"
    fi
    if mkdir -p "$mnt/MECA-AUTO" && cp "$CRYPT_FILE" "$mnt/MECA-AUTO/"; then
        find "$mnt/MECA-AUTO" -name "mecaauto_*.7z" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
        sync
        log "   ✅ Copie clé USB → $dev (MECA-AUTO/$(basename "$CRYPT_FILE"))"; dest "USB ok"
    else
        log "   ⚠️  Copie sur la clé USB échouée (clé pleine ou en lecture seule ?)"; dest "USB erreur"
    fi
    [ -n "$monte_ici" ] && umount "$mnt" 2>/dev/null || true
}

copie_nuage() {
    if [ -z "${BACKUP_NUAGE_URL:-}" ] || [ -z "${BACKUP_NUAGE_USER:-}" ] || [ -z "${BACKUP_NUAGE_PASS:-}" ]; then
        log "   ⚠️  Nuage : adresse, identifiant ou mot de passe manquant"; dest "Nuage non configuré"; return
    fi
    local cfg dossier jours nom code base
    # Identifiants dans un fichier temporaire : jamais visibles dans la liste des processus
    cfg=$(mktemp); chmod 600 "$cfg"
    local u="${BACKUP_NUAGE_USER}:${BACKUP_NUAGE_PASS}"
    u=${u//\\/\\\\}; u=${u//\"/\\\"}
    printf 'user = "%s"\n' "$u" > "$cfg"
    dossier="${BACKUP_NUAGE_DOSSIER:-MecaAuto}"; dossier="${dossier// /%20}"
    base="${BACKUP_NUAGE_URL}/${dossier}"
    curl -s -o /dev/null --max-time 60 -K "$cfg" -X MKCOL "${base}/" || true
    # Rotation sans suppression : une copie par jour de semaine + une par mois
    jours=(lundi mardi mercredi jeudi vendredi samedi dimanche)
    nom="mecaauto_${jours[$(( $(date +%u) - 1 ))]}.7z"
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 900 -K "$cfg" -T "$CRYPT_FILE" "${base}/${nom}") || true
    code="${code:-000}"
    if [ "$code" = "201" ] || [ "$code" = "204" ]; then
        log "   ✅ Copie Nuage → ${BACKUP_NUAGE_DOSSIER:-MecaAuto}/${nom}"; dest "Nuage ok"
        if [ "$(date +%d)" = "01" ]; then
            curl -s -o /dev/null --max-time 900 -K "$cfg" -T "$CRYPT_FILE" "${base}/mecaauto_mois_$(date +%Y-%m).7z" \
                && log "   ✅ Copie mensuelle Nuage → mecaauto_mois_$(date +%Y-%m).7z" || true
        fi
    elif [ "$code" = "401" ]; then
        log "   ⚠️  Nuage : identifiant ou mot de passe d'application refusé (HTTP 401)"; dest "Nuage erreur"
    elif [ "$code" = "000" ]; then
        log "   ⚠️  Nuage injoignable (pas d'Internet ?)"; dest "Nuage injoignable"
    else
        log "   ⚠️  Nuage : envoi refusé (HTTP ${code}) — vérifier l'adresse WebDAV"; dest "Nuage erreur"
    fi
    rm -f "$cfg"
}

copie_mail() {
    if [ "${BACKUP_MAIL_FREQ:-hebdo}" != "quotidien" ] && [ "$(date +%u)" != "1" ] && [ -z "$MANUEL" ]; then
        log "   ✉️  Email : envoi prévu le lundi"; return
    fi
    local dest_mail="${BACKUP_MAIL_DEST:-${EMAIL_DDFPT:-}}" taille
    if [ -z "${SMTP_HOST:-}" ] || [ -z "$dest_mail" ]; then
        log "   ⚠️  Email : serveur SMTP ou destinataire non configuré"; dest "email non configuré"; return
    fi
    taille=$(stat -c %s "$CRYPT_FILE")
    if [ "$taille" -gt 20971520 ]; then
        log "   ⚠️  Email : archive trop grosse ($((taille / 1048576)) Mo > 20 Mo), non envoyée"; dest "email trop gros"; return
    fi
    if BACKUP_MAIL_TO="$dest_mail" python3 "${APP_DIR}/scripts/notify_backup.py" "ARCHIVE" \
            "Copie chiffrée de la sauvegarde du $(date '+%d/%m/%Y'). Ouvrir avec 7-Zip et le mot de passe de chiffrement." \
            "$CRYPT_FILE"; then
        log "   ✅ Email envoyé à ${dest_mail}"; dest "email ok"
    else
        log "   ⚠️  Envoi de l'email échoué (voir réglages de l'onglet Email)"; dest "email erreur"
    fi
}

if [ "${BACKUP_USB_ACTIF:-non}" = "oui" ] || [ "${BACKUP_NUAGE_ACTIF:-non}" = "oui" ] || [ "${BACKUP_MAIL_ACTIF:-non}" = "oui" ]; then
    log "▶ Copies chiffrées hors du Pi..."
    if [ -z "${BACKUP_CRYPT_PASS:-}" ]; then
        log "   ⚠️  Mot de passe de chiffrement non défini : aucune copie envoyée"; dest "copies non chiffrables"
    elif ! command -v 7z >/dev/null 2>&1; then
        log "   ⚠️  7z absent : installer avec « sudo apt install p7zip-full »"; dest "7z absent"
    else
        CRYPT_FILE="${BACKUP_DIR}/mecaauto_${DATE}.7z"
        # -mhe=on : même les noms des fichiers sont chiffrés
        if 7z a -t7z -mhe=on -p"${BACKUP_CRYPT_PASS}" "$CRYPT_FILE" "$BACKUP_FILE" "$ENV_BACKUP" >/dev/null 2>&1 \
                && 7z t -p"${BACKUP_CRYPT_PASS}" "$CRYPT_FILE" >/dev/null 2>&1; then
            log "   🔐 Archive chiffrée : $(basename "$CRYPT_FILE") ($(du -k "$CRYPT_FILE" | cut -f1) Ko)"
            [ "${BACKUP_USB_ACTIF:-non}" = "oui" ]   && copie_usb
            [ "${BACKUP_NUAGE_ACTIF:-non}" = "oui" ] && copie_nuage
            [ "${BACKUP_MAIL_ACTIF:-non}" = "oui" ]  && copie_mail
        else
            log "   ⚠️  Création de l'archive chiffrée échouée"; dest "chiffrement erreur"
        fi
        rm -f "$CRYPT_FILE"   # les copies en clair restent dans ${BACKUP_DIR} (et le NAS)
    fi
fi

# ── Étape 9 : Rotation des anciennes sauvegardes locales ──────
log "▶ Rotation locale : suppression des sauvegardes > ${RETENTION_DAYS} jours..."
DELETED=$(find "$BACKUP_DIR" -name "mecaauto_*.sql.gz" -mtime "+${RETENTION_DAYS}" -print -delete | wc -l)
find "$BACKUP_DIR" -name "env_*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
log "   ${DELETED} ancienne(s) sauvegarde(s) supprimée(s)"

# ── Étape 10 : Résumé ─────────────────────────────────────────
NB_BACKUPS=$(ls "${BACKUP_DIR}"/mecaauto_*.sql.gz 2>/dev/null | wc -l)
OLDEST=$(ls -t "${BACKUP_DIR}"/mecaauto_*.sql.gz 2>/dev/null | tail -1 | xargs -I{} basename {} .sql.gz | sed 's/mecaauto_//')
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

notify_success "Sauvegarde réussie — ${SIZE_KB} Ko, ${TABLE_COUNT} tables, ${NB_BACKUPS} backup(s) conservé(s) (plus ancien: ${OLDEST:-?}), espace total: ${TOTAL_SIZE}${DEST_RESUME:+ — copies : ${DEST_RESUME}}"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
