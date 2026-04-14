# Documentation Complete — Modele CLV Nouvelles Acquisitions

## Document de Reference ("Bible du Projet")

---

## 1. Objectif du Modele

Predire le **PNB (Produit Net Bancaire) a 12 mois** d'un nouveau client a partir de ses donnees disponibles dans les **3 a 6 premiers mois** suivant son entree en relation avec la banque.

Le modele se compose de deux sous-modeles :
1. **Modele PNB** (regression) : predit le PNB total genere par le client sur ses 12 premiers mois
2. **Modele Churn** (classification, phase ulterieure) : predit la probabilite que le client quitte la banque dans les 12 premiers mois

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

### 3.1 Principe : un seul modele, entraine trimestriellement

Apres discussion, l'approche retenue est un **modele unique** (pas de multi-phase) entraine chaque trimestre :

- **Frequence d'entrainement** : trimestrielle (chaque debut de trimestre T)
- **Donnees d'entrainement** : tous les clients historiques ayant au moins 12 mois d'anciennete (pour observer la cible PNB 12 mois)
- **Fenetre de features** : les 3 a 6 premiers mois de chaque client (donnees comportementales precoces)
- **Cible** : PNB total cumule sur les 12 premiers mois (`pnb_12m_total`)
- **Prediction** : appliquee aux nouveaux clients ayant entre 3 et 6 mois d'anciennete

### 3.2 Pourquoi 3 a 6 mois ?

C'est le **meilleur compromis** entre :
- Trop tot (0-2 mois) : pas assez de signal comportemental, predictions peu fiables
- Trop tard (9-12 mois) : la prediction n'est plus utile car le client a deja presque accumule ses 12 mois

A 3-6 mois, on dispose de :
- Premiers PNB mensuels (tendance, niveau, volatilite)
- Produits souscrits/actives (equipements)
- Indicateurs d'engagement (domiciliation salaire, carte activee, prelevements)

### 3.3 Schema temporel

```
Client rejoint en Q2 2024 (ex: 15 avril 2024)

|-- Jour 0 --|------- Features (3-6 mois) -------|----------- Observation cible ------------|
   15 avr                                  15 oct                                    15 avr 2025
   2024                                    2024                                       2025
                                                                                        
   [    Mois 1-6 : donnees d'entree     ]  [     Mois 7-12 : on observe le reste     ]
                                                                                        
   PNB_m1 ... PNB_m6 = FEATURES              PNB_m7 ... PNB_m12 = partie de la CIBLE
                                                                                        
   CIBLE = PNB_m1 + PNB_m2 + ... + PNB_m12  (PNB total 12 mois)
```

**Point important** : les features (mois 1-6) sont un sous-ensemble de la cible (mois 1-12). Ce n'est **pas** du data leakage car :
- On utilise les mois 1-6 comme **signal d'entree** (niveau, tendance, produits)
- On predit le **total sur 12 mois** (qui inclut les mois 1-6 deja observes + les mois 7-12 inconnus)
- Le modele apprend a extrapoler les mois 7-12 a partir du comportement des mois 1-6

---

## 4. Construction du Jeu d'Entrainement

### 4.1 Logique de construction

Pour chaque client acquis :

1. Identifier la **date de creation** (`date_creation`)
2. Determiner le **trimestre d'acquisition** : Q dans lequel tombe la date_creation
3. Extraire les **features** : PNB mensuel des mois 1 a 6, equipements, segment, profession
4. Calculer la **cible** : PNB cumule des mois 1 a 12 (`pnb_12m_total`)

### 4.2 Fenetre variable selon la position dans le trimestre

Un client qui rejoint le 1er janvier a 6 mois complets de donnees au 30 juin.
Un client qui rejoint le 31 mars a 3 mois complets de donnees au 30 juin.

Pour gerer cette variabilite :
- **Feature fixe** : `mois_anciennete` = nombre de mois complets depuis la date_creation (entre 3 et 6)
- Les PNB mensuels au-dela de l'anciennete sont remplis a 0 ou NaN (le modele apprend a gerer)

### 4.3 Cohortes utilisables pour l'entrainement

Avec des donnees de janvier 2023 a mars 2026, les cohortes suivantes ont une cible 12 mois observable :

