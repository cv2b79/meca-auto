#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║         MECA AUTO — Script de déploiement automatique       ║
# ║  Usage : bash deploy.sh                                     ║
# ║  Testé sur : Raspberry Pi OS Bookworm 64-bit                ║
# ╚══════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── Couleurs ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

log()     { echo -e "${BLUE}[INFO]${RESET}  $1"; }
ok()      { echo -e "${GREEN}[OK]${RESET}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $1"; }
error()   { echo -e "${RED}[ERROR]${RESET} $1"; exit 1; }
section() { echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"; echo -e "${BOLD}  $1${RESET}"; echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"; }

# ── Vérifications préalables ──────────────────────────────────
[ "$(id -u)" -eq 0 ] && error "Ne pas lancer en root. Utilisez un user normal avec sudo."
command -v sudo >/dev/null || error "sudo est requis"

section "MECA AUTO — Déploiement automatique"
echo "Ce script va installer et configurer MECA AUTO sur ce serveur."
echo "Durée estimée : 5-10 minutes."
echo ""

# ── Paramètres ────────────────────────────────────────────────
APP_USER=$(whoami)
APP_DIR="/opt/meca-auto"
REPO_URL="https://github.com/cv2b79/meca-auto.git"

read -p "Nom d'utilisateur du service [${APP_USER}] : " INPUT_USER
APP_USER="${INPUT_USER:-$APP_USER}"

read -p "Répertoire d'installation [${APP_DIR}] : " INPUT_DIR
APP_DIR="${INPUT_DIR:-$APP_DIR}"

read -p "Port de l'application [5000] : " APP_PORT
APP_PORT="${APP_PORT:-5000}"

echo ""
section "1/8 — Paquets système"
sudo apt update -q
sudo apt install -y \
    git python3 python3-pip python3-venv \
    postgresql postgresql-contrib \
    libcairo2-dev pkg-config libffi-dev python3-dev \
    cifs-utils curl
ok "Paquets installés"

section "2/8 — PostgreSQL"
sudo systemctl enable postgresql
sudo systemctl start postgresql

read -p "Nom de la base de données [mecaauto] : " DB_NAME
DB_NAME="${DB_NAME:-mecaauto}"
read -p "Utilisateur PostgreSQL [mecauser] : " DB_USER
DB_USER="${DB_USER:-mecauser}"
read -sp "Mot de passe PostgreSQL : " DB_PASS
echo ""

sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';" 2>/dev/null || warn "Utilisateur ${DB_USER} existe déjà"
sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" 2>/dev/null || warn "Base ${DB_NAME} existe déjà"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" 2>/dev/null || true
ok "PostgreSQL configuré"

section "3/8 — Code source"
sudo mkdir -p "$APP_DIR"
sudo chown "${APP_USER}:${APP_USER}" "$APP_DIR"

if [ -d "${APP_DIR}/.git" ]; then
    log "Dépôt existant — mise à jour..."
    git -C "$APP_DIR" pull
else
    log "Clonage du dépôt..."
    git clone "$REPO_URL" "$APP_DIR"
fi
ok "Code récupéré dans ${APP_DIR}"

section "4/8 — Environnement Python"
python3 -m venv "${APP_DIR}/venv"
"${APP_DIR}/venv/bin/pip" install -q --upgrade pip
"${APP_DIR}/venv/bin/pip" install -q -r "${APP_DIR}/requirements.txt"
ok "Dépendances Python installées"

section "5/8 — Configuration .env"
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

read -p "Domaine ou IP publique (ex: mecaauto.duckdns.org) : " APP_DOMAIN

read -p "Email SMTP (laisser vide pour ignorer) : " SMTP_USER
SMTP_PASS=""
SMTP_HOST=""
if [ -n "$SMTP_USER" ]; then
    read -p "Serveur SMTP [smtp.gmail.com] : " SMTP_HOST
    SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}"
    read -sp "Mot de passe SMTP : " SMTP_PASS
    echo ""
fi

cat > "${APP_DIR}/.env" << EOF
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@localhost/${DB_NAME}
SECRET_KEY=${SECRET_KEY}
FLASK_ENV=production

