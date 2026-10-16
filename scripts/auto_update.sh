#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║         MECA AUTO — Mise à jour automatique depuis GitHub    ║
# ║  Récupère les nouveaux commits, redémarre l'app, et revient  ║
# ║  à la version précédente si l'app ne répond plus             ║
# ║  Lancé toutes les 15 min par mecaauto-update.timer (root)    ║
# ╚══════════════════════════════════════════════════════════════╝

set -uo pipefail

APP_DIR="/opt/meca-auto"
BRANCH="main"
LOG_FILE="${APP_DIR}/backups/auto_update.log"
URL="http://127.0.0.1:5000/"
APP_USER=$(stat -c '%U' "$APP_DIR")

mkdir -p "$(dirname "$LOG_FILE")"

log()     { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }
as_user() { runuser -u "$APP_USER" -- "$@"; }

app_ok() {
    # L'app peut mettre quelques secondes à démarrer : 6 essais sur 30 s
    for _ in 1 2 3 4 5 6; do
        sleep 5
        CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" --max-time 10 2>/dev/null)
        [ "$CODE" = "200" ] || [ "$CODE" = "302" ] && return 0
    done
    return 1
}

install_deps() {
    as_user "${APP_DIR}/venv/bin/pip" install -q -r "${APP_DIR}/requirements.txt" >> "$LOG_FILE" 2>&1
}

cd "$APP_DIR" || exit 1

as_user git fetch -q origin "$BRANCH" || { log "❌ git fetch impossible (réseau ou GitHub indisponible)"; exit 1; }

LOCAL=$(as_user git rev-parse HEAD)
REMOTE=$(as_user git rev-parse "origin/${BRANCH}")

# Rien de nouveau, ou le RPi est en avance sur GitHub
[ "$LOCAL" = "$REMOTE" ] && exit 0
as_user git merge-base --is-ancestor "$REMOTE" "$LOCAL" && exit 0

if ! as_user git merge-base --is-ancestor "$LOCAL" "$REMOTE"; then
    log "⚠️  Historique divergent entre le RPi et GitHub — mise à jour manuelle requise"
    exit 1
fi
if [ -n "$(as_user git status --porcelain --untracked-files=no)" ]; then
    log "⚠️  Fichiers modifiés localement sur le RPi — mise à jour annulée"
    exit 1
fi

log "🔄 Mise à jour ${LOCAL:0:7} → ${REMOTE:0:7}"
as_user git merge -q --ff-only "origin/${BRANCH}" || { log "❌ git merge échoué"; exit 1; }

DEPS_CHANGED=0
as_user git diff --quiet "$LOCAL" "$REMOTE" -- requirements.txt || DEPS_CHANGED=1
[ "$DEPS_CHANGED" = 1 ] && { log "📦 requirements.txt modifié — installation des dépendances"; install_deps; }

as_user "${APP_DIR}/venv/bin/python" migrate_db.py >> "$LOG_FILE" 2>&1 || log "⚠️  migrate_db.py a renvoyé une erreur"

systemctl restart mecaauto
if app_ok; then
    log "✅ Mise à jour réussie ($(as_user git log -1 --format='%h %s'))"
else
    log "❌ L'app ne répond plus après la mise à jour — retour à ${LOCAL:0:7}"
    as_user git reset -q --hard "$LOCAL"
    [ "$DEPS_CHANGED" = 1 ] && install_deps
    systemctl restart mecaauto
    if app_ok; then
        log "↩️  Version précédente restaurée"
    else
        log "❌ Restauration échouée — intervention manuelle requise (journalctl -u mecaauto)"
    fi
    exit 1
fi

# Garder les 500 dernières lignes du log
tail -500 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
