# Architecture du Modele CLV — Nouvelles Acquisitions

## Design final

Cinq sous-modeles predisent les **encours ou le NBI** de chaque famille de produit a partir d'un snapshot pris **3 mois apres l'acquisition** du client. Les predictions d'encours sont converties en NBI via les taux de marge fournis par la Finance. Chaque client est ensuite affecte a un **decile** par sous-modele, et la prediction finale est la **valeur moyenne observee de ce decile**. Le NBI total projete sur 5 ans donne la CLV.

---

## 1. Les 5 sous-modeles

| # | Famille | Ce que le modele predit | Unite | Conversion en NBI |
|---|---------|------------------------|-------|-------------------|
| 1 | Epargne bilan | Solde moyen des comptes d'epargne | EUR (encours) | x t_s (marge epargne) |
| 2 | Investissements financiers | Valeur des placements (AuM) | EUR (encours) | x t_i (marge investissements) |
| 3 | Credit immobilier | Encours des prets immobiliers | EUR (encours) | x t_m (marge credit immo) |
| 4 | Autres credits | Encours des credits conso, revolving, etc. | EUR (encours) | x t_c (marge autres credits) |
| 5 | Autre PNB | Commissions, frais de carte, assurances | EUR (NBI directement) | Pas de conversion |

Les taux de marge (t_s, t_i, t_m, t_c) sont fournis par la Finance (deja recus).

---

## 2. Pipeline complet

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
          | NBI x g^t x S(t)   |
          |    / (1+r)^t        |
          +---------------------+
```

---

## 3. Donnees necessaires

### 3.1 Extraction a faire

| Fichier | Contenu | Format |
|---------|---------|--------|
| Encours epargne | Solde mensuel par client | client_id + colonnes mois (indices bancaires) |
| Encours investissements | AuM mensuel par client | idem |
| Encours credit immobilier | Encours mensuel par client | idem |
| Encours autres credits | Encours mensuel par client | idem |
| NBI autre | Commissions, assurances mensuelles par client | idem |
| Equipements (deja disponibles) | Produits detenus par trimestre | client_id + colonnes produits |
| Stock (deja disponible) | Fichiers d'acquisition par mois | client_id + declaratif |

### 3.2 Donnees deja disponibles

- **Fichiers PNB** : NBI total mensuel par client (conserve comme feature potentielle et pour validation)
- **Taux de marge** : t_s, t_i, t_m, t_c fournis par la Finance (deja recus)
- **Fichiers Stock** : donnees d'acquisition (segment, profession, etc.)
- **Fichiers Equipements** : snapshots trimestriels

### 3.3 Le NBI des 3 premiers mois comme feature

Le NBI total observe pendant les 3 premiers mois (issu des fichiers PNB existants) est conserve comme **feature candidate**. Si l'hypothese H1 de la checklist confirme que le NBI precoce a un pouvoir predictif, il sera inclus dans le jeu de features de chaque sous-modele.

---

## 4. Features (snapshot a M+3)

| Famille | Features |
|---------|----------|
| Declaratif | segment, profession, age, genre, commune, canal_acquisition |
| Equipements (M+3) | n_produits_total, detail par type de produit (binaire ou quantite) |
| Comportemental (3 mois) | nbi_total_3m, nbi_moyen_mensuel, tendance_nbi (pente), volatilite_nbi, nb_mois_actifs |
| Encours (M+3) | encours_epargne_m3, encours_invest_m3, encours_immo_m3, encours_autres_cr_m3 |

**Pas de features de fenetrage variable** : tous les clients ont exactement 3 mois d'observation.

---

## 5. Calibration par deciles

### Principe

1. Le XGBoost produit une **prediction brute** (encours ou NBI)
2. Cette prediction place le client dans un **decile D1 a D10** (base sur la distribution d'entrainement)
3. Le client recoit la **valeur moyenne reelle observee de ce decile**

### Pourquoi

- Elimine les outliers : un client predit a 500 000 EUR d'encours epargne recoit la moyenne du D10, pas 500 000
- Lisse les predictions : les deciles sont stables et interpretables
- Chaque sous-modele a sa **propre table de deciles**

### Calcul des deciles

Les bornes et moyennes de deciles sont calculees sur les **predictions out-of-fold** (pas sur le jeu d'entrainement direct) pour eviter l'overfitting de la calibration.

---

## 6. Churn et survie

Pas de modele de churn separe. Le churn est **implicitement capture** dans les donnees d'entrainement : un client parti apres 2 ans aura des encours nuls pour les annees 3-5. La valeur cumulee sur 5 ans reflete donc naturellement l'attrition. Les moyennes par decile integrent cette attrition — un decile qui contient des profils a fort risque de depart aura une moyenne plus basse car elle inclut les clients partis.

La **tenure** (duree de presence) sera fortement correlee avec la valeur cumulee et servira implicitement de proxy de retention.

---

## 7. Formule CLV

```
Pour chaque famille f parmi {epargne, invest, immo, autres_cr, autre_pnb} :

    NBI_f = encours_predit_calibre_f x marge_f     (pour f = 1..4)
    NBI_f = nbi_predit_calibre_f                    (pour f = 5)

