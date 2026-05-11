#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║         MECA AUTO — Script de restauration                  ║
# ║  Usage : ./scripts/restore.sh [fichier.sql.gz]              ║
# ║          Sans argument = utilise la dernière sauvegarde      ║
# ╚══════════════════════════════════════════════════════════════╝

set -euo pipefail

APP_DIR="/opt/meca-auto"
BACKUP_DIR="/opt/meca-auto/backups"

# Charger les variables d'environnement
if [ -f "${APP_DIR}/.env" ]; then
    export $(grep -v '^#' "${APP_DIR}/.env" | grep '=' | xargs)
fi

DB_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:/]*\).*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

# Choisir le fichier à restaurer
if [ -n "${1:-}" ]; then
    BACKUP_FILE="$1"
else
    BACKUP_FILE=$(ls -t "${BACKUP_DIR}"/mecaauto_*.sql.gz 2>/dev/null | head -1)
    if [ -z "$BACKUP_FILE" ]; then
        echo "❌ Aucune sauvegarde trouvée dans ${BACKUP_DIR}"
        exit 1
    fi
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Fichier introuvable : $BACKUP_FILE"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  RESTAURATION DE LA BASE DE DONNÉES"
echo "   Fichier : $(basename $BACKUP_FILE)"
echo "   Base    : $DB_NAME @ $DB_HOST"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  ATTENTION : cette opération va ÉCRASER la base actuelle !"
read -p "Confirmer la restauration ? (oui/non) : " CONFIRM

if [ "$CONFIRM" != "oui" ]; then
    echo "Annulé."
    exit 0
fi

# Vérifier l'intégrité avant restauration
echo "▶ Vérification intégrité du fichier..."
gzip -t "$BACKUP_FILE" || { echo "❌ Fichier corrompu !"; exit 1; }

# Arrêter l'appli pendant la restauration
echo "▶ Arrêt de l'application..."
sudo systemctl stop mecaauto 2>/dev/null || true

# Restaurer
echo "▶ Restauration en cours..."
PGPASSWORD="$DB_PASS" zcat "$BACKUP_FILE" | psql \
    -h "$DB_HOST" \
    -p "${DB_PORT:-5432}" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-password \
    -q

echo "▶ Redémarrage de l'application..."
sudo systemctl start mecaauto 2>/dev/null || true

echo ""
echo "✅ Restauration terminée depuis : $(basename $BACKUP_FILE)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
