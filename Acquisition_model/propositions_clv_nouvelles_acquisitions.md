# Modele CLV pour les Nouvelles Acquisitions — Deux Propositions

## Contexte

Le modele CLV existant predit le PNB (Produit Net Bancaire) sur 3 ans pour les **clients etablis** en utilisant des donnees comportementales trimestrielles (PNB, transactions, produits, activite). Il integre un sous-modele de retention : `CLV = Somme PNB(t) * retention^t * facteur_actualisation^t`.

**Probleme** : Les nouveaux clients (venant de rejoindre la banque) n'ont **aucun historique**. Nous disposons uniquement de :
- Donnees demographiques : age, genre, adresse/commune, situation familiale
- Donnees declaratives : tranche de revenu, categorie socio-professionnelle (CSP)
- Produits souscrits a l'entree en relation (pas de montants)
- Canal d'acquisition : digital (app/web) vs agence
- **Capacite look-alike** : nous POUVONS reconstituer les profils des clients existants au moment de leur propre entree en relation et observer leur trajectoire PNB reelle par la suite

**Objectif** : Concevoir un modele qui predit la CLV des nouveaux clients des le Jour 0, puis effectue une transition vers le modele etabli lorsque suffisamment de donnees comportementales sont disponibles.

**Note importante** : La banque etant basee au **Luxembourg**, les donnees d'enrichissement geographique proviennent du **STATEC** (Institut national de la statistique et des etudes economiques du Grand-Duche de Luxembourg) et non de l'INSEE francais. La clientele est majoritairement luxembourgeoise, avec une part significative de travailleurs frontaliers (France, Belgique, Allemagne).

---

## PROPOSITION A : Modele Look-alike par Cohorte (Mono-etape)

### Concept
Un modele unifie entraine sur les profils d'entree en relation de clients existants, predisant leur PNB a 12 mois. Simple, rapide a deployer, une seule prediction a l'onboarding.

### 1. Construction des Donnees d'Entrainement

**Source** : Prendre tous les clients ayant rejoint la banque en 2022 et 2023 (a partir des fichiers Stock). Pour chacun :
- Reconstituer leur **profil a l'entree en relation** (demographiques, revenu declare, CSP, produits souscrits, canal)
- Calculer leur **PNB reel sur les 12 mois suivant l'entree** (a partir des donnees Stock 2023 et 2024 respectivement)
- Calculer leur **indicateur de depart** a 12 mois (present dans le Stock Y+1 ou non)

**Decoupage train/test** : Temporel — clients entres en 2022 = entrainement, clients entres en 2023 = test. Cela reproduit le deploiement reel (predire le futur a partir du passe).

**Variables cibles** (deux modeles) :
- **Modele PNB** : `pnb_annee1` (continu, EUR) — PNB total genere les 12 premiers mois
- **Modele retention** : `depart_annee1` (binaire) — le client a-t-il quitte la banque dans les 12 mois ?

**Taille d'echantillon** : Depend du volume d'acquisition. Typiquement 2k-15k nouveaux clients/an pour une banque luxembourgeoise. Suffisant pour le gradient boosting.

### 2. Feature Engineering

#### Variables brutes a l'entree en relation
| Variable | Type | Encodage |
|----------|------|----------|
| `age` | numerique | tel quel (annees) |
| `genre` | binaire | 0/1 (M/F) |
| `situation_familiale` | categorielle | one-hot : celibataire, marie, divorce, veuf, pacse |
| `tranche_revenu` | ordinale | point milieu de la tranche (ex : 0-30k=15000, 30-50k=40000, 50-80k=65000, 80-120k=100000, 120k+=140000) |
| `csp_category` | categorielle | one-hot : cadre, employe, ouvrier, profession_liberale, fonctionnaire, retraite, etudiant, sans_emploi |
| `nationalite` | categorielle | luxembourgeois, francais, belge, allemand, portugais, autre_ue, hors_ue |
| `est_frontalier` | binaire | 1 si le client reside hors Luxembourg |
| `pays_residence` | categorielle | Luxembourg, France, Belgique, Allemagne, autre |
| `code_postal` | categorielle | utilise pour joindre les donnees STATEC |
| `canal_digital` | binaire | 1 si acquisition digitale, 0 si agence |

