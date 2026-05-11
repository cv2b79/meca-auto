#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║         MECA AUTO — Watchdog / Health Check                 ║
# ║  Vérifie que l'app répond, redémarre si nécessaire          ║
# ║  Lancé toutes les 5 min par mecaauto-watchdog.timer         ║
# ╚══════════════════════════════════════════════════════════════╝

LOG_FILE="/opt/meca-auto/backups/watchdog.log"
URL="http://localhost:5000/"
MAX_TIME=10
DATE=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$(dirname "$LOG_FILE")"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" --max-time "$MAX_TIME" 2>/dev/null)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    echo "[$DATE] ✅ OK (HTTP $HTTP_CODE)" >> "$LOG_FILE"
else
    echo "[$DATE] ⚠️  App ne répond pas (HTTP ${HTTP_CODE:-timeout}) — redémarrage en cours..." >> "$LOG_FILE"
    systemctl restart mecaauto
    sleep 5
    HTTP_CODE2=$(curl -s -o /dev/null -w "%{http_code}" "$URL" --max-time "$MAX_TIME" 2>/dev/null)
    if [ "$HTTP_CODE2" = "200" ] || [ "$HTTP_CODE2" = "302" ]; then
        echo "[$DATE] ✅ Redémarrage réussi (HTTP $HTTP_CODE2)" >> "$LOG_FILE"
    else
        echo "[$DATE] ❌ Redémarrage échoué — intervention manuelle requise" >> "$LOG_FILE"
    fi
fi

# Garder les 500 dernières lignes du log watchdog
tail -500 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
