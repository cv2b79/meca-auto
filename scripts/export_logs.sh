#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║  MECA AUTO — Export hebdomadaire des logs               ║
# ║  Cron : 0 3 * * 1 (lundi 3h du matin)                  ║
# ╚══════════════════════════════════════════════════════════╝

set -euo pipefail

APP_DIR="/opt/meca-auto"
BACKUP_DIR="${APP_DIR}/backups"
LOG_FILE="${BACKUP_DIR}/export_logs.log"
DATE=$(date +%Y-%m-%d)
EXPORT_FILE="${BACKUP_DIR}/logs_${DATE}.csv"

source "${APP_DIR}/scripts/backup.conf" 2>/dev/null || true

log()  { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"; }
ok()   { echo "[$(date '+%H:%M:%S')] ✓ $1" | tee -a "$LOG_FILE"; }
err()  { echo "[$(date '+%H:%M:%S')] ✗ $1" | tee -a "$LOG_FILE"; }

echo "" >> "$LOG_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$LOG_FILE"
log "Export logs MECA AUTO — ${DATE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$LOG_FILE"

# ── 1. Export CSV de la table logs ────────────────────────
log "Export table logs → ${EXPORT_FILE}"
sudo -u postgres psql -d "${DB_NAME:-mecaauto}" -c \
    "COPY (
        SELECT
            l.id,
            to_char(l.created_at, 'DD/MM/YYYY HH24:MI:SS') AS date_heure,
            u.login AS utilisateur,
            u.nom || ' ' || u.prenom AS nom_complet,
            u.role,
            l.action,
            l.details,
            l.target_type,
            l.target_id
        FROM logs l
        LEFT JOIN users u ON u.id = l.user_id
        ORDER BY l.created_at DESC
    ) TO STDOUT WITH CSV HEADER DELIMITER ';' ENCODING 'UTF8'" \
    > "${EXPORT_FILE}" 2>>"$LOG_FILE"

LINES=$(wc -l < "${EXPORT_FILE}")
ok "Export OK — ${LINES} entrées"

# ── 2. Infos système ──────────────────────────────────────
SYSINFO_FILE="${BACKUP_DIR}/sysinfo_${DATE}.txt"
log "Export infos système → ${SYSINFO_FILE}"
{
    echo "=== MECA AUTO — Rapport système — ${DATE} ==="
    echo ""
    echo "--- Système ---"
    uname -a
    echo ""
    echo "--- Espace disque ---"
    df -h /
    echo ""
    echo "--- Mémoire ---"
    free -h
    echo ""
    echo "--- Service mecaauto ---"
    systemctl status mecaauto --no-pager 2>/dev/null || echo "Service non trouvé"
    echo ""
    echo "--- Dernières lignes log service (50) ---"
    journalctl -u mecaauto -n 50 --no-pager 2>/dev/null || true
    echo ""
    echo "--- Version Python/Flask ---"
    /opt/meca-auto/venv/bin/python --version 2>&1 || true
    /opt/meca-auto/venv/bin/pip show flask 2>/dev/null | grep Version || true
    echo ""
    echo "--- Taille base de données ---"
    sudo -u postgres psql -c "SELECT pg_size_pretty(pg_database_size('${DB_NAME:-mecaauto}')) AS taille;" 2>/dev/null || true
    echo ""
    echo "--- Nombre d'enregistrements clés ---"
    sudo -u postgres psql -d "${DB_NAME:-mecaauto}" -c \
        "SELECT 'OR' AS table_, COUNT(*) FROM ordres_reparation
         UNION ALL SELECT 'Clients', COUNT(*) FROM clients
         UNION ALL SELECT 'Factures', COUNT(*) FROM factures
         UNION ALL SELECT 'Logs', COUNT(*) FROM logs
         UNION ALL SELECT 'Incidents', COUNT(*) FROM incidents;" 2>/dev/null || true
} > "${SYSINFO_FILE}" 2>&1
ok "Infos système OK"

# ── 3. Copie sur NAS ──────────────────────────────────────
NAS_OK=false
if [ -n "${NAS_IP:-}" ] && [ -n "${NAS_SHARE:-}" ]; then
    log "Copie sur NAS ${NAS_IP}/${NAS_SHARE}/${NAS_DIR:-}..."
    CRED_FILE=$(mktemp)
    chmod 600 "$CRED_FILE"
    echo "username=${NAS_USER:-}" > "$CRED_FILE"
    echo "password=${NAS_PASS:-}" >> "$CRED_FILE"
    MOUNT_POINT=$(mktemp -d)

    if mount -t cifs "//${NAS_IP}/${NAS_SHARE}" "$MOUNT_POINT" \
        -o credentials="$CRED_FILE",vers=3.0,sec=ntlmssp,iocharset=utf8 2>>"$LOG_FILE"; then
        NAS_DEST="${MOUNT_POINT}/${NAS_DIR:-mecapro}/logs"
        mkdir -p "$NAS_DEST" 2>/dev/null || true
        cp "${EXPORT_FILE}" "$NAS_DEST/" 2>>"$LOG_FILE" && \
        cp "${SYSINFO_FILE}" "$NAS_DEST/" 2>>"$LOG_FILE" && \
        NAS_OK=true
        umount "$MOUNT_POINT" 2>/dev/null || true
        ok "Copie NAS OK → ${NAS_DEST}"
    else
        err "Montage NAS échoué"
    fi
    rm -f "$CRED_FILE"
    rmdir "$MOUNT_POINT" 2>/dev/null || true
else
    log "NAS non configuré — copie locale uniquement"
fi

# ── 4. Envoi email (optionnel) ────────────────────────────
if [ -n "${SMTP_HOST:-}" ] && [ -n "${NOTIF_INCIDENT_EMAIL:-}" ]; then
    log "Envoi email récapitulatif..."
    SUBJECT="[MECA AUTO] Export logs hebdo — ${DATE}"
    BODY="Bonjour,\n\nVeuillez trouver ci-joint l'export hebdomadaire des logs MECA AUTO du ${DATE}.\n\nFichier : ${EXPORT_FILE}\n"
    if [ "$NAS_OK" = true ]; then
        BODY="${BODY}Copie NAS : OK\n"
    else
        BODY="${BODY}Copie NAS : NON effectuée\n"
    fi
    BODY="${BODY}\nCordialement,\nMECA AUTO"

    python3 "${APP_DIR}/scripts/notify_backup.py" \
        --subject "$SUBJECT" \
        --body "$BODY" \
        --to "${NOTIF_INCIDENT_EMAIL}" 2>>"$LOG_FILE" || err "Envoi email échoué"
fi

# ── 5. Rotation — garder 12 semaines ─────────────────────
find "${BACKUP_DIR}" -name "logs_*.csv"   -mtime +84 -delete 2>/dev/null || true
find "${BACKUP_DIR}" -name "sysinfo_*.txt" -mtime +84 -delete 2>/dev/null || true
ok "Rotation OK (12 semaines)"

ok "Export terminé"