#### Mix produits a l'onboarding (indicateurs binaires)
| Variable | Description |
|----------|-------------|
| `has_compte_courant` | Compte courant (presque toujours 1) |
| `has_compte_epargne` | Compte d'epargne |
| `has_assurance_vie` | Assurance-vie |
| `has_credit_immobilier` | Credit immobilier |
| `has_credit_conso` | Credit a la consommation |
| `has_carte_bancaire` | Carte de debit/credit |
| `has_assurance_habitation` | Assurance habitation |
| `has_assurance_auto` | Assurance auto |
| `has_prevoyance` | Prevoyance |
| `n_produits_onboarding` | Nombre total de produits souscrits |
| `n_familles_produits` | Nombre de familles de produits couvertes (sur 4) |

#### Agregats par famille de produits (4 familles)
| Variable | Produits inclus |
|----------|-----------------|
| `fam_banque_quotidienne` | 1 si compte_courant OU carte_bancaire |
| `fam_epargne_investissement` | 1 si compte_epargne OU assurance_vie |
| `fam_credit` | 1 si credit_immobilier OU credit_conso |
| `fam_assurance_protection` | 1 si assurance_habitation OU assurance_auto OU prevoyance |

#### Enrichissement geographique (STATEC — donnees ouvertes Luxembourg)
Jointure sur `code_postal` ou `code_commune` a partir des donnees du STATEC :

| Variable | Source | Description |
|----------|--------|-------------|
| `revenu_median_commune` | STATEC | Revenu median disponible de la commune (EUR) |
| `densite_population` | STATEC | Habitants par km2 |
| `taux_chomage_canton` | ADEM/STATEC | Taux de chomage local |
| `categorie_urbaine` | STATEC | urbain/periurbain/rural |
| `pib_par_habitant_canton` | STATEC | PIB par habitant du canton |
| `pct_frontaliers_commune` | IGSS/STATEC | Part des frontaliers dans la commune |

#### Variables d'interaction
| Variable | Formule | Justification |
|----------|---------|---------------|
| `revenu_x_produits` | `tranche_revenu * n_produits_onboarding` | Revenu eleve + nombreux produits = potentiel PNB eleve |
| `age_x_credit` | `age * fam_credit` | L'age module le PNB credit (immobilier vs conso) |
| `digital_x_age` | `canal_digital * age` | Client digital jeune vs age = comportement different |
| `revenu_vs_commune` | `tranche_revenu - revenu_median_commune` | Revenu du client par rapport a la norme locale |
| `frontalier_x_revenu` | `est_frontalier * tranche_revenu` | Les frontaliers ont des profils de revenu specifiques |

#### Total : ~30-35 variables

### 3. Architecture du Modele

**Prediction PNB (regression)** :
```
Modele : GradientBoostingRegressor
Parametres : n_estimators=300, max_depth=4, learning_rate=0.05,
             subsample=0.8, min_samples_leaf=20
Cible : pnb_annee1 (EUR, continu)
Perte : huber (robuste aux valeurs aberrantes du PNB)
```

**Prediction retention (classification)** :
```
Modele : GradientBoostingClassifier
Parametres : n_estimators=200, max_depth=4, learning_rate=0.05,
             subsample=0.8, min_samples_leaf=20
Cible : depart_annee1 (binaire)
```

**Sous-modeles par famille** : NON recommande pour la Proposition A. Avec uniquement les variables d'entree en relation, le signal est insuffisant pour justifier 4 sous-modeles. Un modele unifie est preferable. Les indicateurs de famille de produits servent de variables d'entree.

### 4. Sous-modele de Retention pour Nouveaux Clients

**Constat cle** : Le taux de depart en premiere annee des nouveaux clients est typiquement de 15-25% (vs 3-5% pour les clients etablis). La courbe de survie a une forme differente — attrition elevee au debut qui se stabilise.

