# 🔧 MECA AUTO

Logiciel de gestion d'atelier automobile pour lycée professionnel — section Maintenance des Véhicules Automobiles (MVA).

Développé avec Flask (Python), PostgreSQL, déployé sur Raspberry Pi 4.

---

## Fonctionnalités

### Gestion des ordres de réparation (OR)
- Création, suivi et clôture des OR
- Affectation véhicule / client / élève
- Statuts : Ouvert → En cours → Terminé → Clôturé
- Génération de factures PDF
- Notifications email automatiques au client

### Gestion des clients et véhicules
- Fiches clients avec historique OR
- Fiches véhicules (immatriculation, VIN, énergie, kilométrage)

### Pédagogie
- Gestion des classes et élèves par les enseignants
- Import CSV d'élèves (compatible Pronote)
- Saisie des interventions par les élèves
- Checklist de contrôle visuel

### Administration (DDFPT)
- Gestion des utilisateurs, rôles et permissions
- Configuration email SMTP
- Sauvegarde PostgreSQL automatique + copie NAS Synology
- Interface graphique de configuration des sauvegardes
- Journaux d'activité complets

### Sécurité
- Authentification avec verrouillage après tentatives échouées
- Chiffrement Fernet (AES-128) des credentials sensibles en BDD
- En-têtes HTTP de sécurité (CSP, HSTS, X-Frame-Options…)
- HTTPS via Nginx Proxy Manager + Let's Encrypt
- Watchdog systemd (redémarrage automatique si l'app ne répond plus)

---

## Architecture

```
Internet
   │
   ▼
Nginx Proxy Manager (HTTPS / Let's Encrypt)
   │  port 443 → port 5000
   ▼
Gunicorn (2 workers) — port 5000
   │
   ▼
Flask 3.0 (Python)
   │
   ▼
PostgreSQL 17
   │
   ▼
NAS Synology (sauvegarde CIFS/SMB quotidienne)
```

## Rôles

| Rôle | Accès |
|------|-------|
| **DDFPT** | Administration complète, suppression OR/factures, sauvegardes |
| **Enseignant** | Création OR, gestion classes/élèves, checklist |
| **Magasinier** | Facturation, fournitures |
| **Élève** | Saisie interventions sur OR affectés |

---

## Déploiement

Voir [DEPLOYMENT_RPI.md](DEPLOYMENT_RPI.md) pour le guide complet d'installation sur Raspberry Pi 4.

## Guide utilisateur

Voir [docs/guide_utilisateur.md](docs/guide_utilisateur.md) pour le guide d'utilisation par rôle.

---

## Stack technique

| Composant | Version |
|-----------|---------|
| Python | 3.13 |
| Flask | 3.0 |
| SQLAlchemy | 3.1 |
| PostgreSQL | 17 |
| Gunicorn | 21.2 |
| cryptography | ≥ 3.4 |
| Raspberry Pi OS | Bookworm (64-bit) |

---

## Licence

Usage interne — Lycée professionnel. Non destiné à une distribution publique.
