# Checklist — Prerequis et Hypotheses

## Architecture

- **Observation** : snapshot fixe a M+3 (3 mois apres l'acquisition)
- **5 sous-modeles** : Epargne (encours), Investissements (encours), Credit immobilier (encours), Autres credits (encours), Autre PNB (NBI direct)
- **Conversion** : encours x taux de marge = NBI (pour les 4 premiers modeles)
- **Calibration** : lissage par deciles — chaque client recoit la moyenne observee de son decile
- **CLV** : somme(NBI x croissance^t x survie(t) / (1+r)^t) sur 5 ans
- **Taux de marge** : fournis par la Finance (deja recus)

---

## PARTIE 1 — Informations indispensables

### I1 — Les donnees d'encours par famille sont extractibles
Peut-on obtenir les encours mensuels par client pour les 4 familles (epargne, investissements, credit immobilier, autres credits) ainsi que le NBI mensuel pour la 5e famille (autre PNB : commissions, assurances) ? Sans ces donnees, l'architecture a 5 sous-modeles n'est pas realisable.

### I2 — Les 5 familles couvrent 100% du NBI
La somme des NBI par famille (encours x marge pour les 4 premieres + NBI direct pour la 5e) doit correspondre au NBI total observe dans les fichiers PNB existants. S'il y a un ecart, il manque une categorie ou le mapping est incomplet.

### I3 — Profondeur d'historique disponible
Jusqu'ou remontent les donnees d'encours ? Il faut au minimum 3-4 ans de donnees post-acquisition pour les cohortes les plus anciennes afin de calibrer les facteurs de croissance et la projection a 5 ans.

### I4 — Taille des cohortes
Combien de nouveaux clients par trimestre ? On a besoin d'un volume suffisant pour entrainer 5 modeles separes. En dessous de ~500 clients par cohorte d'entrainement, les modeles ne seront pas stables.

### I5 — Taux de marge ~~a obtenir~~
~~Les taux de marge (t_s, t_i, t_m, t_c) doivent etre fournis par la Finance.~~ **FAIT** — les marges ont ete recues.

### I6 — Snapshot equipements a M+3 disponible
Les fichiers d'equipements trimestriels permettent-ils de reconstituer les produits detenus par chaque client 3 mois apres son acquisition ?

### I7 — Donnees de depart (churn) disponibles
Peut-on identifier quels clients sont partis et quand ? On a besoin des taux de survie pour la formule CLV. Sans donnees de churn, la CLV se resume a une somme de NBI sans ajustement de retention.

---

## PARTIE 2 — Hypotheses a verifier

### H1 — Les 3 premiers mois de comportement contiennent un signal predictif reel
**Analyse** : Correler le NBI observe pendant les 3 premiers mois avec le NBI des mois restants (pas le total — le *restant*). Faire par famille de produit et sur le total.

**Si invalide pour une famille** : Ne pas utiliser le NBI precoce comme feature pour ce sous-modele — s'appuyer uniquement sur les encours M+3, equipements et declaratif.

### H2 — Les equipements et encours a M+3 sont predictifs du NBI long terme
**Analyse** : Les clients avec plus de produits ou des encours plus eleves a M+3 generent-ils plus de NBI sur 3-5 ans ? L'encours initial est-il un bon predicteur de l'encours futur ?

**Si l'encours initial est le signal dominant** : Le modele a une base solide.

### H3 — Les 5 familles ont des profils reellement differents selon les clients
**Analyse** : Si tous les clients ont la meme repartition d'encours, 5 modeles sont redondants. Verifier que le mix produit varie significativement entre clients et entre segments.

**Si invalide** : Fusionner les familles trop similaires (ex : regrouper les deux types de credit).

### H4 — Chaque famille a suffisamment d'observations non nulles
**Analyse** : Quel % de clients a un encours = 0 dans chaque famille a M+3 ? Particulierement pour le credit immobilier (probablement tres creux — peu de nouveaux clients ont un pret immo a 3 mois).

**Si >60% de zeros** : Modele en deux etapes (1. classifieur zero/non-zero, 2. regresseur sur les non-zero).

### H5 — L'equipement et les encours a M+3 sont stables dans le temps
**Analyse** : Comparer les produits/encours a 3 mois vs a 3-4 ans pour les cohortes anciennes. Si les clients acquierent l'essentiel de leur equipement apres M+3 (ex : credit immo a M+18), le snapshot les rate.

**Si invalide** : Les facteurs de croissance doivent compenser l'enrichissement futur.

### H6 — Les taux de croissance par famille sont estimables et stables
**Analyse** : Pour les cohortes anciennes, calculer l'encours annuel par famille pour les annees 1, 2, 3, 4. Le taux de croissance est-il constant ? Different par segment ?

**Si stable** : Facteurs de croissance constants dans la CLV.
**Si instable** : Facteurs conditionnels par segment ou par niveau d'encours initial.

### H7 — La survie depend du mix produit
**Analyse** : Les clients avec un credit immobilier + domiciliation du salaire ont-ils un taux de depart plus faible ? Comparer les courbes de survie par profil d'equipement.

**Si valide** : Utiliser S(t | profil equipement) dans la CLV.
**Si invalide** : S(t) unique par segment.

### H8 — Le modele est stable entre les cohortes
**Analyse** : La relation entre les features a M+3 et les encours/NBI long terme est-elle stable entre 2021 et 2024 ?

**Si derive detectee** : Retraining frequent, surponderation des cohortes recentes.

---

## Resume

| Hypothese | Si validee | Si invalidee |
|-----------|-----------|-------------|
| H1 | NBI 3 mois est une feature cle | Pas de feature NBI precoce |
| H2 | Encours M+3 est un pilier du modele | Modele plus faible |
| H3 | 5 sous-modeles justifies | Fusionner les familles similaires |
| H4 | Regression standard | Modele deux etapes pour les familles creuses |
| H5 | Snapshot M+3 fiable pour 5 ans | Facteurs de croissance compensatoires |
| H6 | Croissance constante dans la CLV | Facteurs conditionnels |
| H7 | Survie conditionnelle au mix | Survie unique par segment |
| H8 | Retraining annuel | Retraining trimestriel |
