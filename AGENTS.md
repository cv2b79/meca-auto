# MEC AUTO - Documentation pour agents IA

## Présentation

**MEC AUTO** est un logiciel de gestion d'atelier automobile pour lycée professionnel.
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

### Avec Docker (recommandé pour déploiement Raspberry Pi)
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
- Statuts: ouvert → en_cours → termine → cloture
- Modes tarification: forfait ou horaire

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

## Génération PDF (WeasyPrint)

Les factures sont générées via `WeasyPrint` dans `app/routes/factures.py`:
- Route `/factures/<id>/pdf` génère le PDF
- Template dans `app/templates/factures/pdf.html`

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