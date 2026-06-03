# Memoire du Projet — Modele CLV Nouvelles Acquisitions

> **LIRE CE FICHIER EN PREMIER** a chaque nouvelle session. Il contient l'etat complet du projet, les decisions prises, et le contexte necessaire pour reprendre le travail sans relire tous les fichiers.

---

## 1. Le projet en une phrase

Predire la **Customer Lifetime Value (CLV) sur 5 ans** des nouveaux clients d'une banque luxembourgeoise, a partir d'un snapshot pris **3 mois apres leur acquisition**, en decomposant la prediction en **5 familles de produits**.

---

## 2. Architecture finale

### 2.1 Les 5 sous-modeles

| # | Famille | Prediction | Conversion en NBI |
|---|---------|-----------|-------------------|
| 1 | Epargne bilan | Encours moyen (solde epargne) | x marge t_s |
| 2 | Investissements financiers | Valeur placements (AuM) | x marge t_i |
| 3 | Credit immobilier | Encours prets immo | x marge t_m |
| 4 | Autres credits | Encours credits conso/revolving | x marge t_c |
| 5 | Autre PNB | Commissions, assurances, frais carte | Direct (deja du NBI) |

- Les modeles 1-4 predisent des **encours** (balances en EUR), pas du NBI
- Les taux de marge convertissent les encours en NBI : `NBI = encours x marge`
- Le modele 5 predit du **NBI directement** (pas de conversion)

### 2.2 Calibration par deciles

Chaque sous-modele produit une prediction brute. Le client est ensuite affecte a un **decile (D1-D10)** base sur la distribution des predictions d'entrainement. La prediction finale est la **valeur moyenne observee de ce decile**, pas la prediction brute. Cela :
- Elimine les outliers
- Lisse les predictions
- Produit des resultats stables et interpretables

### 2.3 Formule CLV

```
NBI_total = (encours_ep x t_s) + (encours_inv x t_i) + (encours_immo x t_m) + (encours_cr x t_c) + nbi_autre

CLV = somme(t=1..5) [ NBI_total x g^(t-1) / (1+r)^t ]
```

Pas de terme de survie S(t) explicite — voir section 4 sur le churn.

### 2.4 Observation

