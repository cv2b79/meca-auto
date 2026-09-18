#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║   MECA AUTO — Installation HTTPS (Caddy) sur le Raspberry   ║
# ║  Usage : bash /opt/meca-auto/scripts/setup_https.sh         ║
# ║  Tout reste sur le Pi : Caddy fait le HTTPS devant Gunicorn ║
# ╚══════════════════════════════════════════════════════════════╝

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'
log()   { echo -e "${BLUE}[INFO]${RESET}  $1"; }
ok()    { echo -e "${GREEN}[OK]${RESET}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $1"; }
error() { echo -e "${RED}[ERROR]${RESET} $1"; exit 1; }

[ "$(id -u)" -eq 0 ] && error "Ne pas lancer en root. Utilisez votre utilisateur normal (sudo sera demandé)."

APP_DIR="/opt/meca-auto"
ENV_FILE="${APP_DIR}/.env"
SERVICE="/etc/systemd/system/mecaauto.service"
IP=$(hostname -I | awk '{print $1}')

[ -f "$ENV_FILE" ] || error "$ENV_FILE introuvable"
[ -f "$SERVICE" ]  || error "$SERVICE introuvable (lancer d'abord deploy.sh)"

# ── 1. Vérifier le .env ──────────────────────────────────────
KEY=$(grep -E '^SECRET_KEY=' "$ENV_FILE" | cut -d= -f2- || true)
if [ ${#KEY} -lt 32 ] || echo "$KEY" | grep -qi change; then
    echo ""
    warn "La SECRET_KEY du .env est absente ou trop faible."
    warn "Avec la nouvelle version, l'application refusera de démarrer."
    warn "ATTENTION : changer la clé oblige à ressaisir les identifiants NAS"
    warn "(Administration → Sauvegardes) car ils sont chiffrés avec elle."
    read -p "Générer une nouvelle clé maintenant ? [o/N] : " R
    if [[ "$R" =~ ^[oO]$ ]]; then
        cp "$ENV_FILE" "${ENV_FILE}.bak-$(date +%Y%m%d%H%M)"
        NEWKEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        if grep -qE '^SECRET_KEY=' "$ENV_FILE"; then
            sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${NEWKEY}|" "$ENV_FILE"
        else
            echo "SECRET_KEY=${NEWKEY}" >> "$ENV_FILE"
        fi
        ok "Nouvelle SECRET_KEY écrite (ancien .env sauvegardé)"
    else
        error "Arrêt. Corriger SECRET_KEY dans $ENV_FILE puis relancer."
    fi
fi
if grep -qE '^FLASK_ENV=' "$ENV_FILE"; then
    sed -i 's|^FLASK_ENV=.*|FLASK_ENV=production|' "$ENV_FILE"
else
    echo "FLASK_ENV=production" >> "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"
ok ".env vérifié (FLASK_ENV=production)"

# ── 2. Choix du mode ─────────────────────────────────────────
echo ""
echo -e "${BOLD}Comment le logiciel sera-t-il utilisé ?${RESET}"
echo "  1) Uniquement sur le réseau du lycée (https://${IP})"
echo "     → certificat interne, avertissement du navigateur à accepter une fois"
echo "  2) Aussi depuis Internet avec un nom de domaine (ex: mecaauto.duckdns.org)"
echo "     → certificat Let's Encrypt, ports 80 et 443 à ouvrir sur la box/routeur"
read -p "Choix [1] : " MODE
MODE="${MODE:-1}"

if [ "$MODE" = "2" ]; then
    read -p "Nom de domaine (ex: mecaauto.duckdns.org) : " DOMAIN
    [ -n "$DOMAIN" ] || error "Domaine obligatoire"
    SITE="$DOMAIN"
    TLS_LINE=""
    HSTS='        Strict-Transport-Security "max-age=31536000"'
    # L'IP locale reste servie (certificat interne) : le logiciel reste
    # accessible sur le réseau même si le domaine/NAT n'est pas encore prêt.
    EXTRA_SITE="${IP} {
    tls internal
    encode gzip
    reverse_proxy 127.0.0.1:5000
}"
else
    SITE="${IP}"
    TLS_LINE="    tls internal"
    HSTS=""
    EXTRA_SITE="http://${IP} {
    redir https://${IP}{uri}
}"
fi

