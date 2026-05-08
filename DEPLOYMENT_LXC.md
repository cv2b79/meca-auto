# Déploiement léger MEC AUTO sur Proxmox (LXC)

## Prérequis LXC
- **Modèle**: Debian 12 (ID 100)
- **CPU**: 1 vCPU
- **RAM**: 512 Mo (minimum)
- **Disque**: 2 Go

---

## Installation (5 min)

```bash
# 1. Mise à jour
apt update && apt upgrade -y

# 2. Installer Python + Git
apt install python3 python3-pip python3-venv git -y

# 3. Récupérer le projet
cd /opt
git clone https://github.com/cv2b79/meca-auto.git
cd meca-auto

# 4. Créer environnement virtuel
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Initialiser la base (SQLite par défaut)
python run.py &
```

---

## Démarrage automatique (optionnel)

Créer `/etc/systemd/system/mecaauto.service`:
```ini
[Unit]
Description=MEC AUTO
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/meca-auto
Environment="PATH=/opt/meca-auto/venv/bin"
ExecStart=/opt/meca-auto/venv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Activer:
```bash
systemctl daemon-reload
systemctl enable mecaauto
systemctl start mecaauto
```

---

## Accès

- **URL**: `http://IP_DU_LXC:5000`
- **Admin**: `admin` / `admin123`

---

## Mise à jour

```bash
cd /opt/meca-auto
git pull
systemctl restart mecaauto
```

---

## Sauvegarde

Copier le fichier de base de données:
```bash
cp /opt/meca-auto/instance/mecaauto.db /backup/mecaauto_$(date +%Y%m%d).db
```