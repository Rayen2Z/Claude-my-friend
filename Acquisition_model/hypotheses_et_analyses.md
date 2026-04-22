# Hypotheses et Analyses Exploratoires — Modele Acquisitions

Ce document liste toutes les hypotheses a valider et les analyses exploratoires a mener avant l'entrainement du modele PNB nouvelles acquisitions.

**Architecture du modele** : T/T+1/T+3 (cadence trimestrielle)
- **T** = trimestre d'acquisition
- **T+1** = fin de la fenetre d'observation (snapshot equipements, PNB cumule)
- **T+3** = fin de la fenetre cible (PNB total)
- La fenetre d'observation varie de 4 a 6 mois (`n_mois_observation`)
- La fenetre cible varie de 10 a 12 mois (`n_mois_nbi`)

**Cible du modele** : `pnb_total` brut, avec `n_mois_nbi` comme feature. Le modele apprend a relativiser la duree d'exposition.

---

## Hypotheses a Valider

### HA1 — Qualite et completude des donnees
**Question** : Les donnees sont-elles suffisamment completes et coherentes pour entrainer un modele fiable ?
**Analyse** :
- Taux de valeurs manquantes par colonne et par annee
- Doublons sur client_id (intra-trimestre et inter-trimestre)
- Coherence des dates de creation (pas dans le futur, pas avant 2023)
- Coherence du PNB (pas de valeurs aberrantes extremes)
- Couverture des equipements (% de clients avec au moins un produit renseigne)
- Distribution des segments et professions (pas de categorie dominante a 99%)
- **Distribution de `n_mois_nbi`** (10, 11, 12) et `n_mois_observation` (4, 5, 6) : verifier l'equilibre
- **Gestion des NaN attendus** : pnb_m11/pnb_m12 sont legitimement nuls pour les clients avec n_mois_nbi < 11/12

### HA2 — Le segment est un predicteur du PNB
**Question** : Le segment client (Mass Affluent, Mass Retail, Mass Retail with Potential) est-il significativement correle au PNB ?
**Analyse** :
- PNB moyen et median par segment — **en brut ET en PNB/mois** (controle pour `n_mois_nbi`)
- Test statistique (Kruskal-Wallis) sur `pnb_mensuel_moyen` pour eviter le biais de duree
- Distribution du PNB par segment (boxplots, violins)
- Part de chaque segment dans le PNB total (concentration)
- Coefficient de variation intra-segment (dispersion)

**Note T/T+1/T+3** : Les comparaisons sur PNB brut peuvent etre biaisees si la repartition de `n_mois_nbi` differe entre segments. Toujours presenter les resultats normalises en parallele.

