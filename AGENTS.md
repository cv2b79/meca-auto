# MECA AUTO - Documentation pour agents IA

## Présentation

**MECA AUTO** est un logiciel de gestion d'atelier automobile pour lycée professionnel.
Stack technique : Flask + PostgreSQL + HTMX (pas de framework JS lourd).

## Structure du projet

```
meca auto/
├── app/
│   ├── __init__.py       # Application Flask factory
│   ├── models.py         # Modèles SQLAlchemy (User, Client, Vehicule, OrdreReparation, Facture, etc.)
│   ├── routes/          # Routes Flask blueprints
│   │   ├── auth.py       # Login/logout
│   │   ├── main.py       # Dashboard, settings
│   │   ├── clients.py    # CRUD clients
│   │   ├── vehicules.py  # CRUD véhicules + recherche par plaque
│   │   ├── ordres.py     # CRUD ordres de réparation
│   │   ├── factures.py   # Facturation + PDF + envoi mail
│   │   └── stats.py      # Statistiques + export CSV
│   └── templates/        # Templates Jinja2 (HTML)
├── config.py            # Configuration (DB, SMTP, etc.)
├── run.py               # Point d'entrée
├── requirements.txt     # Dépendances Python
├── docker-compose.yml   # Déploiement complet (DB + Web)
└── Dockerfile           # Image Docker
```

## Commandes utiles

### Développement local (sans Docker)
```bash
# Installer les dépendances
pip install -r requirements.txt

# Initialiser la base (crée admin/admin123)
python run.py
# Le serveur démarre sur http://localhost:5000

# Pour migration DB (si modification des modèles)
flask db init
flask db migrate -m "migration message"
flask db upgrade
```

### Production : Raspberry Pi (systemd, PAS Docker)
- Code dans `/opt/meca-auto`, service systemd `mecaauto` (gunicorn), base PostgreSQL locale, `.env` sur le Pi.
- **Mise à jour automatique** : timer `mecaauto-update` (toutes les 15 min) → `scripts/auto_update.sh` :
  `git pull` de `main`, `pip install` si `requirements.txt` change, `migrate_db.py`, redémarrage,
  retour à la version précédente si l'app ne répond plus. Journal : `backups/auto_update.log`.
- **Un push sur `main` = déploiement en production.** Forcer tout de suite : `sudo systemctl start mecaauto-update`.
- Procédure complète : `DEPLOYMENT_RPI.md`. Historique des changements : `CHANGELOG.md`.
- Le dépôt GitHub est **public** : aucune donnée réelle ni secret dans git (voir `.gitignore`).

### Avec Docker (ancien mode, non utilisé en production)
```bash
# Lancer tout (PostgreSQL + Flask)
docker-compose up -d

# Logs
docker-compose logs -f web

# Arrêter
docker-compose down
```

### Configuration SMTP (pour envoi factures)
Éditer le fichier `.env` (copier depuis `.env.example`):
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=app-password
```

## Modèles de données

### Users (rôles: ddfpt, magasinier, enseignant, eleve)
- **ddfpt**: Admin complet, paramétrage, statistiques
- **magasinier**: Facturation, paramètres tarifs
- **enseignant**: Création/gestion OR
- **eleve**: Saisie interventions

### Ordres de réparation
- Format numéro: `AAAA-Sxx-NNN` (ex: 2025-S18-042)
- Statuts: ouvert → en_cours → termine (travaux finis) → cloture (dossier fermé ; la création de facture clôture l'OR)
- Modes tarification: forfait ou horaire
- `heures_vehicule` (heures pleines) = temps facturé en mode horaire ; les heures des `EleveIntervention`
  (heures pleines) servent au suivi pédagogique et ne sont pas facturées
- `date_sortie_prevue` : alertes tableau de bord (jour J, retard)
- Dates stockées en UTC (`datetime.utcnow`) : afficher avec le filtre Jinja `heure_locale`

### Facturation (`app/routes/factures.py`)
- `calcul_montants(or_obj, taux_horaire)` est la **seule** source du calcul (montant enregistré, page de création,
  impression, PDF) : forfait → `or.montant` ; horaire → `heures_vehicule × taux` ; + fournitures + dépollution ;
  0 si `pas_de_facturation`.
- `Facture.taux_horaire` fige le taux à l'émission ; la page facture signale un écart montant/calcul
  (route `/factures/<id>/recalcul`).

### Véhicules
- Recherche par immatriculation (auto-complétion)
- Gestion historique propriétaire

## Pages principales

1. **/** - Tableau de bord (stats + OR récents)
2. **/clients** - Liste clients
3. **/vehicules** - Liste véhicules (recherche plaque)
4. **/ordres** - Liste OR (filtres statut)
5. **/ordres/new** - Créer OR (saisie véhicule + description)
6. **/ordres/<id>** - Vue détail OR + interventions + états lieux
7. **/factures** - Liste factures
8. **/stats** - Statistiques + export CSV

## Génération PDF

- Factures : `WeasyPrint` dans `app/routes/factures.py` (route `/factures/<id>/pdf`, template `factures/pdf.html`,
  même base `facture_base.html` que l'impression). WeasyPrint n'est pas dans `requirements.txt` : à vérifier sur le Pi.
- PDF de l'OR joint au mail magasinier/DDFPT : `xhtml2pdf` (`ordres/email_or_pdf.html`).

## Emails
- Tout envoi passe par `app/smtp_utils.smtp_send` (SSL sur 465, STARTTLS sinon, délai 20 s, AUTH PLAIN pour que
  Gmail renvoie la vraie erreur 535). Gmail : mot de passe d'application obligatoire.

## Tests avant mise en production
Pas de suite de tests dans le dépôt. Tester avec le client de test Flask sur une base SQLite jetable
(`DATABASE_URL=sqlite:///…`, `Config.SQLALCHEMY_DATABASE_URI` surchargé avant `create_app()`), puis faire valider
l'utilisateur sur un serveur local avant tout push.

## Maintenance

### Sauvegarde PostgreSQL
```bash
docker exec mecaauto-db-1 pg_dump -U mecauser mecaauto > backup.sql
```

### Mise à jour
```bash
git pull
docker-compose down
docker-compose up -d --build
```

## Erreurs courantes

- **Erreur connexion DB**: Vérifier `DATABASE_URL` dans `.env`
- **Erreur SMTP**: Vérifier les identifiants SMTP
- **Erreur PDF**: WeasyPrint nécessite des dépendances système (wkhtmltopdf)