# Checklist de Validation des Donnees

A executer des reception des fichiers de donnees, avant toute analyse ou modelisation.

## Architecture de rappel

- 5 sous-modeles : Epargne (encours), Investissements (encours), Credit immobilier (encours), Autres credits (encours), Autre PNB (NBI direct)
- Snapshot fixe a M+3
- Cible : valeur cumulee sur 5 ans (ou autant que disponible)
- Le churn n'est pas une variable explicite — il est implicitement capture par la duree de presence du client dans les donnees. Un client parti apres 2 ans aura des encours nuls pour les annees 3-5, ce qui reduit naturellement sa valeur cumulee et celle de son decile.

---

## ETAPE 1 — Inventaire des fichiers

### 1.1 Lister les fichiers recus
- [ ] Quels fichiers d'encours ? (epargne, investissements, credit immo, autres credits)
- [ ] Quel fichier de NBI autre ? (commissions, assurances)
- [ ] Fichiers PNB existants (NBI total) conserves pour validation ?
- [ ] Fichiers Stock (acquisitions) — memes que ceux deja utilises ?
- [ ] Fichiers Equipements — memes que ceux deja utilises ?
- [ ] Fichier des taux de marge (deja recu)

### 1.2 Format de chaque fichier
- [ ] Quel separateur ? (virgule, point-virgule, tabulation)
- [ ] Quel encodage ? (UTF-8, Latin-1, CP1252)
- [ ] Colonnes : client_id + indices mois bancaires (comme les fichiers PNB actuels) ?
- [ ] Ou autre format ? (long format avec colonne mois + montant ?)

### 1.3 Couverture temporelle
- [ ] Date de debut des donnees d'encours (annee + mois)
- [ ] Date de fin des donnees d'encours
- [ ] Les 5 familles couvrent-elles la meme periode ?
- [ ] Combien d'annees de donnees post-acquisition pour la cohorte la plus ancienne ?

---

## ETAPE 2 — Qualite des donnees brutes

### 2.1 Par fichier
- [ ] Nombre de lignes (clients) par fichier
- [ ] Nombre de colonnes (mois) par fichier
- [ ] Taux de valeurs manquantes par colonne
- [ ] Taux de valeurs manquantes par client (un client avec 90% de NaN est suspect)
- [ ] Doublons sur client_id dans un meme fichier
- [ ] Type des valeurs : numeriques ? Pas de texte dans les colonnes de montants ?

