# Hypotheses et Analyses — Modele Combine Multi-Produit CLV

Ce document liste **toutes** les hypotheses a valider et les analyses exploratoires a mener pour le modele combine (4 sous-modeles XGBoost + calibration par deciles + CLV 5 ans).

Chaque element est classe comme :
- **HYPOTHESE (H)** : une affirmation verifiable qui, si vraie ou fausse, change une decision d'architecture ou de modele
- **ANALYSE EXPLORATOIRE (AE)** : une investigation descriptive qui informe la comprehension mais ne bloque pas directement une decision

**Architecture de reference** :
- T/T+1/T+3 (fenetrage trimestriel, 4-6 mois observation, 10-12 mois cible)
- 4 sous-modeles XGBoost : Epargne, Investissements, Credit, Autre PNB
- Calibration par deciles sur chaque sous-modele
- CLV = somme(PNB_produit x croissance^t x survie(t) / (1+r)^t) sur 5 ans

---

# PARTIE A — HYPOTHESES ET ANALYSES EXISTANTES (mises a jour)

Ces hypotheses etaient deja definies pour le modele mono-cible. Elles restent valides et doivent etre executees. Les notes sont mises a jour pour reflechir l'architecture multi-produit.

---

## HA1 — Qualite et completude des donnees
**Type** : HYPOTHESE
**Question** : Les donnees sont-elles suffisamment completes et coherentes pour entrainer un modele fiable ?
**Analyse** :
- Taux de valeurs manquantes par colonne et par annee
- Doublons sur client_id (intra-trimestre et inter-trimestre)
- Coherence des dates de creation
- Coherence du PNB (pas de valeurs aberrantes extremes)
- Couverture des equipements
- Distribution des segments et professions
- Distribution de `n_mois_nbi` (10, 11, 12) et `n_mois_observation` (4, 5, 6)

**MAJ multi-produit** : Ajouter les controles de qualite sur les fichiers PNB par produit : taux de NaN par categorie, coherence somme produits vs total.

**Si invalide** : Nettoyage prealable necessaire, certaines cohortes pourraient etre exclues.

**Script** : `ha1_qualite_donnees.py`

---

## HA2 — Le segment est un predicteur du PNB
**Type** : HYPOTHESE
**Question** : Le segment (Mass Affluent, Mass Retail, Mass Retail with Potential) est-il correle au PNB ?
**Analyse** : PNB moyen/median par segment en brut ET PNB/mois, Kruskal-Wallis, boxplots.

**MAJ multi-produit** : Executer l'analyse par categorie de produit. Le segment predit-il davantage le PNB epargne que le PNB credit ? C'est essentiel pour decider si le segment est plus utile a certains sous-modeles.

**Si invalide** : Le segment peut etre retire du jeu de features (poids inutile). Si valide pour certains produits et pas d'autres, le modele XGBoost l'apprendra naturellement mais c'est bon a savoir pour l'interpretabilite.

**Script** : `ha2_ha3_segments_professions.py`

---

## HA3 — La profession est un predicteur du PNB
**Type** : HYPOTHESE
**Question** : La CSP apporte-t-elle un signal predictif au-dela du segment ?
**Analyse** : PNB moyen par profession, interaction segment x profession, Cramer's V.

**MAJ multi-produit** : La profession predit-elle differemment chaque categorie ? Par exemple : un cadre a-t-il un PNB investissement eleve mais un PNB credit faible ? C'est le type de differentiation que les 4 sous-modeles doivent capturer.

**Si invalide** : Retirer la profession des features. Si valide pour certains produits seulement, noter ces interactions pour l'interpretabilite.

**Script** : `ha2_ha3_segments_professions.py`

---

## HA4 — Le PNB d'observation est predictif du PNB total
**Type** : HYPOTHESE (hypothese fondamentale)
**Question** : Le PNB cumule pendant les premiers mois predit-il le PNB total ?

**ATTENTION** : Plancher mecanique de correlation car `pnb_cumul_obs` est un sous-ensemble de `pnb_total`.

**Analyse** :
- Correlation brute `pnb_cumul_obs` vs `pnb_total`
- Correlation nette `pnb_cumul_obs` vs `pnb_remaining`
- R2 progressif (mois 1 a N)

**MAJ multi-produit** : Executer aussi par categorie. Le PNB epargne observe predit-il le PNB epargne restant ? Le PNB credit observe predit-il le PNB credit restant ? La correlation nette pourrait etre tres differente d'un produit a l'autre — certains produits sont peut-etre plus stables (epargne) et d'autres plus volatils (credit).