**Approche** :
- `retention_score_new = 1 - P(depart_annee1)` dans [0, 1]
- Courbe de survie modifiee specifique aux nouveaux clients :
  - `S(1) = retention_score_new` (sortie du modele)
  - `S(2) = S(1) * retention_etabli` (apres l'an 1, comportement de client etabli)
  - `S(3) = S(2) * retention_etabli`

**Formule CLV** :
```
CLV_new = PNB_pred(1) * S(1) / (1.05)^1
        + PNB_pred(2) * S(2) / (1.05)^2
        + PNB_pred(3) * S(3) / (1.05)^3

Ou :
  PNB_pred(1) = prediction du modele
  PNB_pred(2) = PNB_pred(1) * facteur_croissance
  PNB_pred(3) = PNB_pred(2) * facteur_croissance
  S(1) = retention_score_new
  S(2) = S(1) * 0.95
  S(3) = S(2) * 0.95
```

### 5. Format de Sortie

| Colonne | Type | Description |
|---------|------|-------------|
| `client_id` | str | Identifiant client |
| `pnb_pred_annee1` | float | PNB predit premiere annee (EUR) |
| `pnb_pred_annee2` | float | PNB projete annee 2 |
| `pnb_pred_annee3` | float | PNB projete annee 3 |
| `retention_score_new` | float | P(reste apres 1 an) |
| `survie_annee1` | float | = retention_score_new |
| `survie_annee2` | float | = S(1) * 0.95 |
| `survie_annee3` | float | = S(2) * 0.95 |
| `clv_total` | float | CLV actualisee sur 3 ans |
| `type_modele` | str | "nouvelle_acquisition_v1" |

### 6. Enrichissement par Donnees Externes

| Source | Donnees | Cle de jointure |
|--------|---------|-----------------|
| **STATEC** | Revenu median, taux de pauvrete par commune | code_commune |
| **STATEC Recensement** | Densite de population, structure demographique | code_commune |
| **ADEM** | Taux de chomage par canton | canton |
| **IGSS** | Donnees sur les frontaliers | code_commune |
| **data.public.lu** | Donnees ouvertes du Luxembourg (cartographie, communes) | code_postal |

### 7. Strategie de Transition

- **Mois 0-12** : Modele Proposition A (variables d'entree en relation uniquement)
- **Mois 12+** : Le client dispose de 4 trimestres de donnees comportementales -> passage au modele CLV etabli
- Pas de lissage — basculement direct au jalon des 12 mois
- La colonne `type_modele` identifie quel modele a produit la CLV

---

## PROPOSITION B : Modele Progressif en Deux Phases

### Concept
Deux phases distinctes qui s'activent au fur et a mesure de l'accumulation des donnees :
- **Phase 1 (Jour 0)** : Prediction purement declarative — identique a la Proposition A
- **Phase 2 (Mois 3-6)** : Les signaux comportementaux precoces enrichissent la prediction
- **Graduation (Mois 12)** : Transition vers le modele CLV etabli

L'avantage cle : la Phase 2 capture les **signaux d'engagement precoce** fortement predictifs de la valeur a long terme (un client qui commence a effectuer beaucoup de transactions au mois 2 est tres different de celui qui n'active jamais sa carte).

### 1. Construction des Donnees d'Entrainement

**Jeu Phase 1** : Identique a la Proposition A.

**Jeu Phase 2** : Pour les clients entres en 2022-2023, reconstituer :
- Leur **profil d'entree** (memes variables que Phase 1)
- Leurs **3 a 6 premiers mois de donnees comportementales** : transactions, PNB, activation produits
- Leur **PNB a 12 mois** (cible)
- Leur **indicateur de depart a 12 mois** (cible)

### 2. Feature Engineering

#### Variables Phase 1 : Identiques a la Proposition A (~30-35 variables)

#### Variables additionnelles Phase 2 (premiers 3-6 mois)

**Signaux PNB precoces** :
| Variable | Description |
|----------|-------------|
| `pnb_premier_trimestre` | PNB total des 3 premiers mois (EUR) |
| `pnb_mois1` | PNB du mois 1 uniquement |
| `taux_montee_pnb` | pnb_mois3 / pnb_mois1 (vitesse de montee en charge) |
| `log_pnb_premier_trimestre` | log1p(pnb_premier_trimestre) |

**Signaux transactionnels precoces** :
| Variable | Description |
|----------|-------------|
| `n_txn_premier_trimestre` | Nombre de transactions sur 3 mois |
| `jours_avant_premiere_txn` | Delai entre ouverture et premiere transaction |
| `frequence_txn` | n_txn_premier_trimestre / jours_actifs |
| `a_domiciliation_salaire` | 1 si salaire detecte (plus gros virement mensuel entrant) |
| `a_prelevement` | 1 si au moins un prelevement automatique configure |

**Signaux d'activation produits** :
| Variable | Description |
|----------|-------------|
| `n_produits_mois3` | Nombre de produits actifs au mois 3 |
| `produits_ajoutes` | n_produits_mois3 - n_produits_onboarding |
| `carte_activee` | 1 si la carte a ete utilisee au moins une fois |
| `epargne_alimentee` | 1 si un produit d'epargne a un solde > 0 |

**Signaux d'engagement** :
| Variable | Description |
|----------|-------------|
| `connexions_digitales_mois1` | Nombre de connexions app/web au mois 1 |
| `pct_usage_digital` | % des interactions en digital |
| `contact_conseiller` | 1 si RDV/appel avec un conseiller |

**Signal cle : domiciliation du salaire** — Si le client domicilie son salaire dans les 3 premiers mois, c'est le predicteur le plus fort de valeur a long terme et de retention. Cela indique que la banque est sa banque principale.

#### Total Phase 2 : ~30 variables d'entree + ~15 variables comportementales = ~45 variables

### 3. Architecture du Modele

**Phase 1** : Identique a la Proposition A.

**Phase 2** :
```
Modele PNB : GradientBoostingRegressor
Parametres : n_estimators=400, max_depth=5, learning_rate=0.05,
             subsample=0.8, min_samples_leaf=15
Cible : pnb_restant = pnb_annee1 - pnb_premier_trimestre
Perte : huber
```

**Phase 2 Retention** :
```
Modele : GradientBoostingClassifier
Parametres : n_estimators=300, max_depth=5, learning_rate=0.05,
             subsample=0.8, min_samples_leaf=15
Cible : depart_annee1 (binaire)
```

### 4. Sous-modele de Retention Nouveaux Clients

**Phase 1 (Jour 0)** :
- `retention_score_p1 = 1 - P(depart | variables d'entree)`
- Estimation large basee sur les donnees declaratives

**Phase 2 (Mois 3-6)** :
- `retention_score_p2 = 1 - P(depart | entree + comportemental)`
- Beaucoup plus precis — les clients n'ayant pas active leur carte ou domicilie leur salaire au mois 3 sont a tres haut risque
- **Alerte precoce** : signaler les clients avec `retention_score_p2 < 0.5` pour action commerciale proactive

**Projection survie 3 ans** :
```
S(1) = retention_score_p2
S(2) = S(1) * retention_etabli
S(3) = S(2) * retention_etabli
```

### 5. Strategie de Transition

**Chronologie** :
```
Jour 0     -> Prediction Phase 1 (variables d'entree uniquement)
Mois 3     -> Phase 2 (re-scoring avec donnees comportementales)
Mois 6     -> Rafraichissement Phase 2 (6 mois de donnees)
Mois 12    -> Graduation vers le modele CLV etabli
```

**Lissage lors de la transition** (Mois 12) :
```
CLV_transition = alpha * CLV_nouveau_modele + (1 - alpha) * CLV_modele_etabli

Ou alpha decroit entre les mois 10 et 14 :
  Mois 10 : alpha = 1.0 (100% nouveau modele)
  Mois 11 : alpha = 0.75
  Mois 12 : alpha = 0.50
  Mois 13 : alpha = 0.25
  Mois 14 : alpha = 0.0 (100% modele etabli)
```

### 6. Format de Sortie

| Colonne | Type | Description |
|---------|------|-------------|
| `client_id` | str | Identifiant client |
| `phase_modele` | str | "phase1" ou "phase2" |
| `pnb_pred_annee1` | float | PNB predit premiere annee |
| `pnb_pred_annee2` | float | PNB projete annee 2 |
| `pnb_pred_annee3` | float | PNB projete annee 3 |
| `retention_score_new` | float | P(reste apres 1 an) |
| `clv_total` | float | CLV actualisee sur 3 ans |
| `confiance` | str | "faible" (phase1) / "moyenne" (phase2) / "elevee" (etabli) |
| `domiciliation_salaire` | bool | Signal cle pour les equipes commerciales |
| `risque_depart_precoce` | bool | retention_score < 0.5 en Phase 2 |
| `type_modele` | str | "nouvelle_acq_phase1" ou "nouvelle_acq_phase2" |

---

## Recommandation

**Commencer par la Proposition A** — plus simple, plus rapide a deployer, valide l'hypothese look-alike. Si la Proposition A montre une bonne precision (MAE < 20% du PNB reel, AUC > 0.70 pour la retention), alors construire la Proposition B comme amelioration V2.

La Phase 2 de la Proposition B est la ou reside la vraie valeur (les signaux comportementaux precoces, notamment la domiciliation du salaire, sont extremement predictifs), mais elle necessite davantage d'ingenierie de donnees et de complexite operationnelle.

**Sequence recommandee** : Proposition A -> validation -> Proposition B Phase 2.