| Trimestre d'acquisition | Date creation | PNB 12 mois observable jusqu'a | Utilisable ? |
|------------------------|---------------|--------------------------------|-------------|
| Q1 2023 (jan-mar) | Jan-Mar 2023 | Jan-Mar 2024 | OUI |
| Q2 2023 (avr-jun) | Avr-Jun 2023 | Avr-Jun 2024 | OUI |
| Q3 2023 (jul-sep) | Jul-Sep 2023 | Jul-Sep 2024 | OUI |
| Q4 2023 (oct-dec) | Oct-Dec 2023 | Oct-Dec 2024 | OUI |
| Q1 2024 (jan-mar) | Jan-Mar 2024 | Jan-Mar 2025 | OUI |
| Q2 2024 (avr-jun) | Avr-Jun 2024 | Avr-Jun 2025 | OUI |
| Q3 2024 (jul-sep) | Jul-Sep 2024 | Jul-Sep 2025 | OUI |
| Q4 2024 (oct-dec) | Oct-Dec 2024 | Oct-Dec 2025 | OUI |
| Q1 2025 (jan-mar) | Jan-Mar 2025 | Jan-Mar 2026 | OUI (juste) |
| Q2 2025 (avr-jun) | Avr-Jun 2025 | Avr-Jun 2026 | NON (donnees jusqu'a mars 2026 seulement) |
| Q3 2025 | - | - | NON |
| Q4 2025 | - | - | NON |

**Total** : 9 cohortes trimestrielles utilisables (Q1 2023 a Q1 2025).

### 4.4 Decoupage Train / Test

**Approche temporelle** (recommandee) :
- **Train** : cohortes Q1 2023 a Q3 2024 (7 cohortes)
- **Test** : cohortes Q4 2024 a Q1 2025 (2 cohortes)

Cela simule la realite : on entraine sur le passe et on predit l'avenir.

### 4.5 Clients a predire (scoring)

Au trimestre T actuel (Q1 2026), on score les clients qui ont entre 3 et 6 mois d'anciennete :
- Clients acquis entre **Q3 2025** (6 mois d'anciennete) et **Q4 2025** (3 mois d'anciennete)
- Ces clients n'ont PAS leur PNB 12 mois — c'est exactement ce qu'on predit

---

## 5. Features (Variables d'Entree)

### 5.1 Features declaratives (disponibles au jour 0)

| Feature | Type | Description |
|---------|------|-------------|
| `segment` | categorielle | Mass Affluent / Mass Retail / Mass Retail with Potential |
| `profession` | categorielle | Jeune Actif / Salarie / Cadre / etc. |
| `mois_anciennete` | numerique | Nombre de mois complets depuis date_creation (3-6) |
| `trimestre_acquisition` | categorielle | Q1/Q2/Q3/Q4 (saisonnalite) |
| Colonnes additionnelles si disponibles : age, nationalite, canal, est_frontalier, etc. |

### 5.2 Features comportementales (premiers 3-6 mois)

| Feature | Type | Description |
|---------|------|-------------|
| `pnb_m1`, `pnb_m2`, ..., `pnb_m6` | numerique | PNB mensuel (0 si pas encore atteint) |
| `pnb_cumul_3m` | numerique | PNB cumule des 3 premiers mois |
| `pnb_cumul_6m` | numerique | PNB cumule des 6 premiers mois (0 si < 6 mois) |
| `pnb_moyen_mensuel` | numerique | PNB moyen par mois actif |
| `pnb_tendance` | numerique | Pente de la regression lineaire du PNB mensuel |
| `pnb_volatilite` | numerique | Ecart-type du PNB mensuel |
| `pnb_mois_max` | numerique | PNB du meilleur mois |
| `pnb_mois_positifs` | numerique | Nombre de mois avec PNB > 0 |
| `log_pnb_cumul` | numerique | log1p(pnb_cumul) — pour stabiliser la distribution |
| `ratio_pnb_m3_vs_m1` | numerique | Evolution du PNB entre mois 1 et mois 3 |

### 5.3 Features equipements (produits souscrits)

| Feature | Type | Description |
|---------|------|-------------|
| `n_produits_total` | numerique | Nombre total de produits souscrits |
| `has_compte_courant` | binaire | Compte courant |
| `has_carte_bancaire` | binaire | Carte bancaire |
| `has_epargne` | binaire | Produit d'epargne (livret, assurance-vie) |
| `has_credit` | binaire | Credit immobilier ou consommation |
| `has_assurance` | binaire | Assurance (MRH, auto, prevoyance) |
| `n_familles_produits` | numerique | Nombre de familles de produits couvertes (0-4) |
| `has_package_complet` | binaire | 1 si >= 3 familles couvertes |
| `a_domiciliation_salaire` | binaire | Salaire domicilie |
| `a_prelevement` | binaire | Au moins un prelevement automatique |
| `vitesse_equipement` | numerique | Nombre de produits souscrits dans le 1er mois |

### 5.4 Features d'interaction

| Feature | Formule | Justification |
|---------|---------|---------------|
| `segment_x_produits` | segment encode * n_produits | Affluent avec beaucoup de produits = fort potentiel |
| `pnb_par_produit` | pnb_cumul / n_produits | Efficacite de chaque produit |
| `tendance_x_equipement` | pnb_tendance * n_produits | Croissance combinee a l'equipement |

---

## 6. Variable Cible

### 6.1 Definition

```
pnb_12m_total = SUM(pnb_mensuel) pour les mois 1 a 12 apres date_creation
```

C'est le PNB **total cumule** sur les 12 premiers mois du client. Il inclut les mois 1-6 (deja observes et utilises comme features) et les mois 7-12 (non observes, a predire implicitement).

### 6.2 Pourquoi 12 mois et pas 6 ?

- 12 mois est le cycle naturel d'une relation bancaire
- Les cotisations annuelles (carte, assurance) se manifestent sur 12 mois
- Un credit immobilier met souvent 3-6 mois a generer du PNB — 6 mois est trop court
- La CLV existante est sur un horizon de 3 ans — 12 mois est le premier palier naturel
- Apres 12 mois, le client bascule vers le modele CLV etabli

### 6.3 Alternative : predire uniquement les mois 7-12

Au lieu de predire le total 12 mois, on pourrait predire uniquement le PNB des mois 7-12 (la partie non observee), puis l'additionner au PNB deja observe des mois 1-6.

**Avantage** : isole mieux la capacite predictive du modele
**Inconvenient** : introduce une discontinuite entre les clients a 3 mois (qui ont moins de PNB observe) et ceux a 6 mois

**Recommandation** : tester les deux approches et comparer les MAE. Si la prediction du total 12 mois est meilleure (grace a la correlation entre mois 1-6 et mois 7-12), la garder.

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

A chaque debut de trimestre T :

1. **Collecter** toutes les cohortes historiques avec 12 mois de recul
2. **Construire** les features (mois 1-6) et la cible (mois 1-12)
3. **Entrainer** le modele sur les cohortes les plus anciennes
4. **Valider** sur la cohorte la plus recente
5. **Scorer** les nouveaux clients ayant 3-6 mois d'anciennete

### 7.3 Exemple concret : entrainement au Q1 2026

```
TRAIN : clients acquis Q1 2023 -> Q3 2024  (7 cohortes, ~12+ mois de recul)
TEST  : clients acquis Q4 2024 -> Q1 2025  (2 cohortes, 12 mois de recul)
SCORE : clients acquis Q3 2025 -> Q4 2025  (3-6 mois d'anciennete, PNB 12m inconnu)
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

Les clients a 6 mois ont plus d'information que ceux a 3 mois. Le modele doit apprendre que `mois_anciennete` est une feature clef qui module l'importance des PNB mensuels.

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
| **Cible / Target** | Variable a predire (PNB 12 mois) |
| **Segment** | Classification client : Mass Affluent, Mass Retail, Mass Retail with Potential |
| **Equipement** | Produit ou service souscrit par le client |
| **Domiciliation** | Fait de faire verser son salaire sur le compte de la banque |
| **Frontalier** | Travailleur residant dans un pays limitrophe et travaillant au Luxembourg |
| **STATEC** | Institut national de la statistique du Luxembourg |
| **Walk-forward** | Methode de validation temporelle (pas de futur dans le train) |
| **Huber loss** | Fonction de perte robuste aux valeurs aberrantes |