**Si invalide** : Si la correlation nette est proche de zero pour une categorie, le PNB observe de cette categorie ne devrait pas etre une feature de son sous-modele (il n'apporte que du bruit). Il faudrait s'appuyer davantage sur les features declaratives et equipements pour cette categorie.

**Script** : `ha4_pnb_precoce_predictif.py`

---

## HA5 — Les equipements sont le signal le plus fort
**Type** : HYPOTHESE
**Question** : Le nombre et type de produits au snapshot T+1 sont-ils le meilleur predicteur du PNB ?
**Analyse** : PNB moyen par nombre de produits, PNB par type de produit, ranking des produits par impact, domiciliation du salaire.

**MAJ multi-produit** : Le type de produit souscrit predit-il directement le PNB de la categorie correspondante ? Par exemple, avoir un PEL predit-il le PNB epargne ? Avoir un PEA predit-il le PNB investissement ? Cette analyse est au coeur de la decomposition en 4 modeles.

**Si invalide** : Si les equipements ne sont pas lies aux categories de PNB correspondantes, la decomposition en 4 modeles perd de son interet — les features ne differentient pas bien les sous-cibles.

**Script** : `ha5_equipements_signal.py`

---

## HA6 — La dynamique temporelle du PNB est informative
**Type** : HYPOTHESE
**Question** : La trajectoire du PNB mensuel (croissant, stable, decroissant) ajoute-t-elle un signal au-dela du cumule ?
**Analyse** : Classification en profils, pente de regression, comparaison pouvoir predictif cumule vs cumule + pente.

**MAJ multi-produit** : La dynamique temporelle est-elle differente par produit ? L'epargne est probablement stable, le credit peut avoir un pic au debut (deblocage), les investissements sont volatils. Cela justifie-t-il des features de pente separees par produit ?

**Si invalide** : Ne pas creer de features de pente par produit, utiliser uniquement la pente totale. Si valide pour certains produits : creer `obs_slope_{cat}` uniquement pour les categories ou c'est pertinent.

**Script** : `ha6_ha7_dynamique_saisonnalite.py`

---

## HA7 — La saisonnalite d'acquisition impacte le PNB
**Type** : HYPOTHESE
**Question** : Le trimestre d'entree influence-t-il le PNB ?
**Analyse** : PNB mensuel moyen par trimestre d'acquisition, Kruskal-Wallis, effet janvier/rentree.

**MAJ multi-produit** : La saisonnalite est-elle differente par produit ? Le credit est peut-etre saisonnier (immobilier au printemps), l'investissement aussi (effet janvier). Si la saisonnalite est forte pour certains produits, les sous-modeles correspondants doivent avoir `trimestre_acquisition` comme feature importante.

**Si invalide** : `trimestre_acquisition` peut etre retire des features.

**Script** : `ha6_ha7_dynamique_saisonnalite.py`

---

## HA8 — Les cohortes sont stables dans le temps
**Type** : HYPOTHESE
**Question** : Le profil PNB est-il stable entre cohortes, ou y a-t-il une derive ?
**Analyse** : PNB mensuel moyen par cohorte, KS test, composition des segments par cohorte.

**MAJ multi-produit** : La derive est-elle uniforme ou concentree sur certains produits ? Si le PNB credit derive mais l'epargne est stable, le sous-modele credit doit etre retraine plus souvent. Cela affecte aussi la calibration par deciles — les tables de deciles doivent-elles etre mises a jour a chaque trimestre ?

**Si invalide (derive detectee)** : Confirme l'approche de retraining trimestriel. Potentiellement utiliser des poids temporels (cohortes recentes pesent plus).

**Script** : `ha8_ha9_ha10_cohortes_concentration.py`

---

## HA9 — Nouveaux clients vs clients etablis
**Type** : ANALYSE EXPLORATOIRE
**Question** : Le PNB annualise des nouveaux clients est-il different de celui des clients etablis ?
**Analyse** : Comparaison PNB annualise, distributions, ratio par segment.

**Si confirme** : Justifie un modele separe pour les acquisitions.

**Script** : `ha8_ha9_ha10_cohortes_concentration.py`

---

## HA10 — Concentration de type Pareto
**Type** : ANALYSE EXPLORATOIRE
**Question** : Le PNB suit-il une loi de Pareto (20% des clients generent 80% du PNB) ?
**Analyse** : Courbe de Lorenz, Gini, part du top 10/20%.

**MAJ multi-produit** : La concentration est-elle differente par produit ? Le credit est probablement plus concentre (peu de clients ont un credit immobilier), l'epargne plus diffuse. Cela impacte la taille effective d'echantillon par sous-modele et donc la fiabilite des deciles de calibration.

**Script** : `ha8_ha9_ha10_cohortes_concentration.py`

---

## HA11 — Normalisation du PNB par duree
**Type** : HYPOTHESE
**Question** : Le PNB mensuel moyen est-il constant quel que soit `n_mois_nbi` ?
**Analyse** : Comparer `pnb_mensuel_moyen` pour n_mois_nbi = 10, 11, 12.

**MAJ multi-produit** : Executer par categorie. Certains produits pourraient avoir un PNB mensuel stable (epargne) et d'autres non (credit avec un pic de frais de dossier au mois 1).

**Si invalide** : Le modele doit apprendre une correction non-lineaire, et le PNB mensuel moyen n'est pas une bonne cible alternative.

**Script** : `ha11_normalisation_duree.py`

---

## HA12 — PNB total vs PNB restant comme cible
**Type** : HYPOTHESE
**Question** : Faut-il predire `pnb_total` ou `pnb_remaining` ?
**Analyse** : Comparer R2, MAE, RMSE des deux approches, plancher mecanique.

**MAJ multi-produit** : La question se pose pour chaque sous-modele. Si le PNB epargne observe represente 40% du PNB epargne total mais le PNB credit observe represente 10% du PNB credit total, l'impact du plancher mecanique est tres different. Tester les deux cibles pour chaque categorie.

**Si invalide (pnb_remaining meilleur)** : Utiliser `pnb_{cat}_remaining` comme cible pour les sous-modeles, puis additionner avec `pnb_{cat}_cumul_obs` pour obtenir la prediction totale.

**Script** : `ha12_cible_total_vs_restant.py`

---

## HA13 — Impact de la longueur de la fenetre d'observation
**Type** : HYPOTHESE
**Question** : Les clients avec 4 mois d'observation sont-ils aussi bien predits que ceux avec 6 mois ?
**Analyse** : MAE/RMSE/R2 par tranche de `n_mois_observation`, fiabilite de la pente, comparaison produits au snapshot.

**MAJ multi-produit** : L'impact est-il different par categorie ? Si le credit a besoin de 6 mois pour etre observable mais l'epargne est deja stable a 4 mois, on pourrait envisager des strategies differentes par sous-modele.

**Si invalide** : Clients a 4 mois pourraient necessiter un traitement separe ou une ponderation.

**Script** : `ha13_fenetre_observation.py`

---

# PARTIE B — NOUVELLES HYPOTHESES POUR L'ARCHITECTURE MULTI-PRODUIT

Ces hypotheses sont specifiques a la decomposition en 4 sous-modeles et n'existaient pas dans la version mono-cible.

---

## HP1 — La decomposition en 4 produits est pertinente
**Type** : HYPOTHESE (fondamentale pour l'architecture)
**Question** : Les 4 categories de produit (Epargne, Investissement, Credit, Autre PNB) ont-elles des distributions suffisamment differentes pour justifier des modeles separes ?

**Analyse** :
- Distribution de chaque `pnb_{cat}_total` : moyenne, mediane, ecart-type, skewness, kurtosis
- Part de chaque categorie dans le PNB total (camembert par segment)
- Correlation entre les 4 categories (matrice 4x4)
  - Si les categories sont tres correlees (r > 0.7), des modeles separes risquent d'apprendre des signaux redondants
  - Si elles sont quasi-independantes (r < 0.3), chaque modele capture un signal distinct
- Variabilite intra-categorie vs inter-categorie (ratio des variances)

**Objectif** : Verifier que chaque categorie a un profil statistique propre (pas juste une fraction fixe du total).

**Si invalide** : Si les 4 categories sont proportionnelles au total (chaque client fait 30% epargne, 20% invest, etc.), alors 4 modeles sont redondants — un seul modele sur le total avec une repartition constante suffirait. Les 4 modeles ne se justifient que si la **composition** varie significativement entre clients.

---

## HP2 — Quelle famille de produit contribue combien au PNB ?
**Type** : ANALYSE EXPLORATOIRE
**Question** : Quelle est la contribution relative de chaque categorie au PNB total, et comment varie-t-elle ?

**Analyse** :
- Part moyenne de chaque categorie dans le PNB total : `pnb_{cat}_total / pnb_total`
- Distribution de cette part (histogramme des ratios par client)
- Part par segment : un Mass Affluent a-t-il proportionnellement plus d'investissements ?
- Part par profession : un cadre a-t-il plus de credit (immobilier) ?
- Part par trimestre d'acquisition et par cohorte (evolution dans le temps)
- Top 5 des produits (si la granularite produit est disponible) contribuant au PNB dans chaque categorie

**Objectif** : Comprendre la structure du PNB pour interpreter les predictions des sous-modeles et valider les strategies commerciales.

**Impact** : Si une categorie represente <5% du PNB total pour tous les segments, elle pourrait etre fusionnee avec "Autre" plutot que d'avoir son propre sous-modele.

---

## HP3 — Zero-inflation par categorie de produit
**Type** : HYPOTHESE (critique pour le choix d'algorithme)
**Question** : Quelle proportion de clients a un PNB nul (ou quasi-nul) dans chaque categorie ?

**Analyse** :
- % de clients avec `pnb_{cat}_total = 0` pour chaque categorie
- % de clients avec `pnb_{cat}_total < seuil` (seuil = 10 EUR par exemple)
- Matrice de co-occurrence : si un client a un PNB credit = 0, a-t-il aussi un PNB invest = 0 ?
- Profil des clients "zero" par categorie (segment, profession, equipement)

**Objectif** : Determiner si chaque sous-modele necessite une approche classique ou une approche en deux etapes (zero vs non-zero).

**Si >50% de zeros dans une categorie** : Utiliser un modele en deux etapes :
1. Classifieur (logistic/xgboost) : le client aura-t-il un PNB > 0 dans cette categorie ?
2. Regresseur (xgboost) : si oui, combien ?

**Si <20% de zeros** : Approche directe (regresseur seul), les zeros seront naturellement calibres par les deciles bas.

---

## HP4 — Stabilite de l'equipement dans le temps
**Type** : HYPOTHESE (critique pour la projection CLV)
**Question** : Les produits que le client detient 2-3 mois apres l'acquisition sont-ils representatifs de ce qu'il aura 3 et 5 ans plus tard ?

**Analyse** :
- Pour les cohortes anciennes (Q1 2021 = ~4 ans d'historique) :
  - Comparer les produits detenus au snapshot T+1 (2-3 mois) vs les produits detenus au Stock le plus recent (2025)
  - **Taux de retention produit** : quel % des produits initiaux sont encore detenus 3-4 ans plus tard ?
  - **Taux d'acquisition produit** : combien de produits nouveaux sont acquis entre T+1 et T+4 ans ?
  - **Ratio stabilite** = produits_communs / max(produits_T1, produits_T4)
- Segmenter par type de produit :
  - Produits "fondation" (compte courant, carte) : retention proche de 100% ?
  - Produits "croissance" (PEL, assurance vie) : acquis progressivement ?
  - Produits "event-driven" (credit immobilier) : arrivent a un moment precis ?
- Ratio produits_T1 / produits_T4 par segment et profession

**Objectif** : Si l'equipement est tres stable, les features d'equipement a T+1 sont un excellent proxy a long terme. Si l'equipement evolue significativement, les predictions a 5 ans basees sur l'equipement initial sont moins fiables — il faudrait modeliser la trajectoire d'equipement.

**Si invalide (equipement evolue beaucoup)** : Les facteurs de croissance dans la CLV doivent integrer l'enrichissement progressif de l'equipement. La CLV sera sous-estimee si on suppose un equipement fixe.

**Si valide (equipement stable >80%)** : Le snapshot T+1 est un bon proxy, les projections CLV sont plus fiables.

---

## HP5 — Le client acquiert-il 90% de ses produits dans les premiers mois ?
**Type** : HYPOTHESE (liee a HP4, plus specifique)
**Question** : A quel moment le client a-t-il souscrit l'essentiel de son equipement long terme ?

**Analyse** :
- Pour les cohortes anciennes :
  - Courbe d'acquisition cumulee des produits : nombre moyen de produits detenus a M+1, M+2, M+3, M+6, M+12, M+24, M+36, M+48
  - A quel mois atteint-on 50%, 75%, 90% du nombre de produits final ?
  - Cette courbe est-elle differente par segment ? (un Mass Affluent s'equipe-t-il plus vite ?)
  - Y a-t-il un "plateau" clair apres lequel le client n'ajoute presque plus de produits ?
- Ventiler par type de produit :
  - Produits de base (ouverts a J0) vs produits progressifs (ouverts apres M+6)
  - Delai moyen de souscription pour chaque type de produit

**Objectif** : Determiner si notre snapshot a T+1 (2-6 mois) capture l'essentiel du potentiel d'equipement ou seulement le debut.

**Si 90% des produits sont acquis dans les 6 premiers mois** : Notre snapshot est excellent, les sous-modeles ont presque toute l'information equipement.

**Si seulement 50% des produits sont acquis dans les 6 premiers mois** : Le snapshot sous-estime le potentiel. Il faudrait :
- Ajouter un modele d'equipement futur (predire quels produits le client souscrira apres T+1)
- Ou accepter que les projections de PNB par produit pour les annees 2-5 incluent implicitement l'effet des futurs produits via les facteurs de croissance

---

## HP6 — Les facteurs de croissance par produit sont stables et estimables
**Type** : HYPOTHESE (critique pour la CLV)
**Question** : Le PNB par categorie croit-il de facon previsible annee apres annee ?

**Analyse** :
- Pour les cohortes anciennes (Q1-Q4 2021) :
  - Calculer le PNB annuel par categorie pour chaque annee post-acquisition : Annee 1, Annee 2, Annee 3, Annee 4
  - Taux de croissance annuel par categorie : g_{cat} = PNB_{annee N+1} / PNB_{annee N}
  - Ce taux est-il constant (croissance geometrique) ou decroissant (convergence) ?
  - Ecart-type du taux de croissance (est-il stable ou tres variable ?)
- Comparer les taux de croissance entre segments
- Le taux de croissance est-il correle au PNB initial (les clients a fort PNB croissent-ils plus vite ?)
- Y a-t-il des patterns specifiques ?
  - Epargne : croissance reguliere (accumulation)
  - Credit : decroissance (amortissement) ou stabilite (credit revolving)
  - Investissements : volatil (depend des marches)
  - Autre PNB : lie a l'activite transactionnelle

**Objectif** : Calibrer les facteurs GROWTH dans la formule CLV = somme(PNB x g^t x S(t) / (1+r)^t). Si les facteurs de croissance sont stables, la formule est robuste. Sinon, il faut des facteurs conditionnels (par segment, par niveau de PNB initial).

**Si invalide (facteurs instables ou non-geometriques)** :
- Utiliser des facteurs de croissance variables dans le temps plutot que constants
- Ou modeliser directement le PNB multi-annuel (quand suffisamment de donnees seront disponibles)
- Tester une approche log-lineaire : ln(PNB_annuel) = a + b*t + features

---

## HP7 — Le PNB par produit est-il correle entre categories ?
**Type** : HYPOTHESE
**Question** : Un client a fort PNB epargne a-t-il aussi un fort PNB investissement ? Ou les categories sont-elles substituables ?

**Analyse** :
- Matrice de correlation des 4 cibles `pnb_{cat}_total` (Pearson et Spearman)
- Scatter plots croises (epargne vs invest, epargne vs credit, etc.)
- Y a-t-il des clusters naturels ?
  - "Epargnant pur" : fort PNB epargne, faible invest/credit
  - "Investisseur" : fort PNB invest, faible epargne
  - "Emprunteur" : fort PNB credit, faible epargne
  - "Complet" : fort dans toutes les categories
- Correlation conditionnelle par segment

**Objectif** : Comprendre les interactions entre sous-modeles. Si les categories sont substituables (epargne OU invest, pas les deux), les predictions des sous-modeles doivent reflechir cette exclusivite. Si elles sont complementaires, un client "complet" est previsible.

**Si forte correlation positive** : Les 4 sous-modeles captent un seul facteur latent ("richesse du client"). La decomposition reste utile pour l'interpretabilite mais pas pour la precision. La somme des 4 modeles risque de surestimer pour les clients moyens.

**Si correlation faible ou negative** : Chaque sous-modele capture un signal independant. La decomposition est tres justifiee.

---

## HP8 — La calibration par deciles ameliore les predictions
**Type** : HYPOTHESE
**Question** : Le lissage par deciles reduit-il l'erreur de prediction par rapport aux predictions brutes du XGBoost ?

**Analyse** :
- Pour chaque sous-modele, comparer en walk-forward :
  - Predictions brutes XGBoost vs predictions calibrees par deciles
  - MAE, RMSE, et surtout l'erreur de calibration (predicted vs actual par bin)
- Reliability diagram : predictions brutes vs calibrees
- Le gain de calibration est-il uniforme sur toute la distribution ou concentre sur les extremes ?
- Comparer 10 deciles vs 20 vigintiles vs 5 quintiles

**Objectif** : Justifier (ou invalider) la couche de calibration. Si les predictions brutes du XGBoost sont deja bien calibrees, la couche est inutile et ajoute du bruit.

**Si invalide** : Ne pas utiliser la calibration par deciles, utiliser les predictions brutes.

**Si valide** : Determiner le nombre optimal de bins et verifier la monotonie.

---

## HP9 — Les tables de deciles sont stables dans le temps
**Type** : HYPOTHESE
**Question** : Les moyennes par decile calculees sur les donnees d'entrainement sont-elles encore valables 6-12 mois plus tard ?

**Analyse** :
- Pour chaque sous-modele :
  - Calculer les tables de deciles sur les folds d'entrainement successifs
  - Comparer les moyennes par decile entre folds (ex : la moyenne du decile 7 du modele Epargne est-elle stable entre Q1 2022 et Q1 2023 ?)
  - Taux de derive : ecart moyen entre les tables de deciles consecutives
- Visualiser l'evolution des seuils de deciles dans le temps
- Y a-t-il des categories plus stables que d'autres ?

**Objectif** : Determiner la frequence de mise a jour des tables de deciles. Si elles derivent vite, il faut les recalibrer a chaque trimestre (aligne avec le retraining). Si elles sont stables, une calibration semestrielle suffit.

**Si invalide (derive rapide)** : Recalibrer les tables a chaque retraining. Potentiellement utiliser des fenetres glissantes pour le calcul des moyennes de deciles.

---

## HP10 — Les taux de survie sont independants du mix produit
**Type** : HYPOTHESE (critique pour la formule CLV)
**Question** : La probabilite de rester client est-elle la meme quel que soit le mix de produits, ou certains produits "ancrent" le client ?

**Analyse** :
- Taux de churn (ou de depart) observe par profil d'equipement :
  - Client avec credit immobilier vs sans
  - Client avec 5+ produits vs 1-2 produits
  - Client avec domiciliation de salaire vs sans
- Courbe de survie (Kaplan-Meier) par nombre de produits et par categorie dominante
- Regression de Cox : le nombre de produits ou le type de produit est-il un facteur significatif de survie ?
- Interaction : un client "ancre" (credit + domiciliation) a-t-il un taux de survie bien superieur ?

**Objectif** : Determiner si la formule CLV doit utiliser un taux de survie S(t) unique ou un taux de survie conditionnel au mix produit.

**Si invalide (la survie depend du mix)** :
- Utiliser S(t | equipement) au lieu de S(t) dans la formule CLV
- Cela signifie que les clients a fort PNB (plus de produits) ont aussi une meilleure retention, ce qui amplifie la CLV (double avantage)
- Le modele de retention existant devrait integrer l'equipement comme feature

**Si valide** : Un seul taux de survie S(t) par segment suffit.

---

## HP11 — La somme des 4 sous-modeles est meilleure que le modele unique
**Type** : HYPOTHESE (justification de l'architecture)
**Question** : Predire 4 composantes separees puis les sommer donne-t-il une meilleure prediction du PNB total que de predire directement le total ?

**Analyse** :
- Entrainer le modele baseline (XGBoost unique sur pnb_total) avec calibration par deciles
- Entrainer les 4 sous-modeles avec calibration
- Comparer sur les memes folds de validation walk-forward :
  - MAE(somme des 4) vs MAE(modele unique)
  - R2(somme des 4) vs R2(modele unique)
  - Correlation de rang (Spearman)
  - Lift dans le top decile (les meilleurs clients sont-ils mieux identifies ?)
- Analyser les erreurs : ou la decomposition gagne et ou elle perd ?

**Objectif** : Si la decomposition n'ameliore pas (ou degrade) la precision, elle ne se justifie que par l'interpretabilite. Il faut que l'equipe accepte explicitement ce tradeoff.

**Si invalide** : Garder la decomposition pour l'interpretabilite mais rapporter que le gain n'est pas en precision. Envisager un "ensemble" : (modele unique + somme des 4) / 2.

---

## HP12 — L'horizon de 5 ans est justifie
**Type** : HYPOTHESE
**Question** : Le PNB des nouveaux clients se stabilise-t-il dans les 5 ans, ou continue-t-il a evoluer significativement apres ?

**Analyse** :
- Pour les cohortes anciennes (Q1 2021 = ~4 ans d'historique) :
  - Courbe du PNB cumule au fil des annees
  - Le PNB annuel de l'annee 4 est-il significativement different de celui de l'annee 3 ?
  - Taux de croissance marginal : (PNB_annee_N - PNB_annee_N-1) / PNB_annee_N-1
  - Ce taux de croissance marginal converge-t-il vers zero ? Si oui, a quel rythme ?
- Part du PNB total (cumule sur toute la duree observee) realisee a 1 an, 2 ans, 3 ans, 4 ans
- Y a-t-il un "effet plateau" visible ?

**Objectif** : Valider que 5 ans capturent l'essentiel de la CLV, ou s'il faut un horizon plus long (7 ans, 10 ans). Un horizon trop court sous-estime la CLV des "investisseurs" qui montent en gamme lentement.

**Si invalide (pas de plateau a 5 ans)** : Etendre l'horizon a 7 ou 10 ans. Les facteurs de croissance deviennent encore plus importants car ils impactent une plus longue periode.

---

## HP13 — Le PNB par produit est predictible separement
**Type** : HYPOTHESE
**Question** : Chacune des 4 categories de PNB a-t-elle un R2 raisonnable (>0.10) quand on la predit separement ?

**Analyse** :
- Pour chaque sous-modele, calculer le R2 en walk-forward
- Comparer les R2 entre categories : quelle categorie est la plus/moins predictible ?
- Analyser les features les plus importantes par sous-modele (feature importance XGBoost)
- Les features importantes sont-elles differentes entre sous-modeles ? (C'est la justification de la decomposition : si les memes features dominent partout, un modele unique suffit)

**Objectif** : Identifier les categories "faciles" et "difficiles" a predire. Si une categorie a un R2 < 0.05, elle apporte surtout du bruit a la CLV.

**Si une categorie est impredictible** : Envisager de la traiter comme constante (PNB moyen du segment) plutot que de la predire. Cela reduit la variance d'erreur sans biais.

---

# PARTIE C — NOUVELLES ANALYSES EXPLORATOIRES

Ces analyses sont descriptives et informent la comprehension du probleme sans bloquer une decision directe.

---

## AE1 — Profil-type des clients a fort PNB (MAJ)
**Type** : ANALYSE EXPLORATOIRE
**Analyse** :
- Top 20% de PNB mensuel moyen : segment, profession, equipement, trajectoire
- **MAJ** : Decomposer le profil par produit. Le top 20% global est-il le top 20% dans chaque categorie ?
- Existe-t-il des clients "star epargne mais zero credit" et vice versa ?
- Clustering (K-means sur les 4 composantes PNB) pour identifier les archetype

**Objectif** : Identifier les typologies de clients pour la strategie commerciale.

---

## AE2 — Clients a PNB nul ou negatif (MAJ)
**Type** : ANALYSE EXPLORATOIRE
**Analyse** :
- % de clients avec PNB total <= 0
- **MAJ** : Decomposer — un client peut avoir PNB total > 0 mais PNB credit < 0 (couts de risque). Analyser les PNB negatifs par categorie.
- Profil des clients dormants vs en perte

**Objectif** : Comprendre la queue gauche de la distribution et son impact sur les deciles bas.

---

## AE3 — Matrice de correlation complete (MAJ)
**Type** : ANALYSE EXPLORATOIRE
**Analyse** :
- Heatmap incluant les 4 cibles produit + toutes les features
- **MAJ** : Identifier quelles features sont correlees a quelles cibles produit
- VIF si necessaire
- Correlation entre features d'observation par produit et cibles par produit (bloc diagonal ?)

**Objectif** : Detecter la multicolinearite et comprendre la structure du signal.

---

## AE4 — Trajectoire d'equipement dans le temps
**Type** : ANALYSE EXPLORATOIRE (anciennement DEPRECATED, maintenant reactive)
**Question** : Comment l'equipement evolue-t-il au fil des annees post-acquisition ?

**Analyse** :
- Pour les cohortes anciennes :
  - Nombre moyen de produits a M+3, M+6, M+12, M+24, M+36, M+48
  - Taux de souscription par type de produit en fonction de l'anciennete
  - Y a-t-il des "vagues" d'equipement (ex : credit immobilier a M+18 en moyenne) ?
  - Taux de resiliation par type de produit et par anciennete
- Courbes de survie par produit (combien de temps un produit souscrit reste-t-il actif ?)

**Objectif** : Informer HP4 et HP5. Necessaire pour les cohortes anciennes uniquement.

**Note** : Cette analyse etait marquee DEPRECATED car le modele mono-cible n'utilisait qu'un snapshot. Elle est reactive car la projection CLV sur 5 ans necessite de comprendre l'evolution de l'equipement.

---

## AE5 — Effet de la position dans le trimestre (conserve)
**Type** : ANALYSE EXPLORATOIRE
**Analyse** :
- PNB par mois d'arrivee dans le trimestre
- Validation de la feature `n_mois_observation` et `n_mois_nbi`
- Lien avec HA11 et HA13

---

## AE6 — Decomposition de la variance du PNB total
**Type** : ANALYSE EXPLORATOIRE
**Question** : Quelle part de la variance du PNB total est expliquee par chaque composante produit ?

**Analyse** :
- Decomposition de la variance : Var(PNB_total) = sum(Var(PNB_cat)) + 2 * sum(Cov(PNB_i, PNB_j))
- Part de variance expliquee par chaque categorie
- Part de covariance (les categories co-varient-elles positivement ?)
- R2 d'une regression du PNB total sur les 4 composantes (devrait etre ~1.0 si la decomposition est exhaustive)

**Objectif** : Comprendre la structure de risque. Si la covariance est forte, la diversification produit ne reduit pas le risque de prevision.

---

## AE7 — Analyse des residus de la decomposition
**Type** : ANALYSE EXPLORATOIRE
**Question** : La somme des 4 categories correspond-elle exactement au PNB total ?

**Analyse** :
- Calculer le residu : `residual = pnb_total - (pnb_epargne + pnb_invest + pnb_credit + pnb_autre)`
- Distribution du residu (devrait etre centree sur zero)
- % de clients avec residu > 5% du PNB total
- Si residus non nuls : identifier l'origine (arrondis, categorisation manquante, timing)

**Objectif** : Valider que la decomposition est exhaustive. Si des residus significatifs existent, il faut les attribuer ou creer une 5e categorie.

---

## AE8 — Sequences d'equipement et impact sur le PNB
**Type** : ANALYSE EXPLORATOIRE
**Question** : L'ordre dans lequel le client souscrit ses produits a-t-il un impact sur le PNB ?

**Analyse** :
- Identifier les sequences frequentes d'equipement :
  - Compte courant -> Carte -> Epargne -> Assurance -> Credit
  - Compte courant -> Credit immobilier -> Assurance -> Epargne
  - etc.
- PNB moyen par sequence frequente
- Y a-t-il une "sequence optimale" associee au PNB le plus eleve ?
- Le canal d'acquisition influence-t-il la sequence (digital vs agence) ?

**Objectif** : Informer les recommandations commerciales (quel produit proposer ensuite ?) et comprendre si la sequence est predictive du PNB long terme.

---

## AE9 — Impact du canal d'acquisition par categorie de produit
**Type** : ANALYSE EXPLORATOIRE
**Question** : Les clients acquis par le digital et par les agences ont-ils le meme mix produit ?

**Analyse** :
- Composition du PNB par canal d'acquisition (digital vs agence)
- Les clients digitaux souscrivent-ils moins de credit (pas de conseil en agence) ?
- Les clients agence souscrivent-ils plus d'investissements (conseil personnalise) ?
- PNB moyen par categorie et par canal

**Objectif** : Comprendre si le canal influence la composition du PNB, ce qui impacte les predictions des sous-modeles et la strategie d'acquisition.

---

## AE10 — Taux de marge implicite par categorie
**Type** : ANALYSE EXPLORATOIRE
**Question** : Peut-on estimer les taux de marge (t_s, t_i, t_c) a partir des donnees ?

**Analyse** :
- Si on dispose des encours ET du PNB : `marge_implicite = PNB / encours_moyen`
- Comparer nos marges implicites aux marges BCEF (si connues)
- Les marges sont-elles stables dans le temps ou en compression ?
- Y a-t-il des differences de marge par segment client ?

**Objectif** : Informer la formule CLV si on passe un jour a l'approche "encours x marge" (Option C). Permet aussi de verifier la coherence des donnees PNB par produit.

---

# PARTIE D — RECAPITULATIF ET PRIORITES

## Ordre d'execution recommande

### Priorite 1 — Prerequis (bloquer l'architecture si invalide)
| ID | Question cle | Decision impactee |
|----|-------------|-------------------|
| HP1 | Les 4 categories sont-elles distinctes ? | Architecture 4 modeles vs 1 modele |
| HP3 | Combien de zeros par categorie ? | Approche 1-etape vs 2-etapes par sous-modele |
| AE7 | La decomposition est-elle exhaustive ? | Fiabilite de la decomposition |
| HA1 | Qualite des donnees produit ? | Faisabilite de l'approche |

### Priorite 2 — Calibration de la CLV
| ID | Question cle | Decision impactee |
|----|-------------|-------------------|
| HP6 | Facteurs de croissance stables ? | Parametres de la formule CLV |
| HP4 | L'equipement est-il stable dans le temps ? | Fiabilite des projections 5 ans |
| HP5 | 90% des produits acquis dans les 6 premiers mois ? | Qualite du snapshot T+1 |
| HP12 | Horizon 5 ans justifie ? | Duree de la projection CLV |
| HP10 | La survie depend-elle du mix produit ? | Formule CLV (S(t) vs S(t|mix)) |

### Priorite 3 — Validation du modele
| ID | Question cle | Decision impactee |
|----|-------------|-------------------|
| HP11 | 4 modeles > 1 modele ? | Justification finale de l'architecture |
| HP13 | Chaque categorie est-elle predictible ? | Nombre effectif de sous-modeles |
| HP8 | La calibration par deciles aide-t-elle ? | Couche de calibration |
| HP9 | Les tables de deciles sont-elles stables ? | Frequence de recalibration |
| HP7 | Les categories sont-elles correlees ? | Interpretation des predictions |

### Priorite 4 — Existant (deja code, a re-executer avec donnees produit)
| ID | Fichier | Statut |
|----|---------|--------|
| HA1-HA13 | `ha1_*.py` a `ha13_*.py` | Adapter pour donnees multi-produit |
| AE1-AE5 | Integres dans les scripts ci-dessus | MAJ pour decomposition |

### Priorite 5 — Approfondissement
| ID | Question cle |
|----|-------------|
| HP2 | Contribution relative de chaque categorie |
| AE6 | Decomposition de la variance |
| AE8 | Sequences d'equipement |
| AE9 | Impact du canal par produit |
| AE10 | Taux de marge implicites |

---

## Scripts a creer ou mettre a jour

| Script | Hypotheses couvertes | Statut |
|--------|---------------------|--------|
| `ha1_qualite_donnees.py` | HA1 + controles produit | A mettre a jour |
| `ha2_ha3_segments_professions.py` | HA2, HA3 + ventilation par produit | A mettre a jour |
| `ha4_pnb_precoce_predictif.py` | HA4 + correlation par produit | A mettre a jour |
| `ha5_equipements_signal.py` | HA5 + lien equipement/categorie PNB | A mettre a jour |
| `ha6_ha7_dynamique_saisonnalite.py` | HA6, HA7 + dynamique par produit | A mettre a jour |
| `ha8_ha9_ha10_cohortes_concentration.py` | HA8, HA9, HA10 + concentration par produit | A mettre a jour |
| `ha11_normalisation_duree.py` | HA11 + normalisation par produit | A mettre a jour |
| `ha12_cible_total_vs_restant.py` | HA12 + par produit | A mettre a jour |
| `ha13_fenetre_observation.py` | HA13 + par produit | A mettre a jour |
| `hp1_decomposition_produits.py` | HP1, HP2, HP3, HP7, AE6, AE7 | **A creer** |
| `hp4_hp5_stabilite_equipement.py` | HP4, HP5, AE4, AE8 | **A creer** |
| `hp6_facteurs_croissance.py` | HP6, HP12 | **A creer** |
| `hp8_hp9_calibration.py` | HP8, HP9 | **A creer** |
| `hp10_survie_mix_produit.py` | HP10 | **A creer** |
| `hp11_hp13_4modeles_vs_1.py` | HP11, HP13 | **A creer** |
| `ae9_ae10_canal_marges.py` | AE9, AE10 | **A creer** |
