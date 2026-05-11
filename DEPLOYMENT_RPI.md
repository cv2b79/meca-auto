# Déploiement MECA AUTO sur Raspberry Pi 4

## Prérequis matériel

- Raspberry Pi 4 (2 Go RAM minimum, 4 Go recommandé)
- Carte microSD 32 Go+ Classe 10 (ou SSD USB)
- Alimentation USB-C 5V/3A
- Accès réseau local (câble Ethernet recommandé)
- NAS Synology sur le réseau local (pour les sauvegardes)

---

## 1. Système d'exploitation

Installer **Raspberry Pi OS Lite 64-bit** (Bookworm) via Raspberry Pi Imager.

Dans les options avancées de l'Imager :
- Activer SSH
- Définir un nom d'utilisateur (ex : `christophe`) et un mot de passe fort
- Configurer le WiFi si nécessaire

---

## 2. Mise à jour et paquets système

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-pip python3-venv \
    postgresql postgresql-contrib \
    libcairo2-dev pkg-config libffi-dev python3-dev \
    cifs-utils curl
```

---

## 3. PostgreSQL

```bash
sudo systemctl enable postgresql
sudo systemctl start postgresql

sudo -u postgres psql << 'EOF'
CREATE USER mecauser WITH PASSWORD 'CHANGER_CE_MOT_DE_PASSE';
CREATE DATABASE mecaauto OWNER mecauser;
GRANT ALL PRIVILEGES ON DATABASE mecaauto TO mecauser;
\q
EOF
```

---

## 4. Récupération du projet

```bash
sudo mkdir -p /opt/meca-auto
sudo chown christophe:christophe /opt/meca-auto
git clone https://github.com/cv2b79/meca-auto.git /opt/meca-auto
cd /opt/meca-auto
```

---

## 5. Environnement Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 6. Configuration `.env`

```bash
cp .env.example .env   # ou créer manuellement
nano .env
```

Contenu minimal :
```env
DATABASE_URL=postgresql://mecauser:CHANGER_CE_MOT_DE_PASSE@localhost/mecaauto
SECRET_KEY=generer-une-cle-aleatoire-longue-et-complexe
FLASK_ENV=production

# Email (optionnel)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=votre-app-password
```

> **Important** : `SECRET_KEY` est utilisée pour chiffrer les credentials NAS. Choisir une valeur longue et aléatoire. Ne jamais la changer une fois en production (sinon les credentials chiffrés deviennent illisibles).

Générer une clé aléatoire :
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 7. Initialisation de la base de données

```bash
source venv/bin/activate
python migrate_db.py
python run.py  # Lance une fois pour créer les tables, Ctrl+C ensuite
```

---

## 8. Service systemd (Gunicorn)

```bash
sudo nano /etc/systemd/system/mecaauto.service
```

```ini
[Unit]
Description=MEC AUTO Flask App
After=network.target

[Service]
Type=simple
User=christophe
Group=christophe
WorkingDirectory=/opt/meca-auto
Environment="PATH=/opt/meca-auto/venv/bin"
Environment="HOME=/home/christophe"
ExecStart=/opt/meca-auto/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 --timeout 120 "app:create_app()"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mecaauto
sudo systemctl start mecaauto
sudo systemctl status mecaauto
```

---

## 9. Watchdog (redémarrage automatique)

```bash
sudo nano /etc/systemd/system/mecaauto-watchdog.service
```
```ini
[Unit]
Description=MEC AUTO Watchdog
After=mecaauto.service