# Email (optionnel)
SMTP_HOST=${SMTP_HOST}
SMTP_PORT=587
SMTP_USER=${SMTP_USER}
SMTP_PASSWORD=${SMTP_PASS}
SMTP_FROM=${SMTP_USER}
EOF
chmod 600 "${APP_DIR}/.env"
ok ".env créé (SECRET_KEY générée aléatoirement)"

section "6/8 — Base de données"
cd "$APP_DIR"
"${APP_DIR}/venv/bin/python" migrate_db.py
ok "Tables créées"

section "7/8 — Service systemd"
sudo tee /etc/systemd/system/mecaauto.service > /dev/null << EOF
[Unit]
Description=MEC AUTO Flask App
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment="PATH=${APP_DIR}/venv/bin"
Environment="HOME=/home/${APP_USER}"
ExecStart=${APP_DIR}/venv/bin/gunicorn -w 2 -b 0.0.0.0:${APP_PORT} --timeout 120 "app:create_app()"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Watchdog
sudo tee /etc/systemd/system/mecaauto-watchdog.service > /dev/null << EOF
[Unit]
Description=MEC AUTO Watchdog
After=mecaauto.service

[Service]
Type=oneshot
ExecStart=/bin/bash ${APP_DIR}/scripts/healthcheck.sh
EOF

sudo tee /etc/systemd/system/mecaauto-watchdog.timer > /dev/null << EOF
[Unit]
Description=MEC AUTO Watchdog — toutes les 5 minutes
Requires=mecaauto.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mecaauto
sudo systemctl start mecaauto
sudo systemctl enable --now mecaauto-watchdog.timer
ok "Service démarré avec watchdog"

section "8/8 — Sauvegardes"
chmod +x "${APP_DIR}/scripts/backup.sh" "${APP_DIR}/scripts/healthcheck.sh" \
         "${APP_DIR}/scripts/restore.sh" "${APP_DIR}/scripts/list_backups.sh" \
         "${APP_DIR}/scripts/export_logs.sh"

mkdir -p "${APP_DIR}/backups"

# Sudoers pour le backup et l'export logs
sudo tee /etc/sudoers.d/mecaauto-backup > /dev/null << EOF
${APP_USER} ALL=(ALL) NOPASSWD: /bin/bash ${APP_DIR}/scripts/backup.sh
${APP_USER} ALL=(ALL) NOPASSWD: /bin/bash ${APP_DIR}/scripts/export_logs.sh
EOF
sudo chmod 0440 /etc/sudoers.d/mecaauto-backup

# Cron 2h du matin (backup BDD) + lundi 3h (export logs hebdo)
(sudo crontab -l 2>/dev/null | grep -v backup.sh | grep -v export_logs.sh; \
 echo "0 2 * * * /bin/bash ${APP_DIR}/scripts/backup.sh"; \
 echo "0 3 * * 1 /bin/bash ${APP_DIR}/scripts/export_logs.sh") | sudo crontab -
ok "Sauvegardes configurées (backup quotidien 2h00, export logs lundi 3h00)"

# ── Résumé ────────────────────────────────────────────────────
section "Déploiement terminé"
IP=$(hostname -I | awk '{print $1}')
echo -e "${GREEN}Application accessible sur :${RESET}"
echo -e "  Local  : http://${IP}:${APP_PORT}"
[ -n "${APP_DOMAIN:-}" ] && echo -e "  Public : https://${APP_DOMAIN} (via Nginx Proxy Manager)"
echo ""
echo -e "${YELLOW}Compte administrateur par défaut :${RESET}"
echo -e "  Login    : ddfpt"
echo -e "  Mot de passe : ddfpt123 (à changer immédiatement)"
echo ""
echo -e "${YELLOW}Prochaines étapes :${RESET}"
echo -e "  1. Changer le mot de passe admin dans l'interface"
echo -e "  2. Configurer le NAS : Administration → Sauvegardes"
echo -e "  3. Configurer l'email SMTP : Administration → Email"
echo -e "  4. Configurer Nginx Proxy Manager pour HTTPS"
echo ""
echo -e "${BLUE}Logs :${RESET}"
echo -e "  sudo journalctl -u mecaauto -f"