**Snapshot fixe a M+3** (3 mois apres l'acquisition). Pas de fenetre variable, pas de fenetrage trimestriel T/T+1/T+3 (cette approche a ete abandonnee).

---

## 3. Decisions cles et leur justification

### 3.1 Pourquoi 5 familles et pas 1 modele unique ?
- Permet de savoir **d'ou vient la valeur** de chaque client (epargne vs credit vs invest)
- Strategies commerciales differenciees par famille
- Aligne avec l'approche BCEF (modele precedent de la banque, entraine ~2022 sur 2017-2019)
- Le credit immobilier est separe des autres credits car dynamique tres differente (montants eleves, longue duree, taux de retention fort)

### 3.2 Pourquoi predire des encours et pas du NBI directement ?
- Les encours sont plus stables et moins bruites que le NBI mensuel
- La separation encours/marge permet de mettre a jour les marges sans re-entrainer le modele (si les taux changent)
- Aligne avec l'approche BCEF
- Exception : le modele 5 (autre PNB) predit du NBI car ces revenus ne sont pas lies a un encours

### 3.3 Pourquoi M+3 et pas plus tot ou plus tard ?
- A M+0 (jour de l'acquisition) : pas assez d'information
- A M+3 : on a les premiers encours, equipements, et un signal NBI
- A M+6+ : la prediction arrive trop tard pour etre utile commercialement
- 3 mois est le compromis entre signal et operationnalite

### 3.4 Pourquoi pas de modele de churn separe ?
Les donnees d'entrainement couvrent jusqu'a 5 ans post-acquisition. Un client qui part apres 2 ans aura des encours nuls pour les annees 3-5. Sa valeur cumulee sera donc naturellement plus basse, et les moyennes de deciles integreront ce taux d'attrition. La **tenure** (duree de presence) sera implicitement capturee comme un proxy de churn.

### 3.5 Pourquoi des deciles et pas les predictions brutes ?
- Les predictions brutes du XGBoost peuvent etre irrealistes pour des cas extremes
- Les deciles lissent les predictions et les rendent interpretables
- Chaque client est compare a son groupe de pairs
- Approche utilisee par BCEF avec succes

---

## 4. Donnees

### 4.1 Ce qu'on a deja
- **Fichiers Stock** : acquisitions mensuelles (client_id, segment, profession, date_creation) — Jan 2023 a Mar 2026
- **Fichiers PNB** : NBI total mensuel par client — meme periode
- **Fichiers Equipements** : snapshots trimestriels des produits detenus
- **Taux de marge** : t_s, t_i, t_m, t_c fournis par la Finance (deja recus)

### 4.2 Ce qu'on doit extraire
- **Encours epargne** : solde mensuel par client
- **Encours investissements** : AuM mensuel par client
- **Encours credit immobilier** : encours mensuel par client
- **Encours autres credits** : encours mensuel par client
- **NBI autre** : commissions + assurances mensuelles par client

L'utilisateur est en train de preparer cette extraction. Le format attendu est le meme que les fichiers PNB existants (client_id + colonnes indices mois bancaires).

### 4.3 Le NBI des 3 premiers mois comme feature
Les fichiers PNB existants (NBI total) sont conserves. Le NBI observe pendant les 3 premiers mois sera utilise comme **feature candidate** si l'hypothese H1 confirme son pouvoir predictif.

### 4.4 Encodage des mois bancaires
Janvier 1994 = indice 1. Formule : `indice = (annee - 1994) * 12 + mois`. Decembre 2025 = 384.

---

## 5. Hypotheses a verifier (check_list.md)

Avant de construire le modele, 8 hypotheses doivent etre validees :

| # | Question | Impact si invalide |
|---|---------|-------------------|
| H1 | Le NBI a 3 mois est-il predictif du NBI long terme ? | Pas de feature NBI precoce |
| H2 | Les encours/equipements a M+3 sont-ils predictifs ? | Modele plus faible |
| H3 | Les 5 familles ont-elles des profils differents ? | Fusionner les familles similaires |
| H4 | Chaque famille a-t-elle assez de non-zeros ? | Modele 2 etapes pour les familles creuses |
| H5 | L'equipement a M+3 est-il stable dans le temps ? | Facteurs de croissance compensatoires |
| H6 | Les taux de croissance par famille sont-ils stables ? | Facteurs conditionnels |
| H7 | Les clients multi-equipes restent-ils plus longtemps ? | L'equipement n'impacte pas la retention |
| H8 | Le modele est-il stable entre cohortes ? | Retraining frequent |

---

## 6. Roadmap

### Phase 0 — Nettoyage et documentation (FAIT)
- [x] Supprimer les anciens fichiers (churn model, old propositions, etc.)
- [x] Reorganiser en sous-dossiers (hypotheses/, documentation/, notebooks/, presentation/)
- [x] Ecrire l'architecture finale
- [x] Ecrire la checklist des hypotheses
- [x] Ecrire la checklist de validation des donnees

### Phase 1 — Extraction et validation des donnees (EN COURS — utilisateur)
- [ ] Extraire les encours par famille (epargne, invest, credit immo, autres credits)
- [ ] Extraire le NBI autre (commissions, assurances)
- [ ] Valider la coherence : somme des 5 familles ≈ NBI total existant
- [ ] Executer la checklist de validation (data_validation_checklist.md)
- [ ] Partager la structure des fichiers et un resume des donnees

### Phase 2 — Analyse exploratoire et hypotheses
- [ ] Verifier H1-H8
- [ ] Analyser la zero-inflation par famille (surtout credit immo)
- [ ] Analyser la profondeur temporelle disponible
- [ ] Decider du nombre final de sous-modeles (5 ou moins si certaines familles sont non-predictibles)

### Phase 3 — Construction du modele
- [ ] Reecrire `data_preparation.ipynb` pour le nouveau format (encours + NBI)
- [ ] Creer `train_multi_model.py` — 5 sous-modeles XGBoost
- [ ] Creer `calibration.py` — calibration par deciles
- [ ] Validation walk-forward temporelle

### Phase 4 — Assemblage CLV
- [ ] Creer `clv_assembly.py` — encours x marge → NBI → decile → CLV
- [ ] Decomposition CLV par famille
- [ ] Scoring des nouvelles cohortes

### Phase 5 — Documentation et presentation
- [ ] Mettre a jour la presentation PowerPoint
- [ ] Documentation finale du modele

---

## 7. Contexte bancaire Luxembourg

- Banque basee au **Luxembourg**
- Clientele : residents luxembourgeois + **frontaliers** (France, Belgique, Allemagne)
- Enrichissement geographique : **STATEC** (pas INSEE)
- Segments clients : Mass Affluent, Mass Retail, Mass Retail with Potential
- Les frontaliers ont souvent des salaires plus eleves et des besoins specifiques (transfrontalier)

---

## 8. Ce qui a change (historique des decisions)

| Date | Decision | Raison |
|------|---------|--------|
| Avril 2024 | Architecture T/T+1/T+3 avec fenetres variables | Design initial |
| Avril 2024 | Modele unique sur NBI total | Premiere approche |
| Mai 2024 | Decomposition en 4 familles de produits | Alignement BCEF |
| Juin 2024 | Passage de 4 a 5 familles (credit immo separe) | Dynamiques tres differentes |
| Juin 2024 | Prediction d'encours + marges (au lieu de NBI direct) | Plus stable, aligne BCEF |
| Juin 2024 | Snapshot fixe a M+3 (abandon du fenetrage variable) | Simplification |
| Juin 2024 | Pas de modele de churn separe | Churn implicite dans les donnees |

---

## 9. Fichiers du projet

```
Acquisition_model/
+-- documentation/
|   +-- project_knowledge.md             # CE FICHIER — memoire du projet
|   +-- architecture.md                  # Architecture technique detaillee
|   +-- check_list.md                    # Prerequis et hypotheses
|   +-- data_validation_checklist.md     # Etapes de validation des donnees
|   +-- documentation_modele_acquisitions.md  # OBSOLETE — ancien design T/T+1/T+3
+-- hypotheses/
|   +-- ha1..ha13_*.py                   # Scripts d'hypotheses (ancien design, a adapter)
+-- notebooks/
|   +-- data_preparation.ipynb           # Preprocessing (ancien design, a reecrire)
|   +-- eda_acquisitions.ipynb           # EDA (ancien design, a adapter)
+-- presentation/
|   +-- CLV_Acquisition_Model_Presentation.pptx

generate_presentation.py                 # Generateur de slides
requirements.txt                         # pandas, numpy, matplotlib, seaborn, scikit-learn, xgboost, scipy, python-pptx
```

### Fichiers obsoletes (ancien design, a reecrire quand les donnees arrivent)
- `documentation_modele_acquisitions.md` — decrit l'ancien design T/T+1/T+3
- `notebooks/data_preparation.ipynb` — charge des fichiers PNB (pas des encours)
- `notebooks/eda_acquisitions.ipynb` — EDA sur l'ancien format
- `hypotheses/ha*.py` — hypotheses de l'ancien design (certaines restent pertinentes)

---

## 10. Notes techniques

- **XGBoost** est l'algorithme choisi (aligne avec BCEF, gestion native des NaN)
- **Validation walk-forward** : entrainer sur les cohortes anciennes, valider sur les recentes
- **Deciles out-of-fold** : les bornes de deciles sont calculees sur des predictions out-of-fold pour eviter l'overfitting
- **Encodage mois bancaires** : Jan 1994 = 1, formule = (annee - 1994) * 12 + mois
