# Documentation Complete — Modele CLV Nouvelles Acquisitions

## Document de Reference

---

## 1. Objectif du Modele

Predire la **Customer Lifetime Value (CLV) sur 5 ans** des nouveaux clients d'une banque luxembourgeoise, a partir d'un **snapshot fixe pris 3 mois apres leur acquisition (M+3)**.

La prediction est decomposee en **5 familles de produits**, chacune dotee de son propre sous-modele XGBoost. Les 4 premiers sous-modeles predisent des **encours** (soldes en EUR), convertis en NBI via des taux de marge fournis par la Finance. Le 5e sous-modele predit du **NBI directement**.

---

## 2. Donnees

### 2.1 Fichiers sources

| Fichier | Contenu | Format |
|---------|---------|--------|
| Encours epargne | Solde mensuel d'epargne par client | client_id + colonnes mois (indices bancaires) |
| Encours investissements | AuM mensuel par client | idem |
| Encours credit immobilier | Encours prets immo mensuel par client | idem |
| Encours autres credits | Encours credits conso/revolving mensuel par client | idem |
| NBI autre | Commissions, assurances mensuelles par client | idem |
| Fichiers PNB (existants) | NBI total mensuel par client | idem — conserves pour validation et comme feature |
| Fichiers Stock (existants) | Acquisitions mensuelles (segment, profession, date_creation) | Jan 2023 a Mar 2026 |
| Fichiers Equipements (existants) | Snapshots trimestriels des produits detenus | client_id + colonnes produits |
| Taux de marge | t_s, t_i, t_m, t_c | Fournis par la Finance (deja recus) |

### 2.2 Encodage des mois bancaires

Janvier 1994 = indice 1. Formule : `indice = (annee - 1994) * 12 + mois`. Decembre 2025 = 384.

### 2.3 Coherence des donnees

La somme des 5 familles doit correspondre au NBI total observe :
```
encours_ep * t_s + encours_inv * t_i + encours_immo * t_m + encours_cr * t_c + nbi_autre ≈ nbi_total
```

---

## 3. Architecture

### 3.1 Les 5 sous-modeles

| # | Famille | Prediction | Unite | Conversion en NBI |
|---|---------|-----------|-------|--------------------|
| 1 | Epargne bilan | Solde moyen d'epargne | EUR (encours) | x t_s |
| 2 | Investissements financiers | Valeur des placements (AuM) | EUR (encours) | x t_i |
| 3 | Credit immobilier | Encours des prets immobiliers | EUR (encours) | x t_m |
| 4 | Autres credits | Encours credits conso, revolving | EUR (encours) | x t_c |
| 5 | Autre PNB | Commissions, frais carte, assurances | EUR (NBI) | Pas de conversion |

### 3.2 Pipeline complet

```
  Snapshot client a M+3
  (equipements, encours, NBI 3 mois, declaratif)
            |
  +---------+---------+---------+---------+
  v         v         v         v         v
+-------+ +-------+ +-------+ +-------+ +-------+
|XGBoost| |XGBoost| |XGBoost| |XGBoost| |XGBoost|
|Epargne| |Invest | |Cr.Immo| |Aut.Cr.| |Aut.PNB|
+---+---+ +---+---+ +---+---+ +---+---+ +---+---+
    |         |         |         |         |
  encours   encours   encours   encours    NBI
    |         |         |         |         |
  x t_s     x t_i     x t_m     x t_c     |
    |         |         |         |         |
    v         v         v         v         v
  NBI_ep    NBI_inv   NBI_immo  NBI_cr    NBI_aut
    |         |         |         |         |
+---v---+ +---v---+ +---v---+ +---v---+ +---v---+
|Decile | |Decile | |Decile | |Decile | |Decile |
|D[1-10]| |D[1-10]| |D[1-10]| |D[1-10]| |D[1-10]|
+---+---+ +---+---+ +---+---+ +---+---+ +---+---+
    |         |         |         |         |
    +----+----+----+----+----+----+         |
         |              |                   |
         v              v                   v
    NBI_predit = somme des 5 familles
                    |
          +---------v-----------+
          | CLV = somme(t=1..5) |
          | NBI x g^(t-1)       |
          |    / (1+r)^t        |
          +---------------------+
```

### 3.3 Pourquoi 5 familles ?

- Permet de savoir **d'ou vient la valeur** de chaque client (epargne vs credit vs invest)
- Strategies commerciales differenciees par famille
- Aligne avec l'approche BCEF (modele precedent de la banque)
- Le credit immobilier est separe des autres credits : dynamiques tres differentes (montants, duree, retention)

### 3.4 Pourquoi predire des encours et pas du NBI directement ?

- Les encours sont plus stables et moins bruites que le NBI mensuel
- La separation encours/marge permet de mettre a jour les marges sans re-entrainer le modele
- Exception : le modele 5 (autre PNB) predit du NBI car ces revenus ne sont pas lies a un encours

