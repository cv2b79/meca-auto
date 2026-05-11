#!/bin/bash
# Liste toutes les sauvegardes avec leur taille et date

BACKUP_DIR="/opt/meca-auto/backups"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  MECA AUTO — Sauvegardes disponibles"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! ls "${BACKUP_DIR}"/mecaauto_*.sql.gz 2>/dev/null | head -1 > /dev/null; then
    echo "  Aucune sauvegarde trouvée dans ${BACKUP_DIR}"
    exit 0
fi

echo ""
printf "  %-35s %8s\n" "Fichier" "Taille"
echo "  $(printf '%.0s─' {1..50})"

ls -t "${BACKUP_DIR}"/mecaauto_*.sql.gz 2>/dev/null | while read f; do
    size=$(du -h "$f" | cut -f1)
    name=$(basename "$f" .sql.gz | sed 's/mecaauto_//')
    # Marquer la plus récente
    if [ "$f" = "$(ls -t ${BACKUP_DIR}/mecaauto_*.sql.gz | head -1)" ]; then
        printf "  %-35s %8s  ◀ dernière\n" "$name" "$size"
    else
        printf "  %-35s %8s\n" "$name" "$size"
    fi
done

echo ""
TOTAL=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
NB=$(ls "${BACKUP_DIR}"/mecaauto_*.sql.gz 2>/dev/null | wc -l)
echo "  Total : ${NB} sauvegarde(s) — ${TOTAL} utilisés"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Pour restaurer : ./scripts/restore.sh [fichier.sql.gz]"
echo "  Sans argument  : restaure la dernière sauvegarde"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
