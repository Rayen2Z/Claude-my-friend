# Checklist — Prerequis et Hypotheses a Verifier Avant la Construction du Modele

## Architecture decidee

- **Observation** : snapshot fixe a M+3 (3 mois apres l'acquisition)
- **Prediction** : NBI cumule sur 5 ans, decompose en 4 familles de produits
- **Methode** : 4 sous-modeles XGBoost (Epargne, Investissements, Credit, Autre PNB) + taux de marge + taux de survie
- **Calibration** : lissage par deciles sur chaque sous-modele
- **CLV** : somme(NBI_produit x croissance^t x survie(t) / (1+r)^t) sur 5 ans

---

## PARTIE 1 — Informations indispensables

Ce sont des prerequis factuels. Si l'un d'eux n'est pas rempli, le modele tel que prevu n'est pas realisable.

### I1 — Les donnees par famille de produit existent et sont extractibles
Peut-on obtenir le NBI mensuel (ou les encours mensuels + taux de marge) ventile en 4 familles : Epargne bilan, Investissements financiers, Credit, Autre PNB ? Si ce n'est pas possible, toute l'architecture multi-modele tombe.

### I2 — Les 4 familles couvrent 100% du NBI
La somme des 4 familles doit etre egale au NBI total pour chaque client et chaque mois. S'il y a un ecart, il manque une categorie ou il y a un probleme de mapping dans les donnees.

### I3 — Profondeur d'historique disponible
Jusqu'ou remontent les donnees par produit ? Il faut au minimum 3-4 ans de NBI post-acquisition pour les cohortes les plus anciennes afin de calibrer une projection a 5 ans. Si les donnees commencent en 2023, on n'a que ~2,5 ans — insuffisant pour une cible a 5 ans.

### I4 — Taille des cohortes
Combien de nouveaux clients par trimestre ? On a besoin d'un volume suffisant pour entrainer 4 modeles separes. En dessous de ~500 clients par cohorte d'entrainement, les modeles ne seront pas stables.

### I5 — Taux de marge fournis par la Finance
Si les sous-modeles predisent des encours (et non du NBI directement), il faut les taux de marge t_s, t_i, t_c de la Finance pour convertir en NBI. Sont-ils disponibles ? A quelle frequence sont-ils mis a jour ?

### I6 — Snapshot equipements a M+3 disponible
Les fichiers d'equipements trimestriels permettent-ils de reconstituer les produits detenus par chaque client 3 mois apres son acquisition ?

### I7 — Donnees de depart (churn) disponibles
Peut-on identifier quels clients sont partis et quand ? On a besoin des taux de survie pour la formule CLV. Sans donnees de churn, la CLV se resume a une somme de NBI sans ajustement de retention.

---

## PARTIE 2 — Hypotheses a verifier

### H1 — Les 3 premiers mois de comportement contiennent un signal predictif reel
**Analyse** : Correler le NBI observe pendant les 3 premiers mois avec le NBI des mois restants (pas le NBI total — le NBI *restant*, pour eliminer le recouvrement mecanique). Faire cette analyse par famille de produit.

**Si invalide pour une famille** : Le NBI a 3 mois de cette famille est du bruit. Ne pas l'utiliser comme feature pour ce sous-modele — s'appuyer uniquement sur les equipements et les variables declaratives.

**Question cle** : La correlation decroit-elle quand l'horizon s'allonge ? Si r(3 mois, 1 an) = 0.7 mais r(3 mois, 3 ans) = 0.2, predire 5 ans a partir de 3 mois de donnees sera tres difficile.

### H2 — Les equipements a M+3 sont predictifs du NBI long terme
**Analyse** : Les clients avec plus de produits ou des produits specifiques (credit immo, assurance vie, domiciliation du salaire) generent-ils plus de NBI sur 3-5 ans ? L'equipement est-il un meilleur predicteur que le NBI a 3 mois, ou sont-ils complementaires ?

**Si l'equipement est le signal dominant** : Le modele a une base solide — l'equipement est stable et facile a observer.

**Si l'equipement est faible** : Le modele repose essentiellement sur la trajectoire NBI precoce, qui est plus bruitee.

### H3 — Les 4 familles ont des profils reellement differents selon les clients
**Analyse** : Si tous les clients ont a peu pres la meme repartition (30% epargne, 20% invest, etc.), alors 4 modeles sont inutiles — un seul modele sur le NBI total avec une repartition fixe ferait la meme chose. La decomposition n'a de valeur que si le mix produit varie significativement entre les clients.

**Si invalide** : Revenir a un modele unique sur le NBI total.

### H4 — Chaque famille a suffisamment d'observations non nulles pour etre modelisee
**Analyse** : Quel % de clients a un NBI = 0 dans chaque famille a 1 an ? A 3 ans ? Le credit et les investissements auront probablement beaucoup de zeros (la plupart des nouveaux clients n'ont pas de pret immobilier ou de placements dans les premieres annees).

**Si >60% de zeros dans une famille** : Utiliser un modele en deux etapes pour cette famille (1. classifieur zero/non-zero, 2. regresseur sur les non-zero).

**Si <20% de zeros** : Un regresseur standard suffit.

### H5 — L'equipement a M+3 est stable dans le temps (ou evolue de facon previsible)
**Analyse** : Comparer les produits detenus a 3 mois vs les produits detenus a 3-4 ans pour les cohortes anciennes. Si les clients acquierent la majorite de leurs produits dans les 3 premiers mois, notre snapshot capture bien la realite long terme. Si des produits majeurs (comme un credit immobilier) arrivent beaucoup plus tard, le snapshot a M+3 les rate et la projection NBI credit sur 5 ans sera systematiquement sous-estimee.

**Si invalide** : Les facteurs de croissance dans la formule CLV doivent implicitement tenir compte de l'enrichissement futur de l'equipement.

### H6 — Les taux de croissance par produit sont estimables et stables
**Analyse** : Pour les cohortes anciennes, calculer le NBI annuel par famille pour l'annee 1, 2, 3, 4. Chaque famille croit-elle a un taux a peu pres constant ? Ou est-ce erratique ?

**Si stable** : On peut utiliser des facteurs de croissance constants dans la formule CLV et projeter avec confiance les annees 4-5 meme si on n'observe que 3-4 ans.

**Si instable** : La projection a 5 ans a une incertitude large. Envisager des facteurs conditionnels (par segment, par niveau de NBI initial).

### H7 — La survie depend du mix produit
**Analyse** : Les clients avec plus de produits (ou des produits d'ancrage comme credit + domiciliation du salaire) ont-ils un taux de depart plus faible ? Comparer les courbes de survie (Kaplan-Meier) par profil d'equipement.

**Si valide** : Utiliser S(t | profil equipement) dans la formule CLV. Cela cree un effet compose : plus de produits = plus de NBI ET plus de retention.

**Si invalide** : Utiliser un taux de survie unique S(t) par segment.

### H8 — Le modele est stable entre les cohortes (pas de derive)
**Analyse** : La relation entre les features a M+3 et le NBI long terme tient-elle entre les differentes annees d'acquisition ? Si les clients acquis en 2021 se comportent tres differemment de ceux de 2024, le modele necessite un retraining frequent et on doit etre prudent sur une projection a 5 ans basee sur des patterns qui ne persistent peut-etre pas.

**Si stable** : Entrainer une fois, re-entrainer annuellement.

**Si derive detectee** : Re-entrainer trimestriellement, surponderer les cohortes recentes.

---

## Resume — Impact de chaque hypothese

| Hypothese | Si validee | Si invalidee |
|-----------|-----------|-------------|
| H1 | Le NBI a 3 mois est une feature cle | S'appuyer uniquement sur equipements + declaratif |
| H2 | L'equipement est un pilier du modele | Modele plus faible, incertitude plus grande |
| H3 | 4 sous-modeles justifies | Revenir a 1 modele sur le NBI total |
| H4 | Regression standard par famille | Modele en deux etapes (zero/non-zero) pour les familles creuses |
| H5 | Le snapshot M+3 est fiable pour projeter 5 ans | Les facteurs de croissance doivent compenser les produits futurs |
| H6 | Facteurs de croissance constants dans la CLV | Facteurs conditionnels ou variables dans le temps |
| H7 | S(t) conditionne au profil equipement | S(t) unique par segment |
| H8 | Entrainement annuel | Retraining trimestriel, ponderation temporelle |
