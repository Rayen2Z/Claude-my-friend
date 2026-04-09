# Justification des Choix — Modele CLV Nouvelles Acquisitions

Ce document defend chaque choix structurel, logique et technique retenu dans la conception du modele CLV pour les nouveaux clients.

---

## 1. Choix du modele : GradientBoosting (sklearn)

**Choix** : `GradientBoostingRegressor` pour le PNB, `GradientBoostingClassifier` pour la retention.

**Pourquoi pas XGBoost / LightGBM ?**
- sklearn est deja la librairie standard du projet (coherence avec `v0_churn_model.py`)
- Pas de dependance supplementaire a installer dans l'environnement SAP BI / production
- Les performances sont comparables sur des datasets de cette taille (2k-20k lignes)
- XGBoost/LightGBM brillent sur des datasets > 100k lignes avec des centaines de features ; ici le gain serait marginal
- Si necessaire, migrer vers LightGBM est trivial (meme API fit/predict)

**Pourquoi pas un reseau de neurones ?**
- Le dataset est trop petit (quelques milliers de nouveaux clients par an)
- Les features sont tabulaires (pas de sequences, pas d'images)
- Le gradient boosting domine systematiquement les reseaux de neurones sur les donnees tabulaires de petite/moyenne taille (cf. benchmarks Kaggle, papier "Why do tree-based models still outperform deep learning on tabular data?" — Grinsztajn et al., 2022)
- L'interpretabilite est critique dans un contexte bancaire (feature importances, SHAP)

**Pourquoi pas la regression lineaire / logistique ?**
- Les relations entre features et PNB ne sont pas lineaires (effet de seuil du revenu, interactions age x produits)
- Le gradient boosting capture automatiquement les non-linearites et les interactions sans avoir a les specifier manuellement

---

## 2. Perte Huber pour la regression PNB

**Choix** : `loss='huber'` au lieu de `loss='squared_error'`.

**Justification** :
- La distribution du PNB est fortement asymetrique (quelques clients a tres haut PNB, longue queue a droite)
- La perte carree (MSE) est tres sensible aux outliers : un seul client a PNB = 50,000 EUR tire toutes les predictions vers le haut
- La perte Huber est un compromis : quadratique pour les petites erreurs, lineaire pour les grandes. Elle est robuste aux outliers tout en restant differentiable
- Alternative testee : predire `log(PNB+1)` avec MSE. Si les resultats sont meilleurs en MAE, utiliser cette approche. Les deux sont valides

---

## 3. Modele unifie (pas 4 sous-modeles par famille)

**Choix** : Un seul modele PNB, un seul modele retention. Pas de sous-modeles par famille de produits.

**Justification pour la Proposition A** :
- Au Jour 0, on ne connait que les produits souscrits, pas comment le PNB se decomposera entre familles
- Avec 2k-10k nouveaux clients par an, diviser en 4 sous-modeles donnerait 500-2500 exemples par modele : insuffisant pour un gradient boosting fiable
- Les indicateurs de famille de produits (`fam_banque_quotidienne`, `fam_credit`, etc.) servent de features d'entree — le modele apprend leur impact sur le PNB total
- Complexite operationnelle : 4 sous-modeles = 4x plus de maintenance, de monitoring, de retraining

**Nuance pour la Proposition B Phase 2** :
- Avec des donnees comportementales precoces (3 mois de PNB par famille), il devient viable de predire le PNB par famille. C'est une option V2, a tester si le modele unifie manque de precision

---

## 4. Modeles separes Phase 1 / Phase 2 (pas un seul modele)

**Choix** : Deux modeles distincts plutot qu'un seul avec des features manquantes.

**Pourquoi pas un seul modele avec NaN pour les features comportementales en Phase 1 ?**
- Le gradient boosting gere mal les NaN massifs (toute une famille de features absentes)
- Un modele entraine sur un mix de features presentes/absentes optimise un compromis qui n'est ideal pour aucune des deux situations
- Deux modeles specialises sont chacun optimaux pour leur contexte :
  - Phase 1 : optimise sur ~25 features declaratives
  - Phase 2 : optimise sur ~40 features (declaratives + comportementales)
- L'approche a deux modeles est aussi plus interpretable : on peut mesurer precisement le gain de precision entre Phase 1 et Phase 2

---

## 5. Decoupage temporel train/test

**Choix** : Cohorte la plus ancienne = train, cohorte la plus recente = test.

**Justification** :
- Reproduit le deploiement reel : on entraine sur les clients passes pour predire les futurs
- Evite le data leakage temporel (un split aleatoire melangerait les cohortes)
- Capture la non-stationnarite : si les profils des nouveaux clients evoluent (ex: plus de clients digitaux en 2024 vs 2023), le test le revelera
- C'est la meme approche que dans `v0_churn_model.py` (coherence du projet)

---

## 6. Fenetre d'observation de 12 mois

**Choix** : La cible est le PNB et le churn a 12 mois.

**Pourquoi 12 mois et pas 6 ou 24 ?**
- 12 mois est le cycle naturel d'une relation bancaire (annualisation du PNB, cotisations annuelles carte/assurance)
- 6 mois serait trop court : un client avec un credit immobilier met souvent 3-6 mois a generer du PNB significatif
- 24 mois reduirait la taille du jeu d'entrainement (on ne peut utiliser que les cohortes avec 24 mois de recul)
- 12 mois correspond a la definition de "nouveau client" retenue
- Apres 12 mois, le client bascule vers le modele etabli qui a deja un horizon de 3 ans

---

## 7. Enrichissement STATEC (Luxembourg, pas INSEE)

**Choix** : Donnees geographiques du STATEC et non de l'INSEE.

**Justification** :
- La banque est au Luxembourg. La majorite des clients sont residents luxembourgeois ou frontaliers (France, Belgique, Allemagne)
- Les donnees INSEE (Filosofi, Recensement) couvrent uniquement la France et ne sont pas pertinentes pour des communes luxembourgeoises
- Le STATEC (statistiques.public.lu) fournit des donnees equivalentes par commune luxembourgeoise : revenu median, densite de population, structure demographique
- data.public.lu (portail open data du Luxembourg) offre des tables de correspondance code postal / commune

**Variables geographiques retenues** :
- `revenu_median_commune` : indicateur de richesse locale (correle au PNB potentiel)
- `densite_population` : urbain vs rural (impact sur les besoins bancaires)
- `taux_chomage_canton` : contexte economique local
- `pct_frontaliers_commune` : specificite luxembourgeoise — les frontaliers ont des profils de PNB distincts (salaires souvent plus eleves, besoins de credit immobilier transfrontalier)

---

## 8. Traitement des frontaliers

**Choix** : Feature `est_frontalier` (binaire) + `nationalite` (one-hot) + interaction `frontalier_x_revenu`.

**Justification** :
- Au Luxembourg, ~45% de la main-d'oeuvre est frontaliere. C'est une realite structurelle du marche
- Les frontaliers ont des profils financiers specifiques : revenus souvent superieurs (avantage fiscal), besoins de produits transfrontaliers, mobilite plus elevee (risque de churn si changement d'employeur)
- La nationalite ajoute un signal : les frontaliers portugais, francais et allemands ont des comportements bancaires differents
- L'interaction `frontalier_x_revenu` capture le fait qu'un frontalier a haut revenu a un profil CLV tres different d'un resident a meme revenu

---

## 9. Fenetre de lissage de 5 mois (Proposition B)

**Choix** : Blending lineaire entre les mois 10 et 14 pour la transition Phase 2 -> modele etabli.

**Pourquoi pas une bascule instantanee a 12 mois ?**
- Une bascule dure creee une discontinuite dans la CLV : le client passe d'un score nouveau-client a un score etabli du jour au lendemain, potentiellement avec un ecart important
- Les equipes commerciales et le reporting ne supportent pas bien les sauts brusques de CLV
- Au mois 12, les 4 trimestres de donnees comportementales sont disponibles mais le Q4 est tres frais — le modele etabli n'a pas encore une lecture stable du client
- Au mois 14, le Q4 a 2 mois de recul — prediction plus fiable

**Pourquoi lineaire ?**
- Simple a expliquer, simple a implementer, simple a auditer
- Un schema non-lineaire (sigmoid, exponentiel) n'apporterait pas de gain mesurable pour 4 mois de transition
- Les poids sont transparents : mois 10 = 100% nouveau, mois 12 = 50/50, mois 14 = 100% etabli

---

## 10. Domiciliation du salaire comme signal cle

**Choix** : `a_domiciliation_salaire` est identifie comme le predicteur le plus fort en Phase 2.

**Justification** :
- Un client qui domicilie son salaire utilise la banque comme banque principale (vs compte secondaire)
- Cela implique : volume de transactions eleve, utilisation de la carte au quotidien, prelevements automatiques, assurances liees au compte
- Dans les banques de detail, la domiciliation du salaire est le meilleur predicteur connu de :
  1. **PNB futur** : un client principal genere 3-5x le PNB d'un client secondaire
  2. **Retention** : quitter une banque principale implique de migrer les prelevements, la carte, etc. — friction elevee
- C'est aussi un signal d'action commerciale : si un client n'a pas domicilie son salaire au mois 3, c'est le moment d'intervenir (appel conseiller, offre promotionnelle)

---

## 11. Style de code : cellules notebook, pas de POO

**Choix** : Fichiers structures en blocs `# %%` independants, fonctions simples, pas de classes.

**Justification** :
- L'utilisateur travaille en Jupyter Notebook pour le prototypage et la validation
- Les blocs `# %%` sont compatibles avec Jupyter, VS Code (Python Interactive), et PyCharm
- Chaque cellule peut etre executee independamment pour le debug et l'exploration
- La programmation orientee objet (classes, heritage) ajoute une couche d'abstraction inutile pour un pipeline de data science exploratoire
- Les fonctions sont suffisantes pour la reutilisation (ex: `score_phase1()`, `score_phase2()`)
- Coherence avec le reste du projet (`simplified/` utilise le meme style)

---

## 12. Facteur de croissance PNB (GROWTH_FACTOR = 1.10)

**Choix** : Le PNB predit pour l'annee 2 = PNB annee 1 x 1.10 (croissance de 10%).

**Justification** :
- Les nouveaux clients approfondissent generalement leur relation avec la banque au fil du temps : ajout de produits, augmentation du volume de transactions
- Le facteur de 1.10 est une estimation conservative basee sur les patterns observes dans les banques de detail (la premiere annee est souvent sous-representative du potentiel reel)
- Ce facteur doit etre calibre sur les donnees reelles : calculer le ratio PNB annee 2 / PNB annee 1 pour les cohortes historiques
- Si les donnees montrent un facteur different, il suffit de changer la constante `GROWTH_FACTOR`

---

## 13. Taux d'actualisation de 5%

**Choix** : `DISCOUNT_RATE = 0.05` (5% annuel).

**Justification** :
- Standard dans les modeles CLV bancaires
- Represente le cout d'opportunite du capital (la banque pourrait investir cet argent ailleurs)
- Coherent avec le modele CLV existant (`simplified/ROI_simulation.py` utilise le meme taux)
- Un taux plus eleve (8-10%) serait plus conservateur mais reduirait la CLV des annees 2-3, diminuant l'importance de la retention dans le modele

---

## 14. Taux de retention etabli a 0.95

**Choix** : Apres la premiere annee, les nouveaux clients survivants ont un taux de retention annuel de 95% (equivalent aux clients etablis).

**Justification** :
- Les resultats H3 du modele existant montrent des taux de survie de [0.92, 0.86, 0.82] pour le portefeuille global
- Le taux annuel implicite entre les annees est : 0.86/0.92 = 0.935 et 0.82/0.86 = 0.953
- 0.95 est la moyenne arrondie, coherente avec les donnees observees
- Les nouveaux clients qui survivent a la premiere annee (la plus risquee) se comportent ensuite comme les clients etablis — c'est un resultat classique en analyse de survie bancaire ("infant mortality" effect)
