# MEC AUTO - Manuel d'utilisation

## Logiciel de gestion d'atelier automobile pour lycée professionnel

---

## Installation

### Prérequis
- Python 3.8+
- PostgreSQL (optionnel, SQLite par défaut)

### Installation rapide
```bash
pip install -r requirements.txt
python run.py
```

### Première connexion
- **Login**: `admin`
- **Mot de passe**: `admin123`
- À la première connexion, il faudra changer le mot de passe

### Réinitialiser la base
```powershell
Remove-Item "instance\mecaauto.db"
python run.py
```
> Une nouvelle base vierge sera créée avec admin/admin123

---

## Rôles et permissions

| Rôle | Permissions |
|------|-------------|
| **DDFPT** | Admin complet, paramètres, statistiques, gestion utilisateurs |
| **Enseignant** | Créer/modifier OR, gérer clients/véhicules, interventions |
| **Magasinier** | Facturation, paramètres tarifs |
| **Élève** | Saisie interventions, états des lieux, contrôle visuel |

---

## Tableau de bord

- Statistiques globales (OR ouverts, en cours, terminés)
- OR récents accessibles selon votre rôle
- Les élèves voient uniquement leurs OR assignés
- Les enseignants peuvent créer de nouveaux OR

---

## Ordres de réparation (OR)

### Création d'un OR
1. Cliquez sur "Nouvel OR"
2. Saisissez le véhicule (recherche par immatriculation ou création)
3. Ajoutez la description de la réparation
4. Sélectionnez le mode de tarification (forfait ou horaire)
5. Affectez un élève responsable (optionnel)
6. Enregistrez

### Numéro d'OR
Format: `AAAA-Sxx-NNN` (ex: 2025-S18-042)

### Statuts
- **Ouvert** → **En cours** → **Terminé** → **Clôturé**

### États des lieux
- État des lieux d'**entrée** (à la prise du véhicule)
- État des lieux de **sortie** (à la restitution)
- Possibilité d'imprimer en PDF

---

## Véhicules

- Recherche par immatriculation (auto-complétion)
- Historique des propriétaires
- Lien vers les OR associés

---

## Clients

- Gestion des clients
- Coordonnées complètes
-Historique des véhicules possédés

---

## Facturation

1. Dans un OR terminé, cliquez sur "Générer facture"
2. La facture est calculée automatiquement (forfait + fournitures + éventuelles surcharges)
3. Possibilité d'envoyer par email ou télécharger en PDF

---

## Contrôle qualité (checklist)

Accessible uniquement aux enseignants/DDFPT pour créer et modifier les items de contrôle qualité.

---

## Statistiques

- Nombre d'OR par statut
- Export CSV des OR et interventions
- Indicateurs clés

---

## Import d'élèves

Via **Paramètres → Import d'élèves**:
- Format CSV attendu: `Nom, Prénom, Classe, Date de naissance`
- Login généré: 3 premières lettres du prénom + 3 premières lettres du nom
- Mot de passe provisoire: date de naissance (DDMMYYYY)

---

## Sécurité

- Verrouillage après 3 tentatives de connexion ratées (15 min)
- Mot de passe à changer à la première connexion
- Questions de sécurité pour la réinitialisation du mot de passe

---

## Dépannage

### Erreur de connexion base de données
Vérifier `DATABASE_URL` dans le fichier de configuration

### Erreur SMTP (factures par email)
Vérifier les identifiants SMTP dans la configuration

### Erreur PDF (WeasyPrint)
Vérifier que wkhtmltopdf est installé sur le système

---

## Support

Pour toute question ou problème, contactez l'administrateur DDFPT de l'établissement.