---

## 4. Features (Snapshot a M+3)

### 4.1 Variables declaratives

| Feature | Type | Description |
|---------|------|-------------|
| segment | categorielle | Mass Affluent / Mass Retail / Mass Retail with Potential |
| profession | categorielle | Jeune Actif / Salarie / Cadre / etc. |
| age | numerique | Age du client |
| genre | categorielle | Genre du client |
| commune | categorielle | Commune de residence |
| canal_acquisition | categorielle | Canal par lequel le client a ete acquis |
| trimestre_acquisition | categorielle | Q1/Q2/Q3/Q4 (saisonnalite) |

### 4.2 Equipements a M+3

| Feature | Type | Description |
|---------|------|-------------|
| n_produits_total | numerique | Nombre de produits distincts detenus |
| detail par produit | binaire/quantite | Compte courant, carte, livret, assurance vie, credit immo, etc. |

### 4.3 Comportemental (3 premiers mois)

| Feature | Type | Description |
|---------|------|-------------|
| nbi_total_3m | numerique | NBI total des 3 premiers mois |
| nbi_moyen_mensuel | numerique | NBI moyen mensuel sur 3 mois |
| tendance_nbi | numerique | Pente de la regression lineaire du NBI sur 3 mois |
| volatilite_nbi | numerique | Ecart-type du NBI mensuel sur 3 mois |
| nb_mois_actifs | numerique | Nombre de mois avec NBI > 0 |

### 4.4 Encours a M+3

| Feature | Type | Description |
|---------|------|-------------|
| encours_epargne_m3 | numerique | Encours epargne au mois 3 |
| encours_invest_m3 | numerique | Encours investissements au mois 3 |
| encours_immo_m3 | numerique | Encours credit immobilier au mois 3 |
| encours_autres_cr_m3 | numerique | Encours autres credits au mois 3 |

Tous les clients ont exactement **3 mois d'observation**. Pas de fenetre variable.

---

## 5. Variable Cible

### 5.1 Definition