# Accès par IP : le navigateur n'envoie pas de nom (SNI), Caddy doit savoir quel certificat servir
GLOBAL="{
    default_sni ${IP}
}"

# ── 3. Installer Caddy ───────────────────────────────────────
log "Installation de Caddy..."
sudo apt update -q
sudo apt install -y caddy
ok "Caddy installé"

sudo cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak-$(date +%Y%m%d%H%M)" 2>/dev/null || true
sudo tee /etc/caddy/Caddyfile > /dev/null << EOF
# MECA AUTO — généré par scripts/setup_https.sh
${GLOBAL}
${SITE} {
${TLS_LINE}
    encode gzip
    request_body {
        max_size 20MB
    }
    header {
${HSTS}
        -Server
    }
    reverse_proxy 127.0.0.1:5000
}
${EXTRA_SITE}
EOF
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null \
    || error "Caddyfile invalide — voir /etc/caddy/Caddyfile"
sudo systemctl enable caddy
sudo systemctl restart caddy
ok "Caddy configuré pour https://${SITE}"

# ── 4. Gunicorn n'écoute plus que localement ─────────────────
sudo cp "$SERVICE" "${SERVICE}.bak-$(date +%Y%m%d%H%M)"
# Le service peut lancer « python run.py » (serveur de dev) ou gunicorn :
# dans les deux cas on le remplace par gunicorn écoutant uniquement en local.
sudo sed -i "s|^ExecStart=.*|ExecStart=${APP_DIR}/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 --timeout 120 \"app:create_app()\"|" "$SERVICE"
sudo systemctl daemon-reload
sudo systemctl restart mecaauto
sleep 3
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/ --max-time 10 | grep -qE '^(200|302)$'; then
    ok "Application redémarrée (port 5000 accessible uniquement depuis le Pi)"
else
    warn "L'application ne répond pas. Voir : sudo journalctl -u mecaauto -n 50"
fi

# ── 5. Pare-feu ──────────────────────────────────────────────
read -p "Activer le pare-feu (SSH depuis le réseau local, 80/443 ouverts) ? [O/n] : " FW
if [[ ! "$FW" =~ ^[nN]$ ]]; then
    sudo apt install -y ufw
    # SSH en premier (on ne se coupe pas l'accès), depuis tout réseau local privé :
    # l'accès survit à un changement de box, Internet reste bloqué.
    for LAN in 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12; do
        sudo ufw allow from "$LAN" to any port 22 proto tcp
    done
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw --force enable
    ok "Pare-feu actif (SSH autorisé depuis les réseaux locaux uniquement)"
fi

# ── Résumé ───────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}HTTPS en place.${RESET} Adresse : ${BOLD}https://${SITE}${RESET}"
if [ "$MODE" != "2" ]; then
    echo ""
    echo "Le navigateur affichera un avertissement la 1re fois (certificat interne) :"
    echo "cliquer « Paramètres avancés » → « Continuer vers le site »."
    echo "Pour supprimer l'avertissement sur un poste, installer ce certificat racine :"
    echo "  /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt"
else
    echo ""
    echo "En local : https://${IP} (certificat interne) en attendant le NAT."
    echo "Sur la box/routeur : rediriger le port 443 (et 80 si possible) vers ${IP}."
    echo "Tant que le NAT n'est pas en place, Let's Encrypt échouera (normal) :"
    echo "voir sudo journalctl -u caddy -f"
    echo "Ne JAMAIS rediriger le port 22 (SSH) ni le 5000."
fi
echo ""
echo "Retour arrière : sudo systemctl stop caddy, puis restaurer ${SERVICE}.bak-*"