[Service]
Type=oneshot
ExecStart=/bin/bash /opt/meca-auto/scripts/healthcheck.sh
```

```bash
sudo nano /etc/systemd/system/mecaauto-watchdog.timer
```
```ini
[Unit]
Description=MEC AUTO Watchdog — toutes les 5 minutes
Requires=mecaauto.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mecaauto-watchdog.timer
```

---

## 10. Sauvegardes automatiques

### Cron (2h du matin, tous les jours)
```bash
sudo crontab -e
```
Ajouter :
```
0 2 * * * /bin/bash /opt/meca-auto/scripts/backup.sh
```

### Configuration NAS
Dans l'interface web : **Administration → 🗄️ Sauvegardes**

Renseigner :
- IP du NAS (ex : `192.168.1.3`)
- Nom du partage SMB (ex : `Backupapps`)
- Identifiant et mot de passe NAS
- Dossier de destination (ex : `mecapro`)
- Rétention en jours (défaut : 30)

> Les credentials NAS sont chiffrés en base de données (Fernet/AES-128).  
> Le fichier `scripts/backup.conf` (déchiffré, utilisé par bash) est en `chmod 600`.

### Prérequis NAS Synology
- SMB activé dans DSM → Panneau de configuration → Services de fichiers
- L'utilisateur NAS doit avoir accès **Lecture/Écriture** au partage
- Version SMB : 3.0 (DSM 7 par défaut)

---

## 11. HTTPS avec Nginx Proxy Manager

Nginx Proxy Manager (NPM) doit tourner sur une machine du réseau (ex : autre RPi, NAS, VM).

Dans NPM → **Proxy Hosts → Add Proxy Host** :
- Domain : `votre-sous-domaine.duckdns.org`
- Scheme : `http`
- Forward Hostname : `192.168.1.XX` (IP du RPi)
- Forward Port : `5000`
- Onglet SSL → Request a new SSL Certificate (Let's Encrypt)

> **Important** : le Scheme doit être `http` (NPM gère le SSL lui-même).

---

## 12. Sécurité SSH

```bash
# Désactiver la connexion root
sudo sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config

# Limiter aux logins autorisés
echo "AllowUsers christophe" | sudo tee -a /etc/ssh/sshd_config

sudo systemctl restart ssh
```

Ne pas exposer le port 22 sur Internet — accès SSH uniquement depuis le réseau local.

---

## Commandes de maintenance

| Action | Commande |
|--------|----------|
| Démarrer le service | `sudo systemctl start mecaauto` |
| Arrêter | `sudo systemctl stop mecaauto` |
| Redémarrer | `sudo systemctl restart mecaauto` |
| Logs en direct | `sudo journalctl -u mecaauto -f` |
| Statut | `sudo systemctl status mecaauto` |
| Lancer une sauvegarde | `sudo /bin/bash /opt/meca-auto/scripts/backup.sh` |
| Voir les sauvegardes | `bash /opt/meca-auto/scripts/list_backups.sh` |
| Log sauvegardes | `tail -50 /opt/meca-auto/backups/backup.log` |
| Log watchdog | `tail -50 /opt/meca-auto/backups/watchdog.log` |
| Restaurer une sauvegarde | `sudo bash /opt/meca-auto/scripts/restore.sh` |
| Mettre à jour le code | `sudo -u christophe git -C /opt/meca-auto pull && sudo systemctl restart mecaauto` |

---

## Structure du projet

```
/opt/meca-auto/
├── app/                    # Application Flask
│   ├── routes/             # Blueprints (clients, véhicules, OR, settings…)
│   ├── templates/          # Templates Jinja2
│   ├── models.py           # Modèles SQLAlchemy
│   └── __init__.py         # Factory Flask
├── scripts/
│   ├── backup.sh           # Sauvegarde PostgreSQL + NAS
│   ├── restore.sh          # Restauration
│   ├── healthcheck.sh      # Watchdog
│   ├── list_backups.sh     # Liste des sauvegardes
│   ├── notify_backup.py    # Notification email
│   └── backup.conf         # Config NAS déchiffrée (chmod 600, non versionné)
├── backups/                # Fichiers de sauvegarde locaux (non versionnés)
├── venv/                   # Environnement Python (non versionné)
├── .env                    # Variables d'environnement (non versionné)
├── migrate_db.py           # Script de migration PostgreSQL
├── requirements.txt        # Dépendances Python
└── run.py                  # Point d'entrée
```
