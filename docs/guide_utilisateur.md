# Guide utilisateur — MECA AUTO

Application de gestion d'atelier automobile pour lycée professionnel (section MVA).

---

## Connexion

Accéder à l'application via le navigateur (URL fournie par l'établissement).

| Champ | Valeur |
|-------|--------|
| Login | Fourni par l'administrateur |
| Mot de passe | Fourni à la création du compte |

> À la première connexion, vous serez invité à changer votre mot de passe.

En cas d'oubli, contacter le DDFPT.

---

## Rôles et accès

| Rôle | Profil |
|------|--------|
| **DDFPT** | Administrateur — accès complet |
| **Enseignant** | Gestion OR, classes, élèves |
| **Magasinier** | Facturation et fournitures |
| **Élève** | Saisie d'interventions uniquement |

---

## Guide par rôle

---

### 👨‍💼 DDFPT (Administrateur)

#### Tableau de bord
Vue d'ensemble : OR en cours, statistiques, alertes.

#### Ordres de réparation
- **Créer un OR** : Menu OR → Nouveau → choisir client, véhicule, élève
- **Modifier** : cliquer sur l'OR → Modifier
- **Changer le statut** : Ouvert → En cours → Terminé → Clôturé
- **Supprimer un OR** (même avec facture) : bouton 🗑️ sur la fiche OR
- **Générer une facture** : OR clôturé → bouton Facturer

#### Administration (`/settings/admin`)

**Onglet 👥 Utilisateurs**
- Créer / modifier / désactiver / supprimer des comptes
- Assigner un rôle et une classe aux élèves
- Importer des élèves via CSV (format Pronote compatible)

**Onglet 🏫 Établissement**
- Nom, adresse, téléphone, email, SIRET/UAI
- Ces informations apparaissent sur les factures PDF

**Onglet 🧴 Fournitures**
- Gérer le catalogue de fournitures avec prix unitaires
- Utilisées lors de la facturation des OR

**Onglet 📧 Email**
- Configurer le serveur SMTP pour les notifications
- Activer/désactiver les notifications automatiques aux clients :
  - OR créé, OR en cours, OR clôturé, facture émise

**Onglet 💾 Données**
- Export CSV : clients, véhicules, OR
- Import CSV : clients, véhicules
- Archivage des OR anciens

**Onglet 🗄️ Sauvegardes**
- Voir le statut de la dernière sauvegarde (✅/❌)
- Lancer une sauvegarde manuelle
- Consulter le log complet
- Configurer le NAS Synology (IP, partage, credentials)
- Liste des fichiers de sauvegarde locaux

**Onglet 🔒 Sécurité**
- Nombre de tentatives de connexion avant verrouillage
- Durée du verrouillage
- Changer son mot de passe

---

### 👨‍🏫 Enseignant

#### Ordres de réparation
- Créer et modifier des OR
- Affecter un élève à un OR
- Suivre l'avancement des travaux

#### Gestion des élèves (`/settings/eleves`)
- **Classes** : créer, modifier, activer/désactiver
- **Élèves** : ajouter manuellement ou via import CSV
  - Login généré automatiquement : 3 lettres prénom + 3 lettres nom
  - Mot de passe provisoire : date de naissance (JJMMAAAA) ou login si pas de DDN
- **Import CSV** : bouton "📥 Importer CSV"
  - Colonnes attendues : `nom`, `prénom`, `classe`, `date de naissance`, `adresse e-mail`
  - Séparateur `;` ou `,` (détecté automatiquement)
  - Compatible export Pronote
  - [Télécharger le modèle CSV](/settings/eleves/modele-csv)

#### Checklist (`/settings/checklist`)
- Gérer les points de contrôle visuel
- Activer/désactiver des points

---

### 🔧 Magasinier

