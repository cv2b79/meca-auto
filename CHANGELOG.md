# Journal des modifications — MEC AUTO

La version installée s'affiche en bas de chaque page (ex. « version d4257a5 ») et dans le bandeau
de la page **Administration**, qui la compare à GitHub.

---

## 10 novembre 2026 — Facturation et états des lieux

### Facturation au temps véhicule (`d4257a5`)
- **Nouveau champ sur l'OR : « ⏱️ Temps passé sur le véhicule »**, en heures pleines.
  En mode **horaire**, c'est **ce temps qui est facturé** : main-d'œuvre = temps véhicule × taux horaire.
- Les **heures saisies par les élèves** dans les interventions ne sont **plus facturées** : elles servent
  au suivi pédagogique (« Mes interventions », statistiques). Trois élèves qui travaillent 2 h ensemble
  sur une voiture = **2 h facturées**, et non 6 h.
- Le temps véhicule se saisit :
  - dans **Modifier** l'OR (enseignant, magasinier, DDFPT) ;
  - directement sur la page **Créer la facture**, avec le bouton « 🔄 Mettre à jour le calcul ».
    Un rappel indique le nombre d'élèves, les heures cumulées et le maximum par élève.
- S'il n'est pas renseigné, la page de création de facture affiche un avertissement (main-d'œuvre à 0 €).

### Heures pleines (`d4257a5`)
- Le champ **Heures** d'une intervention n'accepte plus que des heures entières.
  Une valeur décimale est arrondie à l'heure inférieure (2,5 → 2).

### Montant identique à l'écran, à l'impression et en PDF (`09e8c77`, `d4257a5`)
- **Bug corrigé** : en mode horaire, la facture enregistrait le champ « Montant » de l'OR (souvent vide → 0 €)
  au lieu du calcul ; en mode forfait, le PDF affichait heures × taux au lieu du forfait.
  Un **seul calcul** est désormais utilisé partout.
- Le **taux horaire est figé** dans la facture à sa création : changer le taux plus tard ne modifie plus
  les factures déjà émises.
- Si le montant enregistré d'une facture ne correspond plus au calcul (ancienne facture, OR modifié après coup),
  la page de la facture affiche **« ⚠️ Montant à vérifier »** et un bouton **Mettre à jour le montant**
  (magasinier, DDFPT). La modification est tracée dans le détail de la facture et dans les journaux.
- Travaux internes (« pas de facturation ») : facture à 0 €.
- **Bug corrigé** : l'aperçu/impression d'une facture au taux horaire plantait.

### États des lieux (`dd4b07a`, `79c8bc8`)
- **Kilométrage facultatif** : un compteur illisible ne bloque plus l'état des lieux de sortie.
- Le champ « Responsable » devient **« Vérifications avant départ effectuées par »** (sortie) /
  « État des lieux d'entrée effectué par » (entrée) : **facultatif**, **prérempli avec la personne connectée**
  (vide pour le DDFPT), avec suggestion des élèves de l'OR.
- **Bug corrigé** : rouvrir un état des lieux affichait un formulaire vide et effaçait carburant, dommages et
  observations à l'enregistrement. Les valeurs déjà saisies sont maintenant reprises.
- **Bug corrigé** : l'inventaire des objets de l'état des lieux d'entrée n'était pas enregistré.

### Création d'OR (`08805d1`)
- Si **CT** ou **assurance** ne sont pas cochés, une confirmation est demandée (« créer l'OR quand même ? »).
  Ce n'est pas bloquant.

### Divers (`0dd5be2`)
- `scripts/recalcul_factures.py` : simulation / correction en masse des montants de factures (SSH).
- `.gitignore` renforcé : sauvegardes, CSV, photos envoyées et archives ne peuvent pas partir sur GitHub
  (le dépôt est public ; les données réelles restent sur le RPi).

---

## 9 novembre 2026 — Clôture et corrections depuis la fiche OR (`5dca22e`)
- **Bug corrigé** : le DDFPT ne pouvait pas clôturer un OR (l'état des lieux de sortie était exigé mais réservé
  aux élèves et enseignants). Le DDFPT et le magasinier peuvent désormais remplir les états des lieux.
- Le DDFPT peut **clôturer sans état des lieux de sortie** après confirmation (tracé dans les journaux).
- Fiche OR : boutons **✏️** pour corriger le **véhicule** et le **client** (retour automatique sur l'OR).

## 4 novembre 2026 — Dates et emails
- **Date de sortie prévue** du véhicule (`5fc9b12`) : saisie à la création ou dans Modifier ; affichée sur la fiche,
  la liste des OR, l'impression et le PDF ; alertes au tableau de bord (jour J, retard).
- Fiche OR : « Créé le … » et « Clôturé le … ». Les heures s'affichent en heure française (elles avaient 1 à 2 h
  de décalage).
- **Emails** (`1cbeb3d`, `c3c2fce`, `4ea8d02`) : bouton de test dans Administration → Email ; SSL sur le port 465,
  STARTTLS sur 587, délai maximal de 20 s ; le vrai motif d'erreur Gmail est affiché.
  Avec Gmail, utiliser un **mot de passe d'application** (validation en 2 étapes requise).

## 2–3 novembre 2026
- Affichage de la **version** en pied de page et comparaison avec GitHub dans Administration (`7683b3b`).
- Archives hebdomadaires / mensuelles des journaux avec export CSV (`392bdef`).
- Correctifs de sécurité de la connexion et du mot de passe oublié, en-têtes de sécurité (`e40b03d`).
- Liste des OR : actions clôturer / supprimer pour le DDFPT (`f37372e`).

## 16 octobre 2026
- **Mise à jour automatique du RPi** depuis GitHub toutes les 15 min, avec retour à la version précédente si
  l'application ne répond plus (`91512d9`).
- **Mots de passe** (`e8b3bf3`) : le DDFPT peut réinitialiser le mot de passe de n'importe quel utilisateur
  (Administration → Utilisateurs → ✏️) ; la question de sécurité est demandée à la connexion tant qu'elle n'est
  pas définie ; 8 caractères minimum.
