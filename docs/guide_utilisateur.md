# Guide utilisateur — MECA AUTO

Application de gestion d'atelier automobile pour lycée professionnel (section MVA).

---

## Connexion

Accéder à l'application via le navigateur (URL fournie par l'établissement).

| Champ | Valeur |
|-------|--------|
| Login | Fourni par l'administrateur |
| Mot de passe | Fourni à la création du compte |

> À la première connexion, vous serez invité à changer votre mot de passe (8 caractères minimum)
> et à définir une **question de sécurité** (menu Mon compte).

**Mot de passe oublié** : lien « Mot de passe oublié » de la page de connexion, si une question de sécurité
est définie. Sinon, le DDFPT réinitialise le mot de passe (voir ci-dessous) ; un mot de passe provisoire est
alors à changer à la connexion suivante.

La version installée du logiciel est indiquée en bas de chaque page. Les nouveautés sont décrites dans
`CHANGELOG.md`.

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
- **Changer le statut** : Ouvert → En cours → Terminé → Clôturé (voir « Workflow d'un OR »)
- **Clôturer** : choisir « Clôturé » dans *Modifier le statut*. Un état des lieux de sortie est proposé ;
  s'il n'a pas été fait (véhicule déjà reparti…), une confirmation permet de clôturer quand même.
- **Supprimer un OR** (même avec facture) : bouton 🗑️ sur la fiche OR
- **Générer une facture** : OR terminé → bouton « Créer la Facture » (la facture clôture l'OR)

#### Administration (`/settings/admin`)

**Onglet 👥 Utilisateurs**
- Créer / modifier / désactiver / supprimer des comptes
- **Réinitialiser un mot de passe** : ✏️ → champ jaune « 🔑 Réinitialiser le mot de passe »
  (mot de passe provisoire, à changer à la prochaine connexion ; le compte est aussi déverrouillé)
- Assigner un rôle et une classe aux élèves
- Importer des élèves via CSV (format Pronote compatible)

**Onglet 🏫 Établissement**
- Nom, adresse, téléphone, email, SIRET/UAI
- Ces informations apparaissent sur les factures PDF

**Onglet 💰 Tarification**
- Taux horaire (utilisé en mode horaire) et catalogue des **forfaits** proposés à la création des OR

**Onglet 🧴 Fournitures**
- Gérer le catalogue de fournitures avec prix unitaires
- Utilisées lors de la facturation des OR

**Onglet 📧 Email**
- Configurer le serveur SMTP pour les notifications, puis **Tester l'envoi**
- Gmail : `smtp.gmail.com`, port 587 (ou 465), adresse Gmail complète et **mot de passe d'application**
  (https://myaccount.google.com/apppasswords — validation en 2 étapes requise), expéditeur = même adresse
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
- Créer et modifier des OR (une confirmation est demandée si le CT ou l'assurance ne sont pas cochés)
- Choisir la **tarification** à la création : **Taux horaire** (temps véhicule × taux des paramètres) ou
  **Forfait** (forfait du catalogue, prix automatique). Aucun montant n'est saisi à la main.
- Affecter un élève à un OR
- Renseigner la **date de sortie prévue** du véhicule (alerte au tableau de bord le jour J et en cas de retard)
- Corriger le **véhicule** ou le **client** avec les boutons ✏️ de la fiche OR
- Saisir les interventions des élèves (heures pleines) et le **temps passé sur le véhicule** (Modifier)
- Faire les états des lieux d'entrée et de sortie (kilométrage facultatif)
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
- Accéder aux OR terminés → « Créer la Facture »
- **Mode horaire** : vérifier ou saisir le **temps passé sur le véhicule** (heures pleines) puis
  « 🔄 Mettre à jour le calcul ». Seul ce temps est facturé, pas la somme des heures des élèves.
- **Mode forfait** : le prix du forfait choisi sur l'OR (catalogue Administration → Tarification) est facturé.
  Si aucun forfait n'est choisi, la page de création de facture le signale (lien « Modifier l'OR »).
- Total = main-d'œuvre + fournitures + frais de dépollution (0 € pour les travaux internes).
- Le taux horaire est figé dans la facture à sa création.
- Si une facture affiche **« ⚠️ Montant à vérifier »**, compléter le temps véhicule et cliquer sur
  **Mettre à jour le montant** : l'écran, l'impression et le PDF affichent alors le même total.
- Imprimer la facture (« Aperçu / Imprimer »), marquer soldée, envoyer par mail

#### Fournitures
- Consulter le stock
- Saisir les fournitures utilisées dans un OR

---

### 🎓 Élève

#### Mes interventions
- Accéder aux OR sur lesquels vous êtes affecté
- Saisir le détail des interventions réalisées (fiche OR → « Ajouter une intervention ») :
  - Description du travail
  - Durée en **heures pleines** (1, 2, 3…)
  - Fourniture utilisée éventuelle
- Remplir l'état des lieux de sortie : votre nom est prérempli dans « Vérifications avant départ effectuées par »

#### Checklist
- Remplir la checklist de contrôle visuel pour un OR

> Les élèves ne peuvent pas créer ni modifier les OR, ni accéder aux données des autres élèves.

---

## Workflow d'un OR

```
1. CRÉATION
   Enseignant/DDFPT crée l'OR
   → Client + Véhicule + Élève assigné, date de sortie prévue (facultatif)
   → État des lieux d'entrée (+ inventaire signé avec le client)
   → Statut : Ouvert

2. TRAVAUX
   Élèves saisissent leurs interventions (heures pleines)
   → Statut : En cours

3. FIN DES TRAVAUX
   Enseignant vérifie, renseigne le temps passé sur le véhicule
   → Checklist de contrôle visuel, état des lieux de sortie (non bloquant)
   → Statut : Terminé            (= travaux finis, véhicule en attente du client)

4. FACTURATION / CLÔTURE
   Magasinier/DDFPT crée la facture  → l'OR passe automatiquement en Clôturé
   ou le DDFPT clôture à la main     (sans facture, ex. travaux internes)
   → Email envoyé au client (si configuré)
   → Statut : Clôturé            (= dossier fermé ; seuls DDFPT et magasinier peuvent encore le corriger)
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
→ L'enseignant ou le DDFPT peut le réinitialiser (page Élèves ✏️, ou Administration → Utilisateurs → ✏️).

**Un enseignant a oublié son mot de passe et n'a pas de question de sécurité.**  
→ Le DDFPT le réinitialise : Administration → Utilisateurs → ✏️ → champ « 🔑 Réinitialiser le mot de passe ».

**La facture affiche 0 € alors que le véhicule a été réparé (mode horaire).**  
→ Le temps passé sur le véhicule n'est pas renseigné : le saisir sur la page de la facture
(« Montant à vérifier ») ou dans Modifier l'OR.

**Je ne peux pas clôturer l'OR.**  
→ Le logiciel propose l'état des lieux de sortie ; le kilométrage et le nom sont facultatifs.
Le DDFPT peut aussi confirmer la clôture sans état des lieux.

**Les emails ne partent pas (Gmail).**  
→ Utiliser un mot de passe d'application Google, puis Administration → Email → Tester l'envoi.

**L'import CSV ne fonctionne pas.**  
→ Vérifier que le fichier est en UTF-8, avec les colonnes `nom` et `prénom` obligatoires.  
→ Télécharger le modèle fourni.

**La sauvegarde NAS échoue.**  
→ Vérifier que le NAS est accessible, que les credentials sont corrects, et que SMB v3 est activé dans DSM.  
→ Consulter le log : Administration → 🗄️ Sauvegardes → 📋 Voir le log.