### HA3 — La profession est un predicteur du PNB
**Question** : La categorie professionnelle (Jeune Actif, Salarie, Cadre, etc.) apporte-t-elle un signal predictif au-dela du segment ?
**Analyse** :
- PNB moyen par profession — **en brut ET en PNB/mois**
- Test statistique (Kruskal-Wallis) sur `pnb_mensuel_moyen`
- Interaction segment x profession (heatmap des PNB moyens)
- Risque de multicolinearite segment/profession (correlation de Cramer's V)

**Note T/T+1/T+3** : Meme controle par `n_mois_nbi` que pour HA2.

### HA4 — Le PNB d'observation est predictif du PNB total
**Question** : Le comportement PNB pendant la fenetre d'observation (T a T+1) est-il un bon predicteur du PNB total (T a T+3) ? C'est l'hypothese fondamentale du modele.

**ATTENTION — Plancher mecanique de correlation** : `pnb_cumul_obs` est un sous-ensemble de `pnb_total` (les N premiers mois sont inclus dans les deux). Cela cree une correlation plancher artificielle d'environ `sqrt(n_mois_observation / n_mois_nbi)` meme sans aucun pouvoir predictif reel. L'analyse doit isoler le signal au-dela de ce plancher.

**Analyse** :
- **HA4a — Correlation brute (reference)** :
  - Correlation de Pearson entre `pnb_cumul_3m` et `pnb_total`
  - Correlation de Pearson entre `pnb_cumul_obs` et `pnb_total`
  - Scatter plots avec droites de regression
- **HA4b — Correlation nette (signal reel)** :
  - Correlation entre `pnb_cumul_obs` et `pnb_remaining` (= `pnb_total - pnb_cumul_obs`)
  - C'est la mesure du vrai pouvoir predictif : le PNB observe predit-il le PNB **non encore observe** ?
  - R2 de la regression `pnb_cumul_obs -> pnb_remaining`
  - Comparer au plancher mecanique pour quantifier le gain
- Correlation progressive (mois 1 a N vs PNB total et vs PNB remaining)
- R2 d'une regression lineaire simple `pnb_cumul_obs -> pnb_total` et `pnb_cumul_obs -> pnb_remaining`
- Ratio `pnb_cumul_obs / pnb_total` : quelle part du PNB total est deja realisee a T+1 ?
- Analyse par segment : la correlation est-elle stable entre les segments ?

### HA5 — Les equipements (produits) sont le signal le plus fort
**Question** : Le nombre et le type de produits au snapshot T+1 sont-ils le meilleur predicteur du PNB total ?
**Analyse** :
- PNB moyen par nombre de produits (0, 1, 2, 3, 4+)
- PNB moyen par type de produit (avec/sans chaque produit)
- Correlation entre `n_produits_total` et `pnb_total`
- Ranking des produits par impact sur le PNB (difference de PNB avec/sans le produit)
- Interaction produits x segment (certains produits sont-ils plus impactants pour certains segments ?)
- Analyse de la **domiciliation du salaire** comme variable binaire : PNB moyen avec vs sans domiciliation
- Comparaison du pouvoir predictif : PNB cumule seul vs equipements seuls vs combine

**Note T/T+1/T+3** : Le `n_produits_total` est confonde avec la duree en banque au moment du snapshot (4-6 mois). Ajouter `n_mois_observation` comme controle dans les regressions.

### HA6 — La dynamique temporelle du PNB d'observation est informative
**Question** : La trajectoire du PNB mensuel pendant la fenetre d'observation (croissante, stable, decroissante) apporte-t-elle un signal au-dela du niveau cumule ?
**Analyse** :
- Classifier les trajectoires en 4 profils : croissant, stable, decroissant, sporadique
- PNB total moyen par profil de trajectoire
- Pente de la regression lineaire des PNB mensuels (fenetre d'observation) comme feature
- Comparaison du pouvoir predictif : `pnb_cumul_obs` seul vs `pnb_cumul_obs` + tendance
- Identification des "slow starters" vs "early peaks"

**Note T/T+1/T+3** : La pente est estimee sur 4 a 6 points selon `n_mois_observation`. Une pente sur 4 points est plus bruitee qu'une pente sur 6 points. Les seuils de classification des trajectoires doivent etre adaptes ou la fiabilite doit etre mesuree par tranche de `n_mois_observation`.

### HA7 — La saisonnalite d'acquisition impacte le PNB
**Question** : Le trimestre d'acquisition influence-t-il le PNB ?

**ATTENTION — Biais de duree et de calendrier** :
1. Les clients Q1 ont `n_mois_nbi = 10-12`, les clients Q4 aussi mais sur des mois calendaires differents. Comparer le PNB brut melange le signal saisonnier et l'artefact de duree.
2. Les clients Q1 ont leur cible sur Q1-Q4 (meme annee). Les clients Q3 ont leur cible sur Q3-Q2 (annee suivante). La composition calendaire de la cible differe.

**Analyse** :
- PNB **mensuel moyen** (`pnb_mensuel_moyen`) par trimestre d'acquisition (pas le PNB brut)
- Test statistique (Kruskal-Wallis) sur `pnb_mensuel_moyen`
- Y a-t-il un "effet janvier" ou un "effet rentree" ?
- La saisonnalite est-elle stable entre les cohortes ?
- **Controle** : comparer les resultats avec et sans normalisation par `n_mois_nbi`

### HA8 — Les cohortes sont stables dans le temps
**Question** : Le profil PNB des nouveaux clients est-il stable entre les cohortes trimestrielles, ou y a-t-il une derive temporelle ?
**Analyse** :
- PNB mensuel moyen par cohorte trimestrielle (9+ cohortes disponibles)
- Distribution du PNB par cohorte (KS test pour comparer les distributions)
- Composition des segments par cohorte (le mix a-t-il change ?)
- Si derive detectee : le modele doit etre re-entraine frequemment (confirme l'approche trimestrielle)

**Note T/T+1/T+3** : Utiliser `pnb_mensuel_moyen` et non `pnb_total` brut pour controler la duree variable. Comparer les cohortes a `n_mois_nbi` equivalent si possible.

### HA9 — Le PNB des nouveaux clients est significativement different de celui des clients etablis
**Question** : Les nouveaux clients generent-ils un PNB different (probablement inferieur) des clients etablis sur la meme periode ?
**Analyse** :
- Comparer le PNB **annualise** des nouveaux clients (`pnb_mensuel_moyen * 12`) vs clients etablis (PNB annuel)
- Distribution comparative (histogrammes superposes)
- Ratio PNB nouveau / PNB etabli par segment
- Cela justifie la necessite d'un modele separe pour les nouvelles acquisitions

**Note T/T+1/T+3** : L'annualisation est necessaire car la fenetre cible est de 10-12 mois et non exactement 12.

### HA10 — La concentration du PNB suit une loi de Pareto
**Question** : Le PNB est-il concentre sur un petit nombre de clients (comme pour le portefeuille etabli) ?
**Analyse** :
- Courbe de Lorenz du PNB total des nouveaux clients
- Coefficient de Gini
- Quelle part du PNB est generee par le top 10%, top 20% ?
- Comparaison avec la concentration du portefeuille etabli

**Note T/T+1/T+3** : Executer l'analyse separement par tranche de `n_mois_nbi` (10, 11, 12) pour verifier que la forme de la distribution n'est pas un artefact de la duree variable.

### HA11 — Normalisation du PNB par duree d'exposition
**Question** : Le PNB mensuel moyen (`pnb_total / n_mois_nbi`) est-il constant quel que soit le nombre de mois d'observation, ou la duree biaise-t-elle le PNB moyen ?
**Analyse** :
- Comparer `pnb_mensuel_moyen` pour `n_mois_nbi` = 10, 11, 12
- Test statistique (Kruskal-Wallis) entre les trois groupes
- Si les moyennes sont stables : la normalisation est valide, le PNB est lineaire en duree
- Si les moyennes different significativement : le modele doit apprendre une correction non-lineaire
- Analyser par segment : la stabilite est-elle uniforme ?

**Impact** : Valide le choix de garder `pnb_total` brut + `n_mois_nbi` comme feature. Si la normalisation est valide, on pourrait aussi utiliser `pnb_mensuel_moyen` comme cible alternative.

### HA12 — Definition de la cible : PNB total vs PNB restant
**Question** : Predire `pnb_total` (inclut la fenetre d'observation) est-il meilleur ou pire que predire `pnb_remaining = pnb_total - pnb_cumul_obs` ?
**Analyse** :
- Quantifier le plancher mecanique de correlation : `r_mecanique = sqrt(var(pnb_cumul_obs) / var(pnb_total))`
- R2 de la regression `features -> pnb_total` vs `features -> pnb_remaining`
- MAE et RMSE des deux approches
- La correlation `pnb_cumul_obs` vs `pnb_total` est-elle artificiellement elevee par rapport a `pnb_cumul_obs` vs `pnb_remaining` ?
- Analyse des residus : les erreurs sont-elles mieux calibrees pour l'une ou l'autre cible ?

**Impact** : Si `pnb_remaining` donne un R2 similaire sur les features non-PNB, il est preferable car il isole le vrai signal predictif et evite que le modele "triche" via l'overlap.

### HA13 — Impact de la longueur de la fenetre d'observation
**Question** : Les clients avec `n_mois_observation = 4` sont-ils aussi bien predits que ceux avec `n_mois_observation = 6` ?
**Analyse** :
- Comparer l'erreur de prediction (MAE, RMSE) par tranche de `n_mois_observation` (4, 5, 6)
- Tester si la pente PNB (`obs_slope`) est aussi fiable a 4 mois qu'a 6 mois (variance de la pente par tranche)
- Comparer le R2 du modele par tranche
- Le nombre de produits au snapshot T+1 est-il comparable a 4 mois vs 6 mois ?

**Impact** : Si la qualite de prediction diverge significativement, envisager un traitement differencie (features adaptees, sous-modeles) ou ponderer les echantillons par fiabilite.

---

## Analyses Exploratoires Complementaires

### AE1 — Profil-type des clients a fort PNB
- Identifier les top 20% de PNB mensuel moyen et analyser leur profil : segment, profession, equipement, trajectoire
- Clustering (K-means ou segmentation manuelle) des profils PNB

### AE2 — Clients a PNB nul ou negatif
- Quel % de nouveaux clients a un PNB <= 0 apres la fenetre cible ?
- Profil de ces clients (segment, equipement, trajectoire)
- Sont-ils "dormants" (aucune activite) ou en perte (couts > revenus) ?

### AE3 — Matrice de correlation complete
- Heatmap de correlation entre toutes les features numeriques
- Inclure `n_mois_nbi` et `n_mois_observation` dans la matrice
- Identifier les features fortement correlees (> 0.8) pour eviter la multicolinearite
- VIF (Variance Inflation Factor) si necessaire

### AE4 — ~~Analyse des equipements dans le temps~~ (DEPRECATED)
> Deprecee : le modele T/T+1/T+3 utilise un snapshot unique a T+1. Il n'y a pas de donnees d'equipement mensuelles. L'evolution de l'equipement dans le temps n'est pas observable avec cette architecture.

### AE5 — Effet de la position dans le trimestre d'acquisition
- Un client qui rejoint le 1er mois du trimestre a-t-il un PNB different de celui qui rejoint le dernier mois ?
- Cela valide/invalide la pertinence de la feature `n_mois_observation` et `n_mois_nbi`
- Cette analyse est devenue critique avec l'architecture T/T+1/T+3 car la position dans le trimestre determine directement la longueur des fenetres
- Lien avec HA11 et HA13

---

## Fichiers d'Analyse

| Fichier | Hypotheses couvertes |
|---------|---------------------|
| `ha1_qualite_donnees.py` | HA1 (qualite, completude, coherence, distribution n_mois_nbi) |
| `ha2_ha3_segments_professions.py` | HA2 + HA3 (segments, professions, correlations PNB, controle n_mois_nbi) |
| `ha4_pnb_precoce_predictif.py` | HA4 (correlation PNB obs vs total, pnb_remaining, plancher mecanique) |
| `ha5_equipements_signal.py` | HA5 (produits comme signal principal, controle n_mois_observation) |
| `ha6_ha7_dynamique_saisonnalite.py` | HA6 + HA7 (trajectoire PNB, saisonnalite avec controle duree) |
| `ha8_ha9_ha10_cohortes_concentration.py` | HA8 + HA9 + HA10 (stabilite trimestrielle, comparaison annualisee, Pareto par n_mois_nbi) |
| `ha11_normalisation_duree.py` | HA11 (normalisation PNB/mois par duree d'exposition) |
| `ha12_cible_total_vs_restant.py` | HA12 (pnb_total vs pnb_remaining comme cible) |
| `ha13_fenetre_observation.py` | HA13 (impact de la longueur de fenetre d'observation) |
