# Déploiement MEC AUTO sur Raspberry Pi 4

## Matériel
- Raspberry Pi 4 (2Go ou 4Go RAM recommandé)
- Carte microSD 32Go+ ( Classe 10 )
- Alimentation USB-C 5V 3A

## Système d'exploitation

### Option A: Raspberry Pi OS Lite (recommandé - sans interface graphique)
- Télécharger: https://www.raspberrypi.com/software/operating-systems/
- Flasher avec Raspberry Pi Imager
- Configurer SSH et WiFi à l'avance (via Raspberry Pi Imager)

### Option B: Raspberry Pi OS Desktop
- Même téléchargement, version avec bureau

---

## Installation sur le Raspberry Pi

### 1. Mise à jour du système
```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

### 2. Installation de PostgreSQL
```bash
sudo apt install postgresql postgresql-contrib -y
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### 3. Création de la base de données
```bash
sudo -u postgres psql
```

Dans PostgreSQL:
```sql
CREATE USER mecauser WITH PASSWORD 'MecaAuto2024!';
CREATE DATABASE mecaauto OWNER mecauser;
GRANT ALL PRIVILEGES ON DATABASE mecaauto TO mecauser;
\q
```

### 4. Installation de Python et dépendances
```bash
sudo apt install python3 python3-pip python3-venv git -y
```

### 5. Récupération du projet
```bash
cd /opt
sudo git clone https://github.com/ton-compte/meca-auto.git
cd meca-auto
```

### 6. Création de l'environnement virtuel
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 7. Configuration des variables d'environnement
Créer un fichier `.env`:
```bash
cp .env.example .env
nano .env
```

Contenu:
```
DATABASE_URL=postgresql://mecauser:MecaAuto2024!@localhost/mecaauto
SECRET_KEY=change-this-secret-key-in-production
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ton-email@gmail.com
SMTP_PASSWORD=ton-app-password
```

### 8. Initialisation de la base
```bash
python run.py
```
Cela créera les tables et l'utilisateur admin (admin/admin123)

### 9. Installation de Gunicorn et Nginx

**Gunicorn** (serveur Python):
```bash
pip install gunicorn
```

**Nginx** (serveur web):
```bash
sudo apt install nginx -y
```

### 10. Configuration Nginx

Créer `/etc/nginx/sites-available/mecaauto`:
```nginx
server {
    listen 80;
    server_name IP_DU_RPI ou nom-de-domaine;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Activer le site:
```bash
sudo ln -s /etc/nginx/sites-available/mecaauto /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 11. Service systemd pour Gunicorn

Créer `/etc/systemd/system/mecaauto.service`:
```ini
[Unit]
Description=MEC AUTO Flask App
After=network.target

[Service]
User=pi
Group=pi
WorkingDirectory=/opt/meca-auto
Environment="PATH=/opt/meca-auto/venv/bin"
ExecStart=/opt/meca-auto/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 3 run:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Activer le service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable mecaauto
sudo systemctl start mecaauto
```

---

## Commandes utiles

| Action | Commande |
|--------|----------|
| Démarrer | `sudo systemctl start mecaauto` |
| Arrêter | `sudo systemctl stop mecaauto` |
| Redémarrer | `sudo systemctl restart mecaauto` |
| Logs | `sudo journalctl -u mecaauto -f` |
| Statut | `sudo systemctl status mecaauto` |

---

## Sauvegarde

### Sauvegarde base de données
```bash
sudo -u postgres pg_dump mecaauto > backup_$(date +%Y%m%d).sql
```

### Restaurer
```bash
sudo -u postgres psql mecaauto < backup_20240101.sql
```

---

## Pour aller plus loin

- **Nom de domaine**: Acheter un nom de domaine et utiliser ddclient pour IP dynamique
- **HTTPS**: Installer Certbot pour SSL gratuit
- **Backup automatique**: Cron job quotidienne
- **Monitoring**: Installer Cockpit pour interface web

---

## Accès

- URL: `http://IP_DU_RASPBERRYPI`
- Admin: `admin` / `admin123` (à changer!)