#### Facturation
- Accéder aux OR terminés
- Créer des factures (main d'œuvre + fournitures + consommables)
- Générer le PDF facture

#### Fournitures
- Consulter le stock
- Saisir les fournitures utilisées dans un OR

---

### 🎓 Élève

#### Mes interventions
- Accéder aux OR sur lesquels vous êtes affecté
- Saisir le détail des interventions réalisées :
  - Description du travail
  - Durée
  - Observations

#### Checklist
- Remplir la checklist de contrôle visuel pour un OR

> Les élèves ne peuvent pas créer ni modifier les OR, ni accéder aux données des autres élèves.

---

## Workflow d'un OR

```
1. CRÉATION
   Enseignant/DDFPT crée l'OR
   → Client + Véhicule + Élève assigné
   → Statut : Ouvert

2. TRAVAUX
   Élève saisit ses interventions
   → Statut : En cours

3. CONTRÔLE
   Enseignant vérifie et valide
   → Checklist de contrôle visuel
   → Statut : Terminé

4. FACTURATION
   Magasinier/DDFPT facture
   → PDF généré
   → Email envoyé au client (si configuré)
   → Statut : Clôturé
```

---

## Import CSV élèves

### Format attendu

```csv
nom;prénom;classe;date de naissance;adresse e-mail
DUPONT;Martin;1MAVA;15/03/2008;martin.dupont@lycee.fr
MARTIN;Sophie;1MAVA;22/07/2008;
BERNARD;Lucas;2MAVA;05/11/2007;
```

### Règles
- **Séparateur** : `;` (point-virgule) ou `,` — détecté automatiquement
- **Encodage** : UTF-8 (avec ou sans BOM — compatible Excel)
- **Login** généré : `mar` + `dup` → `mardup` (3 lettres prénom + 3 lettres nom, minuscules)
- **Mot de passe** : date de naissance sans séparateurs (`15032008`) ou login si pas de DDN
- **Classe** : créée automatiquement si elle n'existe pas encore
- Les lignes sans nom ou prénom sont ignorées (avec message d'avertissement)

[📥 Télécharger le modèle CSV](/settings/eleves/modele-csv)

---

## Sauvegardes (DDFPT)

Les sauvegardes sont gérées dans **Administration → 🗄️ Sauvegardes**.

### Automatique
Sauvegarde quotidienne à **2h du matin** :
- Dump PostgreSQL compressé (`.sql.gz`)
- Vérification intégrité (taille, gzip, nombre de tables)
- Copie sur NAS Synology
- Rotation des fichiers > 30 jours (configurable)
- Email de résultat (si SMTP configuré)

### Manuelle
Bouton **▶️ Lancer une sauvegarde** dans l'onglet Sauvegardes.  
Cliquer sur **🔄 Actualiser** après quelques secondes pour voir le résultat.

### Restauration (SSH uniquement)
```bash
sudo bash /opt/meca-auto/scripts/restore.sh
# ou restaurer un fichier spécifique :
sudo bash /opt/meca-auto/scripts/restore.sh mecaauto_2026-05-11_02-00-00.sql.gz
```

---

## Notifications email

Si un serveur SMTP est configuré, les notifications suivantes peuvent être activées :

| Événement | Destinataire |
|-----------|-------------|
| OR créé | Client (si email renseigné) |
| OR en cours | Client |
| OR clôturé | Client |
| Facture émise | Client (avec PDF joint) |
| Sauvegarde réussie/échouée | DDFPT |

---

## Questions fréquentes

**Je ne peux pas supprimer un client.**  
→ Le client a des OR associés. Supprimer d'abord les OR (DDFPT uniquement).

**L'élève ne voit pas son OR.**  
→ Vérifier que l'élève est bien assigné à l'OR (champ "Élève" dans la fiche OR).

**Le mot de passe d'un élève est perdu.**  
→ L'enseignant ou le DDFPT peut le réinitialiser dans Administration → Utilisateurs → ✏️.

**L'import CSV ne fonctionne pas.**  
→ Vérifier que le fichier est en UTF-8, avec les colonnes `nom` et `prénom` obligatoires.  
→ Télécharger le modèle fourni.

**La sauvegarde NAS échoue.**  
→ Vérifier que le NAS est accessible, que les credentials sont corrects, et que SMB v3 est activé dans DSM.  
→ Consulter le log : Administration → 🗄️ Sauvegardes → 📋 Voir le log.