NBI_total = somme(NBI_f)

CLV = somme(t=1..5) [ NBI_total x g^(t-1) / (1+r)^t ]

    g = facteur de croissance annuel (calibre par famille sur donnees historiques)
    r = taux d'actualisation
```

Note : pas de terme S(t) explicite — la survie est deja integree dans les valeurs cumulees predites et lissees par les deciles.

### Decomposition par produit

Chaque composante de la CLV est calculable separement :

```
CLV_epargne = somme(t=1..5) [ NBI_epargne x g_ep^(t-1) x S(t) / (1+r)^t ]
CLV_invest  = somme(t=1..5) [ NBI_invest  x g_inv^(t-1) x S(t) / (1+r)^t ]
CLV_immo    = somme(t=1..5) [ NBI_immo    x g_immo^(t-1) x S(t) / (1+r)^t ]
CLV_aut_cr  = somme(t=1..5) [ NBI_aut_cr  x g_cr^(t-1)  x S(t) / (1+r)^t ]
CLV_aut_pnb = somme(t=1..5) [ NBI_aut_pnb x g_pnb^(t-1) x S(t) / (1+r)^t ]

CLV_total = CLV_epargne + CLV_invest + CLV_immo + CLV_aut_cr + CLV_aut_pnb
```

Cela permet d'identifier **d'ou vient la valeur** de chaque client et d'adapter les strategies commerciales par famille.

---

## 8. Validation

- **Walk-forward temporelle** : entrainer sur les cohortes anciennes, valider sur les cohortes recentes
- **Par sous-modele** : MAE, R2, Spearman par famille
- **Agregat** : MAE et R2 du NBI total predit vs observe
- **Calibration** : verifier que les moyennes par decile sont monotones et stables dans le temps
- **Coherence** : somme des NBI par famille ≈ NBI total observe (validation croisee avec les fichiers PNB)

---

## 9. Structure du projet

```
Acquisition_model/
+-- documentation/
|   +-- architecture.md                  # CE DOCUMENT
|   +-- check_list.md                    # Prerequis et hypotheses a verifier
|   +-- documentation_modele_acquisitions.md
+-- hypotheses/
|   +-- ha1..ha13_*.py                   # Scripts existants (a adapter)
+-- notebooks/
|   +-- data_preparation.ipynb           # A reecrire pour encours + NBI
|   +-- eda_acquisitions.ipynb           # A adapter
+-- presentation/
|   +-- CLV_Acquisition_Model_Presentation.pptx
```

Fichiers a creer lors de l'implementation :
- `train_multi_model.py` — 5 sous-modeles XGBoost
- `calibration.py` — calibration par deciles
- `clv_assembly.py` — assemblage NBI + CLV
