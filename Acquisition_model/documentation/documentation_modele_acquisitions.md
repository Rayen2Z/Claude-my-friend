# Documentation Complete — Modele CLV Nouvelles Acquisitions

## Document de Reference ("Bible du Projet")

---

## 1. Objectif du Modele

Predire le **PNB (Produit Net Bancaire)** d'un nouveau client sur la periode allant de son acquisition jusqu'a la fin du 4e trimestre suivant (T+3), a partir de ses donnees disponibles au snapshot T+1 (fin du trimestre suivant l'acquisition).

Le modele se compose de deux sous-modeles :
1. **Modele PNB** (regression) : predit le PNB total genere par le client entre son mois d'acquisition et la fin de T+3 (10 a 12 mois selon la position dans le trimestre)
2. **Modele Churn** (classification, phase ulterieure) : predit la probabilite que le client quitte la banque

Ce document couvre le modele PNB. Le modele churn sera developpe dans un second temps.

---

## 2. Perimetre et Donnees Disponibles

### 2.1 Horizon temporel des donnees

| Donnee | Debut | Fin |
|--------|-------|-----|
| Fichiers clients (creation, segment, profession) | Janvier 2023 | Mars 2026 (fin Q1) |
| Fichiers PNB (mensuel, par client) | Janvier 2023 | Mars 2026 (fin Q1) |
| Fichiers equipements (produits souscrits) | Disponible sur la meme periode |

### 2.2 Fichiers sources (2 CSV par annee)

**Fichier 1 — Clients** : liste des clients acquis dans l'annee
- `client_id` : identifiant unique
- `date_creation` : date de creation du client dans la base
- `segment` : Mass Affluent, Mass Retail, Mass Retail with Potential
- `profession` : Jeune Actif, Salarie, Cadre, etc.
- Colonnes additionnelles (a confirmer) : nationalite, age, canal d'acquisition, etc.

**Fichier 2 — PNB** : PNB genere par les memes clients
- `client_id` : identifiant unique
- PNB mensuel (ou annuel, convertible en mensuel)
- Meme structure de segment/profession

**Fichier 3 — Equipements** : produits souscrits par les clients
- `client_id` : identifiant unique
- Produits/equipements souscrits dans la fenetre de 6 mois

### 2.3 Donnees fusionnees

Les fichiers de chaque annee sont fusionnes en un DataFrame unique :
```
client_id | date_creation | segment | profession | [autres colonnes]
          | pnb_m1 | pnb_m2 | ... | pnb_m12 | pnb_12m_total
          | [equipements / produits souscrits]
```

---

## 3. Architecture du Modele

### 3.1 Principe : cadence trimestrielle T/T+1/T+3

L'approche retenue est un **modele unique** entraine a cadence trimestrielle, avec une architecture de fenetres explicite :

- **T** = trimestre d'acquisition du client
- **T+1** = fin du trimestre suivant = moment du snapshot (features, equipements, PNB cumule)
- **T+3** = fin du 4e trimestre = fin de la fenetre cible (PNB total)

Parametres :
- **Frequence d'entrainement** : trimestrielle
- **Donnees d'entrainement** : toutes les cohortes dont la fenetre T+3 est entierement observable
- **Fenetre d'observation** : du mois d'acquisition a la fin de T+1 = **4 a 6 mois** (`n_mois_observation`)
- **Fenetre cible** : du mois d'acquisition a la fin de T+3 = **10 a 12 mois** (`n_mois_nbi`)
- **Cible** : `pnb_total` brut (somme des PNB mensuels de la fenetre cible), avec `n_mois_nbi` comme feature
- **Prediction** : appliquee aux clients acquis au trimestre T dont le snapshot T+1 vient d'etre disponible

### 3.2 Pourquoi T+1 comme fenetre d'observation ?

C'est le **meilleur compromis** entre :
- Trop tot (T seul, 1-3 mois) : pas assez de signal comportemental, predictions peu fiables
- Trop tard (T+2 ou plus) : la prediction n'est plus utile operationnellement

A T+1, on dispose de :
- **4 a 6 mois** de PNB mensuels (tendance, niveau, volatilite)
- **Snapshot equipements** au moment de la prediction (produits souscrits, flux)
- Indicateurs d'engagement (domiciliation salaire, prelevements)
- **Minimum garanti de 3 mois complets** meme pour les clients acquis en fin de trimestre

### 3.3 Variabilite des fenetres

La position du client dans le trimestre d'acquisition determine la longueur des fenetres :

| Mois dans T | n_mois_observation (T→fin T+1) | n_mois_nbi (T→fin T+3) |
|-------------|-------------------------------|------------------------|
| 1er mois (ex: janvier) | 6 | 12 |
| 2e mois (ex: fevrier) | 5 | 11 |
| 3e mois (ex: mars) | 4 | 10 |

La feature `n_mois_nbi` permet au modele de relativiser la duree variable de la cible.
La feature `n_mois_observation` capture la maturite des features comportementales.

### 3.4 Schema temporel

```
Cohorte Q1 2024 :

Client acquis en JANVIER 2024 :
|-------- T (Q1) --------|-------- T+1 (Q2) --------|-------- T+2 (Q3) --------|-------- T+3 (Q4) --------|
Jan                       Avr                         Jul                         Oct                    Dec
 |=== 6 mois observation ===|                                                                             |
 |================================= 12 mois NBI (pnb_total) =============================================|
       n_mois_observation = 6                                                        n_mois_nbi = 12

Client acquis en MARS 2024 :
|-------- T (Q1) --------|-------- T+1 (Q2) --------|-------- T+2 (Q3) --------|-------- T+3 (Q4) --------|
                     Mar  Avr                         Jul                         Oct                    Dec
                      |= 4m =|                                                                             |
                      |====================== 10 mois NBI (pnb_total) ====================================|
       n_mois_observation = 4                                                        n_mois_nbi = 10

Snapshot equipements : pris a fin T+1 (30 juin 2024) pour TOUTE la cohorte Q1 2024.
```

**Point important** : les PNB de la fenetre d'observation (`pnb_cumul_obs`) sont un sous-ensemble de la cible (`pnb_total`). Ce n'est **pas** du data leakage car :
- On utilise le PNB d'observation comme **signal d'entree** (niveau, tendance, volatilite)
- On predit le **PNB total** (qui inclut la partie observee + la partie future non observee)
- Le modele apprend a extrapoler le PNB restant a partir du comportement observe
- La variable `pnb_remaining = pnb_total - pnb_cumul_obs` est disponible pour tester une cible alternative (voir HA12)

---

## 4. Construction du Jeu d'Entrainement

### 4.1 Logique de construction

Pour chaque cohorte trimestrielle T :

1. Identifier tous les clients acquis pendant le trimestre T (`date_creation` dans T)
2. Calculer les fenetres : `end_t1` (fin T+1), `end_t3` (fin T+3) en indices mois bancaires
3. Calculer `n_mois_nbi` = nombre de mois du mois d'acquisition a fin T+3 (10, 11 ou 12)
4. Calculer `n_mois_observation` = nombre de mois du mois d'acquisition a fin T+1 (4, 5 ou 6)
5. Extraire les PNB mensuels `pnb_m1` a `pnb_m{n_mois_nbi}` depuis les fichiers PNB
6. Charger le snapshot equipements T+1 (fichier `YYYY QX.csv`)
7. Construire les features comportementales a partir de la fenetre d'observation
8. Calculer la cible : `pnb_total = sum(pnb_m1 ... pnb_m{n_mois_nbi})`

### 4.2 Variables derivees du preprocessing

| Variable | Formule | Description |
|----------|---------|-------------|
| `n_mois_nbi` | Mois acquisition -> fin T+3 | 10, 11 ou 12 |
| `n_mois_observation` | Mois acquisition -> fin T+1 | 4, 5 ou 6 |
| `pnb_cumul_obs` | sum(pnb_m1 ... pnb_m{n_mois_obs}) | PNB cumule sur la fenetre d'observation |
| `pnb_cumul_3m` | sum(pnb_m1 ... pnb_m3) | PNB des 3 premiers mois |
| `pnb_total` | sum(pnb_m1 ... pnb_m{n_mois_nbi}) | **CIBLE** du modele |
| `pnb_remaining` | pnb_total - pnb_cumul_obs | PNB non encore observe (pour HA12) |
| `pnb_mensuel_moyen` | pnb_total / n_mois_nbi | PNB mensuel moyen normalise (pour HA11) |

### 4.3 Eligibilite d'un client

Un client est eligible pour l'entrainement si sa fenetre T+3 est entierement observable dans les donnees PNB disponibles. Le filtre est : `end_t3 <= max_pnb_idx` (indice mois bancaire le plus recent disponible).

### 4.4 Cohortes utilisables pour l'entrainement

Avec des donnees de janvier 2023 a mars 2026, les cohortes suivantes ont une cible T+3 observable :

| Cohorte (T) | Observation (T+1) | Cible (T+3) | Utilisable ? |
|-------------|-------------------|-------------|-------------|
| Q1 2023 | Q2 2023 | Q4 2023 | OUI |
| Q2 2023 | Q3 2023 | Q1 2024 | OUI |
| Q3 2023 | Q4 2023 | Q2 2024 | OUI |
| Q4 2023 | Q1 2024 | Q3 2024 | OUI |
| Q1 2024 | Q2 2024 | Q4 2024 | OUI |
| Q2 2024 | Q3 2024 | Q1 2025 | OUI |
| Q3 2024 | Q4 2024 | Q2 2025 | OUI |
| Q4 2024 | Q1 2025 | Q3 2025 | OUI |
| Q1 2025 | Q2 2025 | Q4 2025 | OUI |
| Q2 2025 | Q3 2025 | Q1 2026 | OUI (juste) |
| Q3 2025 | Q4 2025 | Q2 2026 | NON (donnees jusqu'a Q1 2026) |

**Total** : ~10 cohortes trimestrielles utilisables (Q1 2023 a Q2 2025).

### 4.5 Decoupage Train / Test

**Approche temporelle** (recommandee) :
- **Train** : cohortes Q1 2023 a Q4 2024 (8 cohortes)
- **Test** : cohortes Q1 2025 a Q2 2025 (2 cohortes)

Cela simule la realite : on entraine sur le passe et on predit l'avenir.

### 4.6 Clients a predire (scoring)

Au trimestre T actuel (Q1 2026), on score les clients acquis au trimestre Q4 2025 :
- Leur snapshot T+1 (Q1 2026) vient d'etre disponible
- Leur PNB total (fin T+3 = Q3 2026) est inconnu — c'est exactement ce qu'on predit

---

## 5. Features (Variables d'Entree)

### 5.1 Features declaratives (disponibles au jour 0)

| Feature | Type | Description |
|---------|------|-------------|
| `segment` | categorielle | Mass Affluent / Mass Retail / Mass Retail with Potential |
| `profession` | categorielle | Jeune Actif / Salarie / Cadre / etc. |
| `n_mois_observation` | numerique | Nombre de mois d'observation (4, 5 ou 6) |
| `n_mois_nbi` | numerique | Nombre de mois dans la fenetre cible (10, 11 ou 12) |
| `trimestre_acquisition` | categorielle | Q1/Q2/Q3/Q4 (saisonnalite) |
| `annee_acquisition` | numerique | Annee d'acquisition |
| Colonnes additionnelles si disponibles : age, nationalite, canal, est_frontalier, etc. |

### 5.2 Features comportementales (fenetre d'observation T→T+1)

| Feature | Type | Description |
|---------|------|-------------|
| `pnb_m1`, `pnb_m2`, ..., `pnb_m6` | numerique | PNB mensuel (NaN si au-dela de n_mois_observation) |
| `pnb_cumul_3m` | numerique | PNB cumule des 3 premiers mois |
| `pnb_cumul_obs` | numerique | PNB cumule sur la fenetre d'observation (4-6 mois) |
| `obs_slope` | numerique | Pente de la regression lineaire du PNB sur la fenetre d'observation |
| `obs_volatility` | numerique | Ecart-type du PNB mensuel sur la fenetre d'observation |
| `obs_active_months` | numerique | Nombre de mois avec PNB > 0 dans la fenetre d'observation |

### 5.3 Features equipements (snapshot T+1)

Les equipements proviennent du snapshot trimestriel T+1. Chaque produit est represente par sa **quantite** (`qty_*`), pas un indicateur binaire.

| Feature | Type | Description |
|---------|------|-------------|
| `n_produits_total` | numerique | Nombre de produits distincts detenus (qty > 0) |
| `qty_*` | numerique | Quantite detenue pour chaque produit individuel |
| Colonnes de flux (si disponibles) | numerique | Encours, flux entrants/sortants au snapshot T+1 |

### 5.4 Features d'interaction (a construire lors de l'entrainement)

| Feature | Formule | Justification |
|---------|---------|---------------|
| `segment_x_produits` | segment encode * n_produits | Affluent avec beaucoup de produits = fort potentiel |
| `pnb_par_produit` | pnb_cumul_obs / n_produits | Efficacite de chaque produit |
| `tendance_x_equipement` | obs_slope * n_produits | Croissance combinee a l'equipement |

---

## 6. Variable Cible

### 6.1 Definition

```
pnb_total = SUM(pnb_mensuel) pour les mois 1 a n_mois_nbi apres le mois d'acquisition
```

C'est le PNB **total cumule** du client entre son mois d'acquisition et la fin du trimestre T+3. Il varie de 10 a 12 mois selon la position du client dans le trimestre d'acquisition.

La feature `n_mois_nbi` (10, 11 ou 12) est fournie au modele pour qu'il apprenne a relativiser la duree d'exposition variable.

### 6.2 Pourquoi T+3 (et non T+2 ou un horizon fixe) ?

- T+3 donne un horizon de **10-12 mois**, proche du cycle naturel d'une relation bancaire
- Les cotisations annuelles (carte, assurance) se manifestent sur ~12 mois
- Un credit immobilier met souvent 3-6 mois a generer du PNB — un horizon plus court serait insuffisant
- L'alignement trimestriel permet une operationnalisation directe (scoring tous les trimestres)
- Apres T+3, le client a suffisamment d'historique pour basculer vers le modele CLV etabli

### 6.3 Variable PNB mensuel moyen (pour analyses)

```
pnb_mensuel_moyen = pnb_total / n_mois_nbi
```

Cette variable n'est **pas** la cible du modele, mais elle est utilisee dans les hypotheses (HA2, HA7, HA8, HA11) pour neutraliser l'effet de la duree variable lors des comparaisons entre groupes.

### 6.4 Alternative : predire le PNB restant (`pnb_remaining`)

```
pnb_remaining = pnb_total - pnb_cumul_obs
```

Au lieu de predire `pnb_total` (qui inclut le PNB deja observe), on pourrait predire uniquement la partie non observee (`pnb_remaining`), puis l'additionner au PNB deja observe.

**Avantage** : isole le vrai pouvoir predictif du modele, evite que la correlation mecanique entre `pnb_cumul_obs` et `pnb_total` gonfle artificiellement les metriques
**Inconvenient** : le modele doit predire une quantite plus incertaine (moins de variance expliquee mecaniquement)

**Decision** : les deux approches seront testees dans HA12. La cible par defaut reste `pnb_total` brut.

---

## 7. Entrainement du Modele

### 7.1 Architecture

```python
GradientBoostingRegressor(
    n_estimators=300,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    min_samples_leaf=20,
    loss='huber',       # robuste aux outliers PNB
    random_state=42,
)
```

### 7.2 Cycle d'entrainement trimestriel

A chaque debut de trimestre T_current :

1. **Collecter** toutes les cohortes dont la fenetre T+3 est entierement observable
2. **Construire** les features (fenetre d'observation T→T+1) et la cible (fenetre T→T+3)
3. **Entrainer** le modele sur les cohortes les plus anciennes
4. **Valider** sur les cohortes les plus recentes
5. **Scorer** les clients de la cohorte dont le snapshot T+1 vient d'etre disponible

### 7.3 Exemple concret : entrainement au Q1 2026

```
TRAIN : cohortes Q1 2023 -> Q4 2024  (8 cohortes, fenetre T+3 complete)
TEST  : cohortes Q1 2025 -> Q2 2025  (2 cohortes, fenetre T+3 complete)
SCORE : cohorte Q4 2025              (snapshot T+1 = Q1 2026 disponible, PNB total inconnu)
```

---

## 8. Evaluation et Metriques

### 8.1 Metriques de regression (modele PNB)

| Metrique | Description | Seuil acceptable |
|----------|-------------|-----------------|
| MAE | Erreur absolue moyenne (EUR) | < 20% du PNB moyen |
| RMSE | Racine de l'erreur quadratique moyenne | Pour comparaison |
| R2 | Coefficient de determination | > 0.30 (donnees limitees) |
| MAPE | Erreur pourcentage moyenne | < 30% |

### 8.2 Validation croisee temporelle

Pas de k-fold classique (risque de leakage temporel). Utiliser une **validation walk-forward** :

| Iteration | Train | Test |
|-----------|-------|------|
| 1 | Q1-Q2 2023 | Q3 2023 |
| 2 | Q1-Q3 2023 | Q4 2023 |
| 3 | Q1-Q4 2023 | Q1 2024 |
| ... | ... | ... |
| 7 | Q1 2023 - Q2 2024 | Q3 2024 |

Cela donne 7 iterations de validation avec des performances stables attendues.

---

## 9. Integration CLV

### 9.1 Formule CLV pour nouveaux clients

```
CLV_nouveau = PNB_predit_12m * S(1) / (1.05)^1
            + PNB_predit_12m * croissance * S(2) / (1.05)^2
            + PNB_predit_12m * croissance^2 * S(3) / (1.05)^3

Ou :
  PNB_predit_12m = sortie du modele de regression
  S(t) = probabilite de survie a l'annee t (modele churn, phase ulterieure)
  croissance = facteur de croissance PNB annuel (a calibrer, ~1.10)
  1.05 = taux d'actualisation annuel
```

### 9.2 Transition vers le modele etabli

- **Mois 0-12** : modele nouvelles acquisitions (ce modele)
- **Mois 12+** : le client a 4 trimestres de donnees -> bascule vers le modele CLV etabli
- Pas de fenetre de lissage necessaire car la prediction est faite une seule fois (au mois 3-6) et reste valide jusqu'au mois 12

---

## 10. Limites et Points d'Attention

### 10.1 Biais de la fenetre variable

Les clients avec `n_mois_observation = 6` ont plus d'information que ceux avec `n_mois_observation = 4`. De meme, les clients avec `n_mois_nbi = 12` ont une cible sur un horizon plus long que ceux avec `n_mois_nbi = 10`. Le modele doit apprendre a utiliser ces features pour moduler ses predictions. Les hypotheses HA11 et HA13 valident la robustesse du modele face a cette variabilite.

### 10.2 Saisonnalite

Un client acquis en janvier (debut d'annee, bonnes resolutions, epargne) peut avoir un profil PNB different d'un client acquis en septembre (rentree, credit scolaire). La feature `trimestre_acquisition` capture ce signal.

### 10.3 Representativite des cohortes

Les cohortes 2023 peuvent ne pas etre representatives de 2025 (changement de strategie commerciale, nouveaux produits, contexte economique). Le re-entrainement trimestriel attenme ce risque.

### 10.4 PNB negatif

Certains clients peuvent avoir un PNB negatif (couts > revenus pour la banque). Le modele Huber gere bien ces cas mais il faut les analyser dans l'exploration.

### 10.5 Clients frontaliers

Au Luxembourg, les frontaliers representent une part significative des nouvelles acquisitions. Leur profil PNB est souvent different (salaires plus eleves, besoins transfrontaliers). Si la variable est disponible, c'est une feature importante.

---

## 11. Calendrier et Prochaines Etapes

| Etape | Description | Statut |
|-------|-------------|--------|
| 1 | Fusionner les CSV clients et PNB par annee | A faire |
| 2 | Construire le DataFrame unifie avec features et cible | A faire |
| 3 | Analyse exploratoire et validation des hypotheses | A faire |
| 4 | Entrainer le modele PNB V0 | A faire |
| 5 | Evaluer et iterer | A faire |
| 6 | Developper le modele churn | Phase ulterieure |
| 7 | Integrer dans le pipeline CLV | Phase ulterieure |

---

## 12. Glossaire

| Terme | Definition |
|-------|-----------|
| **PNB** | Produit Net Bancaire — revenu net genere par un client pour la banque |
| **CLV** | Customer Lifetime Value — valeur totale actualisee d'un client sur un horizon donne |
| **Cohorte** | Groupe de clients acquis dans la meme periode (trimestre) |
| **Feature** | Variable d'entree du modele (predicteur) |
| **Cible / Target** | Variable a predire (`pnb_total`, PNB sur la fenetre T→T+3) |
| **Segment** | Classification client : Mass Affluent, Mass Retail, Mass Retail with Potential |
| **Equipement** | Produit ou service souscrit par le client |
| **Domiciliation** | Fait de faire verser son salaire sur le compte de la banque |
| **Frontalier** | Travailleur residant dans un pays limitrophe et travaillant au Luxembourg |
| **STATEC** | Institut national de la statistique du Luxembourg |
| **Walk-forward** | Methode de validation temporelle (pas de futur dans le train) |
| **Huber loss** | Fonction de perte robuste aux valeurs aberrantes |
| **T/T+1/T+3** | Architecture de fenetrage trimestriel : T = acquisition, T+1 = observation, T+3 = cible |
| **n_mois_nbi** | Nombre de mois dans la fenetre cible (10, 11 ou 12 selon la position dans le trimestre) |
| **n_mois_observation** | Nombre de mois dans la fenetre d'observation (4, 5 ou 6) |
| **pnb_remaining** | PNB non observe = pnb_total - pnb_cumul_obs (cible alternative pour HA12) |
| **pnb_mensuel_moyen** | PNB total / n_mois_nbi (PNB normalise par duree, pour analyses) |
| **Plancher mecanique** | Correlation artificielle entre pnb_cumul_obs et pnb_total due a leur overlap |
