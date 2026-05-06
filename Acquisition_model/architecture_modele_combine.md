# Architecture du Modele Combine — Multi-Modele BCEF + Fenetrage Trimestriel T/T+1/T+3

## Contexte

Le modele BCEF existant de la banque (entraine ~2022 sur donnees 2017-2019) utilise une **decomposition en 4 sous-modeles par produit** avec **lissage par deciles** et **separation des marges**. Notre projet a construit un systeme de **fenetrage trimestriel T/T+1/T+3** avec des features comportementales riches (4-6 mois d'observation) et validation walk-forward.

**Objectif** : Combiner les deux approches — utiliser la decomposition structurelle BCEF (4 sous-modeles, calibration par deciles, interpretabilite par produit) avec nos ameliorations operationnelles (retraining trimestriel, features enrichies, donnees 2021-2025, fenetrage variable).

**Categories produit** : Epargne bilan, Investissements financiers, Credit, Autre PNB (identiques au BCEF).
**Format de l'extraction** : A definir — le preprocessing est concu pour auto-detecter le format.

---

## 1. Vue d'ensemble de l'architecture

```
                    Features a T+1
                   (4-6 mois obs)
                          |
          +---------------+---------------+---------------+
          v               v               v               v
    +----------+   +----------+   +----------+   +----------+
    | XGBoost  |   | XGBoost  |   | XGBoost  |   | XGBoost  |
    | Epargne  |   | Invest.  |   | Credit   |   | Autre PNB|
    +----+-----+   +----+-----+   +----+-----+   +----+-----+
         |              |              |              |
    +----v-----+   +----v-----+   +----v-----+   +----v-----+
    |Decile D[x]|  |Decile D[x]|  |Decile D[x]|  |Decile D[x]|
    | lissage  |   | lissage  |   | lissage  |   | lissage  |
    +----+-----+   +----+-----+   +----+-----+   +----+-----+
         |              |              |              |
         v              v              v              v
    NBI_epargne    NBI_invest     NBI_credit     NBI_autre
         |              |              |              |
         +-------+------+------+------+
                 v
       PNB_predit (somme)
                 |
       +---------v----------+
       |   CLV = S(t=1..5)  |
       | PNB x g^t x S(t)   |
       |    / (1+r)^t        |
       +--------------------+
```

**Du BCEF** : decomposition en 4 modeles, calibration par deciles, interpretabilite par produit
**De notre approche** : fenetrage T/T+1/T+3, features obs riches, retraining trimestriel, validation walk-forward

---

## 2. Modifications du pipeline de donnees

### 2.1 Nouvelles donnees requises (extraction fraiche)

Fournir des fichiers de **PNB mensuel par categorie de produit** en complement (ou remplacement) des fichiers PNB agreges actuels.

**Option A — Fichiers PNB par produit (preferee)** :
```
1. DATA/PNB_PRODUIT/PNB_EPARGNE_YYYY_SX.csv     -> PNB mensuel epargne par client
1. DATA/PNB_PRODUIT/PNB_INVEST_YYYY_SX.csv       -> PNB mensuel investissements par client
1. DATA/PNB_PRODUIT/PNB_CREDIT_YYYY_SX.csv       -> PNB mensuel credit par client
1. DATA/PNB_PRODUIT/PNB_AUTRE_YYYY_SX.csv        -> PNB mensuel autre par client
```

**Option B — Fichier unique avec colonne categorie** :
```
1. DATA/PNB/PNB_YYYY_SX.csv avec colonnes : client_id, mois_idx, categorie, montant
```

**Option C — Fichiers d'encours + taux de marge (style BCEF)** :
```
1. DATA/ENCOURS/ENCOURS_EPARGNE_YYYY_SX.csv      -> soldes epargne
1. DATA/ENCOURS/ENCOURS_INVEST_YYYY_SX.csv        -> AuM investissements
1. DATA/ENCOURS/ENCOURS_CREDIT_YYYY_SX.csv        -> encours credit
+ taux de marge fournis par la Finance (t_s, t_i, t_c)
```

Le code auto-detecte le format disponible : si `PNB_PRODUIT/` existe, il charge les fichiers par produit ; sinon il fonctionne en mode total uniquement.

### 2.2 Nouvelles colonnes cibles

```python
PRODUCT_CATEGORIES = ["epargne", "invest", "credit", "autre"]

for cat in PRODUCT_CATEGORIES:
    df[f"pnb_{cat}_total"]     = ...  # somme du PNB mensuel par produit
    df[f"pnb_{cat}_cumul_obs"] = ...  # portion fenetre d'observation
    df[f"pnb_{cat}_remaining"] = ...  # portion prediction

# Agregat (validation : doit etre egal a la somme des composantes)
df["pnb_total"] = sum(df[f"pnb_{cat}_total"] for cat in PRODUCT_CATEGORIES)
```

### 2.3 Nouvelles features comportementales par produit

```python
for cat in PRODUCT_CATEGORIES:
    df[f"obs_slope_{cat}"]        = ...  # pente du PNB par produit pendant l'observation
    df[f"obs_volatility_{cat}"]   = ...  # ecart-type du PNB mensuel par produit
    df[f"pnb_moyen_obs_{cat}"]    = ...  # PNB mensuel moyen par produit pendant l'observation
    df[f"has_activity_{cat}"]     = ...  # binaire : activite positive dans cette categorie ?
```

---

## 3. Pipeline d'entrainement multi-modeles

### 3.1 Nouveau fichier : `train_multi_model.py`

Quatre modeles XGBoost partageant le meme jeu de features mais avec des cibles differentes :

```python
MODELS = {
    "epargne": {"target": "pnb_epargne_total", "label": "Epargne bilan"},
    "invest":  {"target": "pnb_invest_total",  "label": "Investissements financiers"},
    "credit":  {"target": "pnb_credit_total",  "label": "Encours credit"},
    "autre":   {"target": "pnb_autre_total",   "label": "Autre PNB (commissions, assurance)"},
}
```

### Jeu de features partage

| Famille | Features |
|---------|----------|
| Declaratif | segment, profession, trimestre_acquisition, annee_acquisition |
| Controles fenetrage | n_mois_nbi, n_mois_observation |
| Comportemental (total) | pnb_cumul_obs, pnb_cumul_3m, obs_slope, obs_volatility, obs_active_months, pnb_moyen_obs |
| Comportemental (par produit) | obs_slope_{cat}, pnb_moyen_obs_{cat}, has_activity_{cat} |
| Equipements | n_produits_total, colonnes qty_* |
| Derives | is_slow_starter, is_early_peak, mois_anciennete |

### Algorithme

XGBRegressor — aligne avec BCEF, gestion native des valeurs manquantes :
- `objective="reg:pseudohuberror"` (robuste aux outliers)
- `n_estimators=500, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8`
- Early stopping sur ensemble de validation

### 3.2 Validation walk-forward temporelle

```
Fold 1 : Train Q1-Q4 2021 -> Validation Q1 2022
Fold 2 : Train Q1 2021-Q1 2022 -> Validation Q2 2022
...
Fold N : Train Q1 2021-Q2 2024 -> Validation Q3 2024
Test final : Q1-Q2 2025 (hold-out)
Scoring : Q3-Q4 2025 (pas de verite terrain)
```

### 3.3 Metriques d'evaluation

| Metrique | Par sous-modele | Agregat |
|----------|----------------|---------|
| MAE | MAE par categorie produit | MAE de la somme vs pnb_total |
| R2 | R2 par categorie | R2 de la somme vs pnb_total |
| Lift par decile | Courbe de lift par categorie | Lift global |
| Correlation de rang | Spearman par categorie | Spearman sur le total |

---

## 4. Couche de calibration par deciles

### 4.1 Principe

Chaque prediction brute est convertie en **valeur moyenne reelle du decile** correspondant :

1. La prediction brute place le client dans un decile D1-D10 (par rapport a la distribution d'entrainement)
2. Le client recoit la **valeur moyenne reelle de ce decile** observee dans les donnees d'entrainement

### 4.2 Implementation

```python
class DecileCalibrator:
    def __init__(self, n_bins=10):
        self.n_bins = n_bins
        self.bin_edges = None
        self.bin_means = None

    def fit(self, y_pred_oof, y_actual_oof):
        percentiles = np.linspace(0, 100, self.n_bins + 1)
        self.bin_edges = np.percentile(y_pred_oof, percentiles)
        self.bin_edges[0], self.bin_edges[-1] = -np.inf, np.inf

        assignments = np.digitize(y_pred_oof, self.bin_edges[1:-1])
        self.bin_means = np.array([
            y_actual_oof[assignments == b].mean()
            for b in range(self.n_bins)
        ])

    def transform(self, y_pred):
        assignments = np.digitize(y_pred, self.bin_edges[1:-1])
        return self.bin_means[np.clip(assignments, 0, self.n_bins - 1)]
```

### 4.3 Choix de conception

- **Predictions out-of-fold** pour definir les bornes de deciles (evite l'overfitting de calibration)
- **10 deciles** (standard), tester 20 vigintiles si l'echantillon le permet
- **Controle de monotonie** : verifier que les moyennes par decile sont croissantes
- **Calibration par modele** : chaque sous-modele a sa propre table de deciles

### 4.4 Nouveau fichier : `calibration.py`

Contient la logique DecileCalibrator + graphiques de calibration + comparaison brut vs calibre.

---

## 5. Assemblage CLV

### 5.1 Prediction directe du PNB sur 5 ans (approche BCEF)

Le modele BCEF predit le **PNB cumule sur 5 ans** directement — il ne predit PAS 1 an puis multiplie par un facteur de croissance. Chaque sous-modele XGBoost est entraine pour prevoir le PNB total par produit sur tout l'horizon de projection.

**Pour notre implementation** : Nos donnees d'entrainement couvrent 2021-2025. Les cohortes anciennes (Q1 2021) ont ~4 ans de PNB observable. Nous pouvons entrainer sur des horizons progressivement plus longs.

**Approche hybride** :
- **Annee 1** (T->T+3, 10-12 mois) : Predit directement par les 4 sous-modeles, haute confiance
- **Annees 2-5** : Pour les cohortes avec suffisamment d'historique, on observe le PNB multi-annuel reel pour calibrer les facteurs de croissance. Pour les cohortes recentes, on applique des facteurs de croissance par produit calibres empiriquement.

A mesure que les donnees s'accumulent, on etend progressivement l'horizon de prediction directe.

### 5.2 Agregation

```python
# Predictions calibrees par produit (annee 1)
pnb_epargne_cal = calibrator_epargne.transform(model_epargne.predict(X))
pnb_invest_cal  = calibrator_invest.transform(model_invest.predict(X))
pnb_credit_cal  = calibrator_credit.transform(model_credit.predict(X))
pnb_autre_cal   = calibrator_autre.transform(model_autre.predict(X))

# PNB annuel predit total
pnb_predit_annuel = (pnb_epargne_cal + pnb_invest_cal + pnb_credit_cal + pnb_autre_cal) * (12 / n_mois_nbi)
```

### 5.3 Formule CLV (horizon 5 ans)

```python
# Facteurs de croissance par produit (calibres sur donnees multi-annuelles observees)
GROWTH = {"epargne": 1.05, "invest": 1.12, "credit": 1.00, "autre": 1.08}

def compute_clv(pnb_by_product, survival_rates, discount=0.05, horizon=5):
    clv = 0
    for t in range(1, horizon + 1):
        annual_nbi = sum(
            pnb * (GROWTH[cat] ** (t - 1))
            for cat, pnb in pnb_by_product.items()
        )
        clv += annual_nbi * survival_rates[t - 1] / ((1 + discount) ** t)
    return clv
```

### 5.4 Decomposition CLV par produit

```python
# D'ou vient la valeur du client ?
for cat in ["epargne", "invest", "credit", "autre"]:
    clv_component[cat] = compute_single_product_clv(pnb_cal[cat], GROWTH[cat], S, ...)

# -> Permet des strategies commerciales differenciees par produit
```

### 5.5 Nouveau fichier : `clv_assembly.py`

---

## 6. Comparaison avec baseline

| Metrique | Baseline (modele unique) | Multi-modele (4 + calibration) |
|----------|--------------------------|-------------------------------|
| MAE sur pnb_total | ? | ? (devrait etre egal ou meilleur) |
| R2 sur pnb_total | ? | ? |
| Erreur de calibration | ? | ? (devrait etre nettement meilleur) |
| Interpretabilite | Faible (un seul chiffre PNB) | Elevee (decomposition par produit) |

Nouveau fichier : `train_baseline.py` — XGBoost unique sur pnb_total avec calibration par deciles.

---

## 7. Structure de fichiers finale

```
Acquisition_model/
+-- architecture_modele_combine.md   # CE DOCUMENT
+-- data_preparation.ipynb           # MAJ : ajout chargement PNB par produit
+-- eda_acquisitions.ipynb           # MAJ : ajout sections EDA par produit
+-- train_baseline.py                # NOUVEAU : baseline modele unique + calibration
+-- train_multi_model.py             # NOUVEAU : 4 sous-modeles XGBoost
+-- calibration.py                   # NOUVEAU : lissage par deciles
+-- clv_assembly.py                  # NOUVEAU : agregation predictions -> CLV
+-- evaluation.py                    # NOUVEAU : framework d'evaluation croisee
+-- documentation_modele_acquisitions.md  # MAJ : nouvelle architecture
+-- hypotheses_et_analyses.md        # MAJ : ajout hypotheses decomposition
+-- ha1..ha13_*.py                   # CONSERVE : scripts d'hypotheses existants
+-- CLV_Acquisition_Model_Presentation.pptx
+-- df_acquisitions.pkl              # SORTIE : inclut colonnes par produit
```

---

## 8. Phases d'implementation

### Phase 0 : Nettoyage et documentation
1. Supprimer les anciens fichiers (fait)
2. Ecrire `architecture_modele_combine.md` (ce document)
3. Mettre a jour `requirements.txt` (ajouter xgboost)

### Phase 1 : Enrichissement des donnees (depend de l'extraction)
1. Mettre a jour `data_preparation.ipynb` pour charger le PNB par produit
2. Creer les cibles et features par produit
3. Valider : somme des cibles par produit = pnb_total

### Phase 2 : Baseline + Calibration
1. Creer `train_baseline.py` — XGBoost unique sur pnb_total avec calibration
2. Creer `calibration.py` — module DecileCalibrator reutilisable
3. Etablir les metriques de reference

### Phase 3 : Entrainement multi-modeles
1. Creer `train_multi_model.py` — 4 sous-modeles XGBoost
2. Validation walk-forward pour chaque sous-modele
3. Comparer performance agregee vs baseline

### Phase 4 : Assemblage CLV
1. Creer `clv_assembly.py` — CLV par produit avec croissance x survie
2. Analyse de decomposition par produit (d'ou vient la valeur par segment ?)
3. Pipeline de scoring pour nouvelles cohortes

### Phase 5 : Documentation et presentation
1. Mettre a jour `documentation_modele_acquisitions.md`
2. Mettre a jour `generate_presentation.py` avec slides multi-modeles
3. Mettre a jour `hypotheses_et_analyses.md`

---

## 9. Risques et mitigations

### Zero-inflation dans les categories creuses
Beaucoup de nouveaux clients n'ont aucun PNB credit ou investissement dans leurs 10-12 premiers mois.
**Mitigation** : Pour les categories ou >50% des clients ont une cible a zero, utiliser une approche en deux etapes : (1) classifieur zero/non-zero, (2) regresseur sur le sous-ensemble non-zero. La calibration par deciles gere aussi naturellement ce cas.

### La somme des PNB par produit peut ne pas etre egale au total
Arrondis, differences de timing, ou changements de categorisation.
**Mitigation** : Calculer le residu et l'attribuer a la categorie `autre`. Logger un warning si le residu depasse 5%.

### Le multi-modele peut ne pas battre le modele unique
La decomposition ajoute de la complexite sans garantie d'amelioration.
**Mitigation** : La Phase 2 (baseline) est executee en premier. Le gain principal peut etre l'interpretabilite (decomposition CLV par produit) plutot que l'amelioration brute du MAE.

---

## 10. Verification

- [ ] La somme des PNB par produit correspond au PNB total
- [ ] R2 walk-forward de chaque sous-modele > 0.15
- [ ] La calibration par deciles reduit le MAE vs predictions brutes
- [ ] MAE agregat multi-modele <= MAE baseline modele unique
- [ ] La decomposition CLV montre des profils produit differencies par segment
- [ ] La validation walk-forward ne montre pas de degradation temporelle
- [ ] Tous les noms de colonnes sont coherents entre preprocessing, entrainement et evaluation
