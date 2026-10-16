#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║   MECA AUTO — Active la mise à jour automatique (une fois)   ║
# ║  Usage : sudo bash /opt/meca-auto/scripts/install_auto_update.sh
# ╚══════════════════════════════════════════════════════════════╝

set -euo pipefail

APP_DIR="/opt/meca-auto"

[ "$(id -u)" -eq 0 ] || { echo "À lancer avec sudo"; exit 1; }

tee /etc/systemd/system/mecaauto-update.service > /dev/null << EOF
[Unit]
Description=MEC AUTO Mise à jour automatique depuis GitHub
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash ${APP_DIR}/scripts/auto_update.sh
EOF

tee /etc/systemd/system/mecaauto-update.timer > /dev/null << EOF
[Unit]
Description=MEC AUTO Mise à jour automatique — toutes les 15 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now mecaauto-update.timer

echo "✅ Mise à jour automatique activée (vérification toutes les 15 min)"
echo "   Journal      : ${APP_DIR}/backups/auto_update.log"
echo "   Tester       : sudo systemctl start mecaauto-update"
echo "   Désactiver   : sudo systemctl disable --now mecaauto-update.timer"
