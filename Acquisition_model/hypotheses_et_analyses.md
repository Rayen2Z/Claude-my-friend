# Hypotheses et Analyses Exploratoires — Modele Acquisitions

Ce document liste toutes les hypotheses a valider et les analyses exploratoires a mener avant l'entrainement du modele PNB nouvelles acquisitions.

---

## Hypotheses a Valider

### HA1 — Qualite et completude des donnees
**Question** : Les donnees sont-elles suffisamment completes et coherentes pour entrainer un modele fiable ?
**Analyse** :
- Taux de valeurs manquantes par colonne et par annee
- Doublons sur client_id (intra-annee et inter-annee)
- Coherence des dates de creation (pas dans le futur, pas avant 2023)
- Coherence du PNB (pas de valeurs aberrantes extremes)
- Couverture des equipements (% de clients avec au moins un produit renseigne)
- Distribution des segments et professions (pas de categorie dominante a 99%)

### HA2 — Le segment est un predicteur du PNB a 12 mois
**Question** : Le segment client (Mass Affluent, Mass Retail, Mass Retail with Potential) est-il significativement correle au PNB a 12 mois ?
**Analyse** :
- PNB moyen et median par segment
- Test statistique (Kruskal-Wallis) pour verifier la difference entre segments
- Distribution du PNB par segment (boxplots, violins)
- Part de chaque segment dans le PNB total (concentration)
- Coefficient de variation intra-segment (dispersion)