Chaque sous-modele predit la **valeur cumulee** de sa famille sur toute la periode post-acquisition disponible (jusqu'a 5 ans) :

- Sous-modeles 1-4 : encours moyen cumule (en EUR)
- Sous-modele 5 : NBI cumule (en EUR)

### 5.2 Horizon de projection

La cible est la valeur observee sur la periode post-acquisition la plus longue disponible dans les donnees d'entrainement. Un client qui a 4 ans d'historique aura une cible sur 4 ans. Un client parti apres 2 ans aura des encours nuls pour les annees suivantes, ce qui reduit naturellement sa valeur cumulee.

---

## 6. Calibration par Deciles

### 6.1 Principe

1. Le XGBoost produit une **prediction brute** (encours ou NBI)
2. Cette prediction place le client dans un **decile D1 a D10** (base sur la distribution d'entrainement)
3. Le client recoit la **valeur moyenne reelle observee de ce decile**

### 6.2 Pourquoi

- Elimine les outliers : un client predit a 500 000 EUR d'encours recoit la moyenne du D10, pas 500 000
- Lisse les predictions : les deciles sont stables et interpretables
- Chaque sous-modele a sa **propre table de deciles** (5 tables au total)

### 6.3 Calcul des deciles

Les bornes et moyennes de deciles sont calculees sur les **predictions out-of-fold** (pas sur le jeu d'entrainement direct) pour eviter l'overfitting de la calibration.

---

## 7. Formule CLV

### 7.1 Calcul du NBI total

```
NBI_total = (encours_ep x t_s) + (encours_inv x t_i) + (encours_immo x t_m) + (encours_cr x t_c) + nbi_autre
```

Chaque composante est la valeur calibree par decile (pas la prediction brute).

### 7.2 Projection sur 5 ans

```
CLV = somme(t=1..5) [ NBI_total x g^(t-1) / (1+r)^t ]

    g = facteur de croissance annuel (calibre par famille sur donnees historiques)
    r = taux d'actualisation (cout du capital de la banque)
```

Pas de terme de survie S(t) explicite — l'attrition est implicitement capturee dans les valeurs cumulees (voir section 8).

### 7.3 Decomposition par famille

```
CLV_epargne = somme(t=1..5) [ NBI_epargne x g_ep^(t-1) / (1+r)^t ]
CLV_invest  = somme(t=1..5) [ NBI_invest  x g_inv^(t-1) / (1+r)^t ]
CLV_immo    = somme(t=1..5) [ NBI_immo    x g_immo^(t-1) / (1+r)^t ]
CLV_aut_cr  = somme(t=1..5) [ NBI_aut_cr  x g_cr^(t-1) / (1+r)^t ]
CLV_aut_pnb = somme(t=1..5) [ NBI_aut_pnb x g_pnb^(t-1) / (1+r)^t ]

CLV_total = CLV_epargne + CLV_invest + CLV_immo + CLV_aut_cr + CLV_aut_pnb
```

Cela permet d'identifier **d'ou vient la valeur** de chaque client et d'adapter les strategies commerciales.

---

## 8. Churn Implicite

Pas de modele de churn separe. L'attrition est **implicitement capturee** dans les donnees d'entrainement :

- Un client parti apres 2 ans aura des encours nuls pour les annees 3, 4 et 5
- Sa valeur cumulee sera donc naturellement plus basse
- Les moyennes par decile integrent ce taux d'attrition : un decile contenant des profils a fort risque de depart aura une moyenne plus basse
- La **tenure** (duree de presence) est fortement correlee avec la valeur cumulee et sert de proxy implicite de retention

---

## 9. Entrainement et Evaluation

### 9.1 Algorithme

**XGBoost** est l'algorithme retenu pour les 5 sous-modeles :
- Gestion native des valeurs manquantes (NaN)
- Aligne avec l'approche BCEF
- Performant sur les donnees tabulaires avec peu de features

### 9.2 Validation walk-forward temporelle

Entrainer sur les cohortes anciennes, valider sur les cohortes recentes. Pas de k-fold classique (risque de fuite temporelle).

| Iteration | Train | Test |
|-----------|-------|------|
| 1 | Cohortes 2023 | Cohorte Q1 2024 |
| 2 | Cohortes 2023 + Q1 2024 | Cohorte Q2 2024 |
| ... | ... | ... |

### 9.3 Metriques

| Metrique | Scope | Description |
|----------|-------|-------------|
| MAE | Par sous-modele | Erreur absolue moyenne |
| R² | Par sous-modele | Coefficient de determination |
| Spearman | Par sous-modele | Correlation de rang |
| MAE/R² agregat | NBI total | Somme des NBI par famille vs NBI total observe |
| Monotonie deciles | Par sous-modele | Les moyennes par decile doivent etre croissantes |
| Coherence | Global | Somme des NBI par famille ≈ NBI total (fichiers PNB) |

---

## 10. Cycle Operationnel

### 10.1 Scoring des nouvelles cohortes

A chaque fin de trimestre, les clients acquis 3 mois plus tot disposent de leur snapshot M+3. Le modele les score :

1. Collecter les features a M+3 (equipements, encours, NBI 3 mois, declaratif)
2. Appliquer les 5 sous-modeles XGBoost
3. Convertir les encours en NBI via les taux de marge
4. Affecter chaque client a un decile par sous-modele
5. Calculer la CLV totale et par famille

### 10.2 Re-entrainement

- **Frequence** : trimestrielle (a chaque nouvelle cohorte completee)
- **Strategie** : fenetre d'entrainement croissante (toutes les cohortes passees)
- **Comparaison** : valider que le nouveau modele est au moins aussi bon que le precedent sur les cohortes recentes

### 10.3 Contexte Luxembourg

- Banque basee au **Luxembourg**
- Clientele : residents luxembourgeois + **frontaliers** (France, Belgique, Allemagne)
- Enrichissement geographique : **STATEC** (pas INSEE)
- Segments : Mass Affluent, Mass Retail, Mass Retail with Potential
- Les frontaliers ont des profils de revenus et des besoins specifiques (salaires transfrontaliers)

---

## 11. Glossaire

| Terme | Definition |
|-------|-----------|
| **NBI / PNB** | Produit Net Bancaire — revenu net genere par un client pour la banque |
| **CLV** | Customer Lifetime Value — valeur totale actualisee d'un client sur 5 ans |
| **Encours** | Solde ou montant en cours d'un produit bancaire (epargne, credit, placement) |
| **AuM** | Assets under Management — valeur des actifs geres (investissements financiers) |
| **Marge** | Taux de marge applique aux encours pour obtenir le NBI : NBI = encours x marge |
| **Decile** | Groupe de 10% des clients classes par prediction du modele (D1 = plus bas, D10 = plus haut) |
| **Cohorte** | Groupe de clients acquis dans la meme periode |
| **Famille de produits** | Une des 5 categories : epargne, investissements, credit immo, autres credits, autre PNB |
| **M+3** | 3 mois apres l'acquisition du client — moment du snapshot |
| **Walk-forward** | Methode de validation temporelle (pas de donnees futures dans l'entrainement) |
| **Out-of-fold** | Predictions faites sur des donnees non vues pendant l'entrainement (pour calibrer les deciles) |
| **Frontalier** | Travailleur residant dans un pays limitrophe et travaillant au Luxembourg |
| **STATEC** | Institut national de la statistique du Luxembourg |
| **BCEF** | Modele precedent de la banque (entraine ~2022 sur 2017-2019), servant de reference |
| **Tenure** | Duree de presence du client — proxy implicite de churn dans ce modele |