### 2.2 Valeurs aberrantes
- [ ] Y a-t-il des encours negatifs ? (possible pour les credits, pas normal pour l'epargne)
- [ ] Y a-t-il des valeurs extremes ? (encours > 10M EUR par exemple)
- [ ] Distribution des valeurs : moyenne, mediane, ecart-type, min, max, percentiles 1% et 99%
- [ ] Y a-t-il des valeurs exactement identiques pour de nombreux clients ? (signe d'un defaut de remplissage)

### 2.3 Zeros
- [ ] % de clients avec encours = 0 pour chaque famille, chaque mois
- [ ] Distinction entre 0 (le client a un produit avec solde nul) et NaN (le client n'a pas ce produit)
- [ ] Les zeros sont-ils coherents avec l'equipement ? (un client sans credit immo dans les equipements doit avoir encours_immo = 0)

---

## ETAPE 3 — Coherence entre les fichiers

### 3.1 Correspondance des clients
- [ ] Les memes client_id apparaissent-ils dans les 5 fichiers d'encours/NBI ?
- [ ] Les client_id des fichiers d'encours correspondent-ils a ceux des fichiers Stock ?
- [ ] Y a-t-il des clients dans Stock absents des fichiers d'encours ? (clients sans aucune activite ?)
- [ ] Y a-t-il des clients dans les encours absents de Stock ? (clients existants, pas des nouvelles acquisitions)

### 3.2 Correspondance temporelle
- [ ] Les indices mois dans les fichiers d'encours utilisent-ils le meme encodage que les fichiers PNB ? (Jan 1994 = 1)
- [ ] Les periodes couvertes sont-elles alignees entre les 5 fichiers ?

### 3.3 Validation NBI total
C'est le controle le plus important : la somme des 5 familles doit correspondre au NBI total.
- [ ] Pour chaque client et chaque mois : `encours_ep * t_s + encours_inv * t_i + encours_immo * t_m + encours_cr * t_c + nbi_autre ≈ nbi_total` (fichier PNB)
- [ ] Quel est l'ecart moyen ? L'ecart median ?
- [ ] Quel % de clients a un ecart > 10% ?
- [ ] Si ecarts importants : identifier l'origine (categorie manquante ? marge incorrecte ? temporalite differente ?)

---

## ETAPE 4 — Analyse de la structure pour le modele

### 4.1 Couverture du snapshot M+3
- [ ] Pour chaque cohorte d'acquisition : les donnees d'encours sont-elles disponibles a M+3 ?
- [ ] Le snapshot equipements trimestriel couvre-t-il bien M+3 pour chaque cohorte ?
- [ ] Combien de clients ont des donnees completes a M+3 vs des donnees manquantes ?

### 4.2 Taille des cohortes
- [ ] Nombre de clients par trimestre d'acquisition
- [ ] Nombre total de clients exploitables (avec snapshot M+3 complet)
- [ ] Y a-t-il des trimestres avec un volume anormalement faible ?

### 4.3 Profondeur de cible
Pour chaque cohorte, combien de mois/annees de donnees post-acquisition sont disponibles ?
- [ ] Cohorte la plus ancienne : combien de mois de cible ?
- [ ] Cohorte la plus recente avec cible complete (au moins 12 mois) ?
- [ ] Repartition des cohortes par duree de cible disponible (histogramme)

### 4.4 Zero-inflation par famille
- [ ] % de clients avec encours = 0 **a M+3** pour chaque famille
- [ ] % de clients avec encours cumule = 0 **sur toute la periode** pour chaque famille
- [ ] Le credit immobilier sera probablement tres creux (<10% de clients non-zero ?) — confirmer
- [ ] Les autres credits : quel taux de non-zero ?

### 4.5 Tenure implicite (proxy churn)
- [ ] Pour les cohortes anciennes : a quel mois les encours tombent-ils a zero definitivement ?
- [ ] % de clients encore actifs (encours > 0 dans au moins une famille) a 1 an, 2 ans, 3 ans, 4 ans
- [ ] La "duree de vie" moyenne des clients par segment
- [ ] Y a-t-il des clients dont les encours tombent a zero puis reviennent ? (clients dormants vs vrais departs)

---

## ETAPE 5 — Features disponibles

### 5.1 Variables declaratives
- [ ] Quelles colonnes sont presentes dans les fichiers Stock ? (segment, profession, age, genre, commune, canal, revenu...)
- [ ] Taux de remplissage de chaque variable declarative
- [ ] Nombre de modalites par variable categorielle (pas de variable avec 500 modalites)

### 5.2 Equipements a M+3
- [ ] Quels types de produits sont identifies dans les fichiers equipements ?
- [ ] Peut-on distinguer : compte courant, carte, livret, PEL, assurance vie, PEA, credit immo, credit conso, domiciliation salaire ?
- [ ] Format : binaire (0/1) ou quantite ?

### 5.3 Encours a M+3 (features)
- [ ] Peut-on extraire l'encours a M+3 exactement pour chaque client ? (pas une moyenne trimestrielle)
- [ ] Si encours moyens trimestriels : quel trimestre correspond le mieux a M+3 ?

### 5.4 NBI des 3 premiers mois (feature candidate)
- [ ] Le NBI total des fichiers PNB pour les mois 1-3 est-il disponible pour chaque client ?
- [ ] Peut-on aussi deriver un NBI par famille pour les mois 1-3 ? (encours_mois_1_3 * marge)

---

## ETAPE 6 — Resume a fournir

Une fois les verifications faites, preparer un resume avec :

1. **Inventaire** : liste des fichiers, format, couverture temporelle
2. **Volume** : nombre de clients par cohorte, nombre total exploitable
3. **Qualite** : taux de NaN, doublons, valeurs aberrantes
4. **Coherence** : ecart entre somme des familles et NBI total
5. **Zero-inflation** : % de zeros par famille a M+3 et en cumule
6. **Profondeur** : nombre d'annees de cible disponibles par cohorte
7. **Features** : liste des variables declaratives et equipements disponibles

Ce resume permettra de lancer immediatement l'analyse et la verification des hypotheses H1-H8.