### HA3 — La profession est un predicteur du PNB a 12 mois
**Question** : La categorie professionnelle (Jeune Actif, Salarie, Cadre, etc.) apporte-t-elle un signal predictif au-dela du segment ?
**Analyse** :
- PNB moyen par profession
- Test statistique (Kruskal-Wallis)
- Interaction segment x profession (heatmap des PNB moyens)
- Risque de multicolinearite segment/profession (correlation de Cramer's V)

### HA4 — Le PNB des 3-6 premiers mois est predictif du PNB a 12 mois
**Question** : Le comportement PNB precoce (mois 1 a 6) est-il un bon predicteur du PNB total a 12 mois ? C'est l'hypothese fondamentale du modele.
**Analyse** :
- Correlation de Pearson entre pnb_cumul_3m et pnb_12m_total
- Correlation de Pearson entre pnb_cumul_6m et pnb_12m_total
- Scatter plot PNB 3 mois vs PNB 12 mois (avec droite de regression)
- Scatter plot PNB 6 mois vs PNB 12 mois
- R2 d'une regression lineaire simple pnb_6m -> pnb_12m
- Analyse par segment : la correlation est-elle stable entre les segments ?
- Ratio pnb_6m / pnb_12m : quelle part du PNB 12 mois est deja realisee a 6 mois ?

### HA5 — Les equipements (produits) sont le signal le plus fort
**Question** : Le nombre et le type de produits souscrits dans les 6 premiers mois sont-ils le meilleur predicteur du PNB a 12 mois ?
**Analyse** :
- PNB moyen par nombre de produits (0, 1, 2, 3, 4+)
- PNB moyen par type de produit (avec/sans chaque produit)
- Correlation entre n_produits et pnb_12m
- Ranking des produits par impact sur le PNB (difference de PNB avec/sans le produit)
- Interaction produits x segment (certains produits sont-ils plus impactants pour certains segments ?)
- Courbe d'equipement : comment le nombre de produits evolue dans les 6 premiers mois
- Analyse de la **domiciliation du salaire** comme variable binaire : PNB moyen avec vs sans domiciliation

### HA6 — La dynamique temporelle du PNB precoce est informative
**Question** : La trajectoire du PNB mensuel (croissante, stable, decroissante) apporte-t-elle un signal au-dela du niveau cumule ?
**Analyse** :
- Classifier les trajectoires en 4 profils : croissant, stable, decroissant, sporadique
- PNB 12 mois moyen par profil de trajectoire
- Pente de la regression lineaire des PNB mensuels (mois 1-6) comme feature
- Comparaison du pouvoir predictif : pnb_cumul seul vs pnb_cumul + tendance
- Identification des "slow starters" (PNB faible mois 1-2 puis forte croissance) vs "early peaks" (PNB eleve mois 1 puis declin)

### HA7 — La saisonnalite d'acquisition impacte le PNB
**Question** : Le trimestre d'acquisition influence-t-il le PNB a 12 mois ?
**Analyse** :
- PNB moyen par trimestre d'acquisition (Q1, Q2, Q3, Q4)
- Test statistique (Kruskal-Wallis)
- Y a-t-il un "effet janvier" (bonnes resolutions, planification financiere) ?
- Y a-t-il un "effet rentree" (septembre, nouveaux emplois) ?
- La saisonnalite est-elle stable entre 2023 et 2025 ?

### HA8 — Les cohortes sont stables dans le temps
**Question** : Le profil PNB des nouveaux clients est-il stable entre les cohortes 2023, 2024 et 2025, ou y a-t-il une derive temporelle ?
**Analyse** :
- PNB moyen par cohorte annuelle
- Distribution du PNB par cohorte (KS test pour comparer les distributions)
- Composition des segments par cohorte (la mix a-t-elle change ?)
- Si derive detectee : le modele doit etre re-entraine frequemment (confirme l'approche trimestrielle)

### HA9 — Le PNB des nouveaux clients est significativement different de celui des clients etablis
**Question** : Les nouveaux clients generent-ils un PNB different (probablement inferieur) des clients etablis sur la meme periode ?
**Analyse** :
- Comparer le PNB annuel des nouveaux clients (12 premiers mois) vs clients etablis (meme annee)
- Distribution comparative (histogrammes superposes)
- Ratio PNB nouveau / PNB etabli par segment
- Cela justifie la necessite d'un modele separe pour les nouvelles acquisitions

### HA10 — La concentration du PNB suit une loi de Pareto
**Question** : Le PNB est-il concentre sur un petit nombre de clients (comme pour le portefeuille etabli) ?
**Analyse** :
- Courbe de Lorenz du PNB 12 mois des nouveaux clients
- Coefficient de Gini
- Quelle part du PNB est generee par le top 10%, top 20% ?
- Comparaison avec la concentration du portefeuille etabli (rappel : H5 du modele existant)

---

## Analyses Exploratoires Complementaires

### AE1 — Profil-type des clients a fort PNB
- Identifier les top 20% de PNB et analyser leur profil : segment, profession, equipement, trajectoire
- Clustering (K-means ou segmentation manuelle) des profils PNB

### AE2 — Clients a PNB nul ou negatif
- Quel % de nouveaux clients a un PNB <= 0 apres 12 mois ?
- Profil de ces clients (segment, equipement, trajectoire)
- Sont-ils "dormants" (aucune activite) ou en perte (couts > revenus) ?

### AE3 — Matrice de correlation complete
- Heatmap de correlation entre toutes les features numeriques
- Identifier les features fortement correlees (> 0.8) pour eviter la multicolinearite
- VIF (Variance Inflation Factor) si necessaire

### AE4 — Analyse des equipements dans le temps
- Comment evolue le nombre de produits entre le mois 1 et le mois 6 ?
- Y a-t-il un "pic d'equipement" au mois 1 (souscription initiale) puis une stabilisation ?
- Le cross-sell precoce (produits ajoutes apres le mois 1) est-il correle au PNB ?

### AE5 — Effet de la date exacte de creation dans le trimestre
- Un client qui rejoint le 1er jour du trimestre a-t-il un PNB different de celui qui rejoint le dernier jour ?
- Cela valide/invalide la pertinence de la feature `mois_anciennete`

---

## Fichiers d'Analyse

| Fichier | Hypotheses couvertes |
|---------|---------------------|
| `ha1_qualite_donnees.py` | HA1 (qualite, completude, coherence) |
| `ha2_ha3_segments_professions.py` | HA2 + HA3 (segments, professions, correlations PNB) |
| `ha4_pnb_precoce_predictif.py` | HA4 (correlation PNB 3-6 mois vs 12 mois) |
| `ha5_equipements_signal.py` | HA5 (produits comme signal principal) |
| `ha6_ha7_dynamique_saisonnalite.py` | HA6 + HA7 (trajectoire PNB, saisonnalite) |
| `ha8_ha9_ha10_cohortes_concentration.py` | HA8 + HA9 + HA10 (stabilite, comparaison, Pareto) |
