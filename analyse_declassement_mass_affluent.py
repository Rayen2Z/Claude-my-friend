# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  ANALYSE DU DÉCLASSEMENT MASS AFFLUENT                                      ║
# ║  Données : périodes 371 → 389 (371–376 = lookback flux ; 377–389 analysé). ║
# ║  Panel long : 1 ligne par (client × période).                              ║
# ║                                                                            ║
# ║  Règles métier :                                                           ║
# ║    • Un client est Mass Affluent (MA) si                                    ║
# ║        (avoirs ≥ 62 000 €  OU  flux ≥ 6 000 € sur CHACUN des 6 mois)        ║
# ║        ET  Actif sur les 3 derniers mois (flag Active_3M = Y).              ║
# ║    • L'activité est une condition NÉCESSAIRE en plus du financier.          ║
# ║    • Déclassement = MA au mois t, puis non-MA au mois t+1 (consécutifs).   ║
# ║    • Cause = le(s) critère(s) qui soutenai(en)t le statut à t et qui        ║
# ║      casse(nt) à t+1 (avoirs / flux / activité).                            ║
# ║                                                                            ║
# ║  Script auto-porté : à coller dans un notebook. Il suppose qu'un           ║
# ║  DataFrame `df` est déjà chargé (cf. cellule 0 pour le format attendu).    ║
# ║  Code en anglais, commentaires/affichages en français pour la direction.   ║
# ╚══════════════════════════════════════════════════════════════════════════╝

# %% [markdown]
# # 0. Configuration & chargement
#
# Colonnes attendues dans `df` (les noms peuvent contenir accents/espaces, ils
# sont normalisés automatiquement) :
# `identifiant_tiers`, `période`, `segment_upgrade`, `segment amélioré`,
# `frontalier_on`, `avoirs_eurs`, `volume_entrant_cvl`.

# %%
import unicodedata
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ── Paramètres métier ────────────────────────────────────────────────────────
AVOIRS_MIN    = 62_000     # seuil avoirs pour rester MA
INFLOW_MIN    = 6_000      # flux mensuel minimum
INFLOW_WINDOW = 6          # nb de mois consécutifs où le flux doit tenir
MA_LABEL      = "Mass Affluent"
EPOCH_YEAR    = 1994       # référentiel mois bancaire (Janvier 1994 = 1)
ANALYSIS_START = 377       # 05/2025 : 1er mois de déclassement analysé.
                           # Les périodes 371–376 servent uniquement d'historique flux (lookback).

FIG_DIR = Path("declassement_figures")
FIG_DIR.mkdir(exist_ok=True)

plt.rcParams.update({"figure.figsize": (12, 5.5), "axes.grid": True,
                     "grid.alpha": 0.25, "figure.dpi": 110,
                     "axes.titlesize": 13, "axes.labelsize": 11})
COL = {"avoirs": "#06B6D4", "flux": "#F59E0B", "both": "#7C3AED",
       "anom": "#94A3B8", "accent": "#EC4899", "dark": "#334155",
       "active": "#10B981", "mix": "#EF4444"}   # activité (vert) / financier+activité (rouge)


def idx_to_ym(idx):
    """Indice mois bancaire -> 'AAAA-MM'."""
    y = EPOCH_YEAR + (int(idx) - 1) // 12
    m = (int(idx) - 1) % 12 + 1
    return f"{y}-{m:02d}"


def _norm(name):
    """Normalise un nom de colonne : sans accents, snake_case."""
    s = unicodedata.normalize("NFD", str(name)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^0-9a-zA-Z]+", "_", s.lower()).strip("_")


def _to_num(series):
    """Montants -> float, tolère les formats européens ('1 234,56' / '1,234.56')."""
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)
    s = series.astype(str).str.strip()
    sample = s.dropna().head(200)
    if sample.str.contains(r",.*\.", regex=True).any():       # 1,234.56
        s = s.str.replace(",", "", regex=False)
    else:                                                     # 1 234,56
        s = (s.str.replace("\xa0", "", regex=False)
               .str.replace(" ", "", regex=False)
               .str.replace(",", ".", regex=False))
    return pd.to_numeric(s, errors="coerce")


# ── Démo hors-ligne : décommenter pour tester le pipeline sans vraies données ─
# rng = np.random.default_rng(0)
# _nper = 389 - 371 + 1
# _ids = np.repeat(np.arange(1000), _nper)
# _per = np.tile(np.arange(371, 390), 1000)
# df = pd.DataFrame({
#     "identifiant_tiers": _ids, "période": _per,
#     "segment_upgrade": "Mass Affluent",
#     "segment amélioré": rng.choice(["Salarié", "Cadre", "Non-résident"], len(_ids)),
#     "frontalier_on": rng.choice(["O", "N"], len(_ids)),
#     "avoirs_eurs": rng.normal(70_000, 20_000, len(_ids)).clip(0),
#     "volume_entrant_cvl": rng.normal(7_000, 3_000, len(_ids)).clip(0),
# })

# ── Normalisation des noms de colonnes vers un schéma canonique ──────────────
CANON = {
    "identifiant_tiers": "id", "id": "id", "client_id": "id",
    "periode": "periode",
    "segment_upgrade": "segment",
    "segment_ameliore": "profil",
    "frontalier_on": "frontalier", "frontalier_o_n": "frontalier",
    "avoirs_eurs": "avoirs", "avoirs_eur": "avoirs", "avoirs": "avoirs",
    "volume_entrant_cvl": "inflow", "volume_entrant": "inflow",
}
rename = {c: CANON[_norm(c)] for c in df.columns if _norm(c) in CANON}
data = df.rename(columns=rename).copy()

required = {"id", "periode", "segment", "avoirs", "inflow"}
missing = required - set(data.columns)
assert not missing, f"Colonnes manquantes après normalisation : {missing}"
HAS_FRONT  = "frontalier" in data.columns
HAS_PROFIL = "profil" in data.columns

# ── Typage ───────────────────────────────────────────────────────────────────
data["periode"] = pd.to_numeric(data["periode"], errors="coerce").astype("Int64")
data["avoirs"]  = _to_num(data["avoirs"])
data["inflow"]  = _to_num(data["inflow"]).fillna(0)   # ligne présente sans flux = 0 € ce mois-ci
data["segment"] = data["segment"].astype(str).str.strip()
data = data.dropna(subset=["id", "periode"]).drop_duplicates(["id", "periode"])
data["periode"] = data["periode"].astype(int)

print(f"Lignes : {len(data):,} | Clients : {data['id'].nunique():,} | "
      f"Périodes : {data['periode'].min()}–{data['periode'].max()} "
      f"({idx_to_ym(data['periode'].min())} → {idx_to_ym(data['periode'].max())})")
print(f"Frontalier dispo : {HAS_FRONT} | Profil (segment amélioré) dispo : {HAS_PROFIL}")

# ── Flag d'activité (Active 3M) — DataFrame séparé `activity` ─────────────────
# Attendu : colonnes id / période / 'Active 3 M' (valeurs 'Y'/'N'). Fusion sur
# (id, période). Flag manquant après fusion = INCONNU (n'entre pas dans la cause
# « Activité »). L'activité est une condition NÉCESSAIRE de l'éligibilité MA.
CANON_ACT = {
    "identifiant_tiers": "id", "id": "id", "client_id": "id", "client": "id",
    "periode": "periode", "period": "periode", "period_number": "periode",
    "numero_periode": "periode", "num_periode": "periode", "no_periode": "periode",
    "active_3_m": "active", "active_3m": "active", "actif_3_m": "active",
    "actif_3m": "active", "flag_active_3_m": "active", "flag_actif_3m": "active",
    "active_3_months": "active", "active3m": "active",
}
try:
    _act = activity.rename(columns={c: CANON_ACT[_norm(c)]
                                    for c in activity.columns if _norm(c) in CANON_ACT}).copy()
    assert {"id", "periode", "active"} <= set(_act.columns), \
        f"Colonnes activité manquantes : {{'id','periode','active'}} - {set(_act.columns)}"
    _act["periode"] = pd.to_numeric(_act["periode"], errors="coerce").astype("Int64")
    _act["active"]  = _act["active"].astype(str).str.strip().str.upper().map({"Y": True, "N": False})
    _act = _act.dropna(subset=["id", "periode"]).drop_duplicates(["id", "periode"])
    _act["periode"] = _act["periode"].astype(int)
    data = data.merge(_act[["id", "periode", "active"]], on=["id", "periode"], how="left")
    HAS_ACTIVE = True
    _cov = data["active"].notna().mean() * 100
    print(f"Flag activité fusionné : couverture {_cov:.1f}% des lignes | "
          f"actifs {(data['active'] == True).mean()*100:.1f}% / inactifs {(data['active'] == False).mean()*100:.1f}%")
except NameError:
    HAS_ACTIVE = False
    print("⚠ DataFrame `activity` introuvable — analyse sans le critère d'activité.")


# %% [markdown]
# # 1. Hygiène du panel & prévalence Mass Affluent
#
# On vérifie la profondeur d'observation par client et l'évolution de la part de
# clients MA sur la période. Un effritement régulier de la part MA = signal de
# fond ; un décrochage ponctuel = effet calendaire à creuser (section 8).

# %%
# Pivots (client × période) — base de tous les calculs vectorisés
seg_wide    = data.pivot_table(index="id", columns="periode", values="segment", aggfunc="first")
avoirs_wide = data.pivot_table(index="id", columns="periode", values="avoirs", aggfunc="first")
inflow_wide = data.pivot_table(index="id", columns="periode", values="inflow", aggfunc="first")
front_wide  = data.pivot_table(index="id", columns="periode", values="frontalier", aggfunc="first") if HAS_FRONT else None
profil_wide = data.pivot_table(index="id", columns="periode", values="profil", aggfunc="first") if HAS_PROFIL else None
# Flag activité déjà pré-calculé (Active 3M) : True / False / NaN (inconnu), pas de fenêtre à recalculer
active_wide = data.pivot_table(index="id", columns="periode", values="active", aggfunc="first") if HAS_ACTIVE else None
periods = sorted(seg_wide.columns)

obs_per_client = seg_wide.notna().sum(axis=1)
ma_share = pd.Series({p: (seg_wide[p] == MA_LABEL).sum() / seg_wide[p].notna().sum() * 100
                      for p in periods})

print("Observations par client : "
      f"médiane={obs_per_client.median():.0f}, min={obs_per_client.min()}, max={obs_per_client.max()}")
print("\nPart de clients Mass Affluent par période :")
for p in periods:
    print(f"  {idx_to_ym(p)} (p{p}) : {ma_share[p]:5.1f}%")

fig, ax = plt.subplots()
ax.plot([idx_to_ym(p) for p in periods], ma_share.values, "o-", lw=2.5, color=COL["both"])
ax.set_title("Part de clients Mass Affluent au fil des mois")
ax.set_ylabel("% de clients MA")
plt.xticks(rotation=45, ha="right")
plt.tight_layout(); plt.savefig(FIG_DIR / "01_ma_prevalence.png", bbox_inches="tight", facecolor="white"); plt.show()


# %% [markdown]
# # 2. Tests de qualification par (client, période)
#
# - **Test avoirs** : `avoirs ≥ 62 000 €`.
# - **Test flux** : `flux ≥ 6 000 €` pour CHACUN des 6 derniers mois (t-5..t).
#   La fenêtre complète n'est calculable qu'à partir de la 6e période observée.
#   Avec le lookback 371–376, toute la fenêtre d'analyse (≥ 377) est couverte ;
#   avant la 6e période → test flux *indéterminé* (NaN).

# %%
avoirs_pass_wide = avoirs_wide >= AVOIRS_MIN           # bool
inflow_ge = inflow_wide >= INFLOW_MIN                  # flux du mois ≥ 6k
present   = inflow_wide.notna()

inflow_pass_wide = pd.DataFrame(index=inflow_wide.index)   # 1/0/NaN
qualcount_wide   = pd.DataFrame(index=inflow_wide.index)   # nb de mois qualifiants (0..6)
for p in periods:
    win = [p - k for k in range(INFLOW_WINDOW)]
    avail = [w for w in win if w in inflow_wide.columns]
    cnt = sum((inflow_ge[w] & present[w]).astype(int) for w in avail)
    qualcount_wide[p] = cnt
    if len(avail) < INFLOW_WINDOW:                         # fenêtre incomplète
        inflow_pass_wide[p] = np.nan
    else:
        all_present = pd.concat([present[w] for w in win], axis=1).all(axis=1)
        inflow_pass_wide[p] = np.where(all_present, cnt.eq(INFLOW_WINDOW), np.nan)

first_full = min((p for p in periods if (p - INFLOW_WINDOW + 1) in periods), default=None)
print(f"Test flux pleinement calculable à partir de : "
      f"{idx_to_ym(first_full)} (p{first_full})" if first_full else "Test flux : aucune fenêtre complète")


# %% [markdown]
# # 3. Détection des déclassements
#
# Événement = MA à la période t **et** segment différent de MA à t+1, sur deux
# périodes **consécutives observées**. On garde tous les événements (un client
# peut être déclassé plusieurs fois) et on isole aussi le **1er déclassement**
# par client.

# %%
def _lookup(wide, ids, p):
    return wide[p].reindex(ids).values if (wide is not None and p in wide.columns) else np.full(len(ids), np.nan)

rows = []
for p in periods:
    nxt = p + 1
    if nxt not in seg_wide.columns or nxt < ANALYSIS_START:   # 371–376 = lookback seulement
        continue
    was_ma  = (seg_wide[p] == MA_LABEL)
    now_seg = seg_wide[nxt]
    down = was_ma & now_seg.notna() & (now_seg != MA_LABEL)
    ids = down[down].index
    if len(ids) == 0:
        continue
    rows.append(pd.DataFrame({
        "id": ids, "t": p, "d": nxt, "mois_declassement": idx_to_ym(nxt),
        "target_segment": now_seg.reindex(ids).values,
        "avoirs_t": _lookup(avoirs_wide, ids, p),   "avoirs_d": _lookup(avoirs_wide, ids, nxt),
        "avoirs_pass_t": _lookup(avoirs_pass_wide, ids, p), "avoirs_pass_d": _lookup(avoirs_pass_wide, ids, nxt),
        "inflow_pass_t": _lookup(inflow_pass_wide, ids, p), "inflow_pass_d": _lookup(inflow_pass_wide, ids, nxt),
        "qual_t": _lookup(qualcount_wide, ids, p),  "qual_d": _lookup(qualcount_wide, ids, nxt),
        "active_pass_t": _lookup(active_wide, ids, p), "active_pass_d": _lookup(active_wide, ids, nxt),
        "frontalier": _lookup(front_wide, ids, nxt),
        "profil": _lookup(profil_wide, ids, nxt),
    }))

dg = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
dg_first = dg.sort_values("d").drop_duplicates("id", keep="first")   # 1er déclassement / client

n_ma_clients = (seg_wide == MA_LABEL).any(axis=1).sum()
print(f"Déclassements (événements)      : {len(dg):,}")
print(f"Clients déclassés (uniques)     : {dg['id'].nunique():,}")
print(f"Clients MA observés (≥1 mois)   : {n_ma_clients:,}")
print(f"Taux de déclassement (clients)  : {dg['id'].nunique()/max(n_ma_clients,1)*100:.1f}%")
print("\nSegment cible après déclassement :")
print(dg["target_segment"].value_counts().to_string())


# %% [markdown]
# # 4. ★ Attribution de la cause (cœur de l'analyse)
#
# Règle **(avoirs ≥ 62k OU flux 6 mois) ET activité**. Le **déclencheur** est le(s)
# critère(s) qui soutenai(en)t le statut à t et qui casse(nt) à t+1 :
# - **Avoirs** : les avoirs passent sous 62k (financier, l'activité tient).
# - **Flux** : rupture de la série de 6 mois ≥ 6k (financier, l'activité tient).
# - **Les deux (fin)** : avoirs ET flux cèdent (activité intacte).
# - **Activité** : le client devient inactif (Active_3M passe à N), financier intact.
# - **Financier + Activité** : un soutien financier ET l'activité cassent le même mois.
# - **Anomalie** : la règle dirait encore MA → lag d'application ou autre critère.
# - **Indéterminé** : flux hors fenêtre OU flag d'activité manquant.
#
# ⚠️ L'ajout de l'activité doit faire **fondre les anomalies** : beaucoup de clients
# « financièrement encore MA » mais déclassés le sont en fait parce qu'ils sont devenus inactifs.

# %%
def _status(a, i):
    if pd.isna(i):
        return "Avoirs OK / flux ?" if a else "Avoirs KO / flux ?"
    if a and i == 1:  return "Les deux"
    if a:             return "Avoirs seul"
    if i == 1:        return "Flux seul"
    return "Aucun"

def _trigger(r):
    lost_av = bool(r.avoirs_pass_t) and not bool(r.avoirs_pass_d)
    it, idd = r.inflow_pass_t, r.inflow_pass_d
    fin_indet = pd.isna(it) or pd.isna(idd)
    lost_fx = (not fin_indet) and (it == 1) and (idd != 1)
    if HAS_ACTIVE:                                          # activité = condition nécessaire
        at, ad = r.active_pass_t, r.active_pass_d
        act_indet = pd.isna(at) or pd.isna(ad)
        lost_ac = (not act_indet) and bool(at) and (not bool(ad))   # était actif, devient inactif
    else:
        act_indet, lost_ac = False, False
    fin_broken = lost_av or lost_fx
    if not (fin_broken or lost_ac):
        return "Indéterminé" if (fin_indet or act_indet) else "Anomalie (règle dit encore MA)"
    if fin_broken and lost_ac:  return "Financier + Activité"
    if lost_ac:                 return "Activité"
    if lost_av and lost_fx:     return "Les deux (fin)"
    if lost_av:                 return "Avoirs"
    return "Flux"

dg["statut_t"]  = [_status(a, i) for a, i in zip(dg.avoirs_pass_t, dg.inflow_pass_t)]
dg["statut_d"]  = [_status(a, i) for a, i in zip(dg.avoirs_pass_d, dg.inflow_pass_d)]
dg["trigger"]   = dg.apply(_trigger, axis=1)
dg["avoirs_ko_d"] = ~dg.avoirs_pass_d.astype(bool)
dg["flux_ko_d"]   = dg.inflow_pass_d.ne(1)              # NaN -> True (inconnu compté comme non-passant)
if HAS_ACTIVE:
    dg["active_ko_d"] = dg["active_pass_d"] == False    # inactif connu à t+1

trig = dg["trigger"].value_counts()
print("Déclencheur du déclassement (tous événements) :")
for k, v in trig.items():
    print(f"  {k:<34} {v:>6,}  ({v/len(dg)*100:4.1f}%)")

print("\nÀ t+1 (état des critères, indépendamment du déclencheur) :")
print(f"  Avoirs < 62k                       : {dg['avoirs_ko_d'].mean()*100:4.1f}%")
print(f"  Test flux non satisfait            : {dg['flux_ko_d'].mean()*100:4.1f}%")
print(f"  Les deux (fin) KO simultanément    : {(dg['avoirs_ko_d'] & dg['flux_ko_d']).mean()*100:4.1f}%")
if HAS_ACTIVE:
    print(f"  Inactif (Active_3M = N)            : {dg['active_ko_d'].mean()*100:4.1f}%")

# ── ★ Test du facteur ACTIVITÉ : explique-t-il les anciennes « anomalies » ? ──
if HAS_ACTIVE:
    fin_ok_d = dg["avoirs_pass_d"].astype(bool) | dg["inflow_pass_d"].eq(1)
    amo = dg[fin_ok_d]
    print("\n★ FACTEUR ACTIVITÉ")
    print(f"  Déclassés ENCORE éligibles financièrement (avoirs OU flux OK à t+1) : {len(amo):,}")
    if len(amo):
        print(f"    … dont INACTIFS (Active_3M = N) : {(amo['active_pass_d'] == False).mean()*100:4.1f}%"
              f"  → expliqués par l'activité")
    share_act = dg["trigger"].isin(["Activité", "Financier + Activité"]).mean() * 100
    print(f"  Déclassements déclenchés par l'activité (seule ou combinée) : {share_act:.1f}% du total")

ct = pd.crosstab(dg["statut_t"], dg["statut_d"])
print("\nTable de transition  statut@t (lignes)  ×  statut@t+1 (colonnes) :")
print(ct.to_string())

# ── Vue « fenêtre flux complète » ────────────────────────────────────────────
# Déclassements où le test des 6 mois est calculable à t ET à t+1 (élimine les
# « indéterminé »). Avec le lookback 371–376, ce sous-ensemble ≈ tout `dg`.
dg_clean = dg[dg["inflow_pass_t"].notna() & dg["inflow_pass_d"].notna()].copy()
print(f"\n{'='*60}")
print(f"FENÊTRE FLUX COMPLÈTE — {len(dg_clean):,} déclassements "
      f"({len(dg_clean)/max(len(dg),1)*100:.0f}% du total) avec test flux déterminable")
print(f"{'='*60}")
trig_clean = dg_clean["trigger"].value_counts()
print("Déclencheur (fenêtre complète uniquement) :")
for k, v in trig_clean.items():
    print(f"  {k:<34} {v:>6,}  ({v/max(len(dg_clean),1)*100:4.1f}%)")
print("\nÀ t+1 (fenêtre complète) :")
print(f"  Avoirs < 62k                       : {dg_clean['avoirs_ko_d'].mean()*100:4.1f}%")
print(f"  Test flux non satisfait            : {dg_clean['flux_ko_d'].mean()*100:4.1f}%")
print(f"  Les deux KO simultanément          : {(dg_clean['avoirs_ko_d'] & dg_clean['flux_ko_d']).mean()*100:4.1f}%")

# ── E2. Sévérité de la rupture de flux ───────────────────────────────────────
# Parmi les déclassements « Flux », combien de mois (sur 6) qualifiaient encore ?
# qual_d = 5 -> un seul mois a décroché = fragilité de bord, très réversible.
flux_dg = dg[dg["trigger"] == "Flux"]
if len(flux_dg):
    print("\nSévérité de la rupture flux — mois qualifiants (≥6k) sur 6 au déclassement :")
    print(flux_dg["qual_d"].value_counts().sort_index().to_string())
    # ── E3. Coussin d'avoirs lors d'un déclassement flux ─────────────────────
    cush = flux_dg["avoirs_d"].dropna()
    if len(cush):
        print(f"\nAvoirs au déclassement (cause flux) — médiane {cush.median():,.0f} € | "
              f"part 40–62k : {((cush >= 40_000) & (cush < AVOIRS_MIN)).mean()*100:.1f}%")

# ── Figure : déclencheurs (barres) + segment cible (camembert) ───────────────
# Ordre & couleurs partagés par toutes les sections (7, 8, 9).
TRIGGER_ORDER = ["Avoirs", "Flux", "Les deux (fin)", "Activité",
                 "Financier + Activité", "Anomalie (règle dit encore MA)", "Indéterminé"]
cmap = {"Avoirs": COL["avoirs"], "Flux": COL["flux"], "Les deux (fin)": COL["both"],
        "Activité": COL["active"], "Financier + Activité": COL["mix"],
        "Anomalie (règle dit encore MA)": COL["anom"], "Indéterminé": "#CBD5E1"}
order = TRIGGER_ORDER
# Figure basée sur la fenêtre flux complète (vue nette)
trig_o = trig_clean.reindex([o for o in order if o in trig_clean.index])
den = max(len(dg_clean), 1)
fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
axes[0].barh([str(i) for i in trig_o.index][::-1], trig_o.values[::-1],
             color=[cmap.get(i, COL["dark"]) for i in trig_o.index][::-1], edgecolor="white")
axes[0].set_title("Déclencheur du déclassement (fenêtre flux complète)")
for y, v in enumerate(trig_o.values[::-1]):
    axes[0].text(v, y, f" {v:,} ({v/den*100:.0f}%)", va="center", fontsize=9)
tgt = dg["target_segment"].value_counts()
axes[1].pie(tgt.values, labels=tgt.index, autopct="%1.0f%%", startangle=90,
            colors=[COL["flux"], COL["accent"], COL["anom"]])
axes[1].set_title("Segment d'arrivée après déclassement")
plt.tight_layout(); plt.savefig(FIG_DIR / "02_triggers.png", bbox_inches="tight", facecolor="white"); plt.show()

# ── Figure : heatmap de la table de transition ───────────────────────────────
fig, ax = plt.subplots(figsize=(8, 5))
im = ax.imshow(ct.values, cmap="Purples", aspect="auto")
ax.set_xticks(range(len(ct.columns))); ax.set_xticklabels(ct.columns, rotation=30, ha="right")
ax.set_yticks(range(len(ct.index)));   ax.set_yticklabels(ct.index)
ax.set_xlabel("statut @ t+1"); ax.set_ylabel("statut @ t")
ax.set_title("Transition des soutiens MA (t → t+1)")
for i in range(ct.shape[0]):
    for j in range(ct.shape[1]):
        ax.text(j, i, f"{ct.values[i, j]:,}", ha="center", va="center", fontsize=9,
                color="white" if ct.values[i, j] > ct.values.max() * 0.5 else COL["dark"])
plt.colorbar(im, ax=ax, fraction=0.046); plt.tight_layout()
plt.savefig(FIG_DIR / "03_transition_heatmap.png", bbox_inches="tight", facecolor="white"); plt.show()


# %% [markdown]
# # 5. Fragilité — les déclassés étaient-ils « à peine » MA ?
#
# On regarde les avoirs au **dernier mois MA (t)**. Si les déclassés se massent
# juste au-dessus de 62k, le statut était fragile → le déclassement est en grande
# partie mécanique (frontière), pas un vrai décrochage de richesse.

# %%
av_t = dg["avoirs_t"].dropna()
band = ((av_t >= AVOIRS_MIN) & (av_t < 70_000)).mean() * 100
print(f"Avoirs au dernier mois MA — médiane : {av_t.median():,.0f} € | moyenne : {av_t.mean():,.0f} €")
print(f"Part des déclassés « borderline » (62k ≤ avoirs < 70k au mois t) : {band:.1f}%")

fig, ax = plt.subplots()
clip = av_t.clip(upper=av_t.quantile(0.97))
ax.hist(clip, bins=50, color=COL["avoirs"], edgecolor="white")
ax.axvline(AVOIRS_MIN, color=COL["accent"], ls="--", lw=2, label="Seuil 62k €")
ax.axvspan(AVOIRS_MIN, 70_000, color=COL["accent"], alpha=0.08, label="Zone fragile 62–70k")
ax.set_title("Avoirs au dernier mois Mass Affluent (clients déclassés)")
ax.set_xlabel("Avoirs (€)"); ax.legend()
plt.tight_layout(); plt.savefig(FIG_DIR / "04_fragilite_avoirs.png", bbox_inches="tight", facecolor="white"); plt.show()


# %% [markdown]
# # 6. Magnitude — falaise ou érosion progressive ? (event study)
#
# Trajectoire alignée sur le mois de déclassement (k=0 = t+1). On suit la médiane
# des avoirs et le nombre moyen de mois de flux qualifiants autour de l'événement.
# Chute brutale en k=0 → choc ; pente descendante sur plusieurs mois → érosion.

# %%
KS = list(range(-6, 4))
ev = dg[["id", "d"]].copy()
es = ev.loc[ev.index.repeat(len(KS))].copy()
es["k"] = KS * len(ev)
es["periode"] = es["d"] + es["k"]

avoirs_long = avoirs_wide.reset_index().melt(id_vars="id", var_name="periode", value_name="avoirs")
qual_long   = qualcount_wide.reset_index().melt(id_vars="id", var_name="periode", value_name="qual")
es = es.merge(avoirs_long, on=["id", "periode"], how="left").merge(qual_long, on=["id", "periode"], how="left")
traj = es.groupby("k").agg(avoirs_med=("avoirs", "median"), avoirs_moy=("avoirs", "mean"),
                           qual_moy=("qual", "mean")).reindex(KS)

print("Trajectoire autour du déclassement (k=0 = mois de déclassement) :")
print(traj.round(0).to_string())

fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
axes[0].plot(traj.index, traj["avoirs_med"], "o-", lw=2.5, color=COL["avoirs"], label="Médiane")
axes[0].plot(traj.index, traj["avoirs_moy"], "o--", lw=1.8, color=COL["dark"], alpha=0.7, label="Moyenne")
axes[0].axhline(AVOIRS_MIN, color=COL["accent"], ls=":", label="Seuil 62k")
axes[0].axvline(0, color="red", ls=":", alpha=0.6)
axes[0].set_title("Avoirs autour du déclassement"); axes[0].set_xlabel("Mois relatif (k)")
axes[0].set_ylabel("Avoirs (€)"); axes[0].legend()
axes[1].plot(traj.index, traj["qual_moy"], "o-", lw=2.5, color=COL["flux"])
axes[1].axvline(0, color="red", ls=":", alpha=0.6)
axes[1].set_title("Mois de flux qualifiants (sur 6) autour du déclassement")
axes[1].set_xlabel("Mois relatif (k)"); axes[1].set_ylabel("Nb mois ≥ 6k (moy.)"); axes[1].set_ylim(0, 6)
plt.tight_layout(); plt.savefig(FIG_DIR / "05_event_study.png", bbox_inches="tight", facecolor="white"); plt.show()


# %% [markdown]
# # 7. Coupes explicatives — frontaliers & profil
#
# Taux de déclassement par groupe, calculé sur la **population à risque** :
# chaque couple (client, période) où le client est MA et où un mois suivant est
# observé. Hypothèse à tester : les frontaliers (salaire domicilié à l'étranger)
# cassent davantage par le **flux**.

# %%
# Population à risque : MA à p, avec p+1 observé
risk_rows = []
for p in periods:
    if p + 1 not in seg_wide.columns:
        continue
    ma_p = (seg_wide[p] == MA_LABEL) & seg_wide[p + 1].notna()
    risk_rows.append(pd.DataFrame({"id": ma_p[ma_p].index, "periode": p}))
risk = pd.concat(risk_rows, ignore_index=True)
risk = risk[risk["periode"] >= ANALYSIS_START - 1].copy()   # dénominateur aligné sur la fenêtre analysée
dgset = set(zip(dg.id, dg.t))
risk["down"] = [(i, p) in dgset for i, p in zip(risk.id, risk.periode)]
if HAS_FRONT:
    risk = risk.merge(front_wide.reset_index().melt(id_vars="id", var_name="periode", value_name="frontalier"),
                      on=["id", "periode"], how="left")
if HAS_PROFIL:
    risk = risk.merge(profil_wide.reset_index().melt(id_vars="id", var_name="periode", value_name="profil"),
                      on=["id", "periode"], how="left")

print(f"Taux de déclassement global (mensuel, pop. à risque) : {risk['down'].mean()*100:.2f}%")

def _rate_table(col):
    g = risk.groupby(risk[col].astype(str)).agg(n_risque=("down", "size"), taux=("down", "mean"))
    g["taux_%"] = (g["taux"] * 100).round(2)
    return g.drop(columns="taux").sort_values("taux_%", ascending=False)

panels = []
if HAS_FRONT:
    print("\nPar frontalier :"); print(_rate_table("frontalier").to_string()); panels.append("frontalier")
if HAS_PROFIL:
    print("\nPar profil (segment amélioré) — top :")
    print(_rate_table("profil").head(12).to_string()); panels.append("profil")

# Mix de déclencheurs par frontalier
if HAS_FRONT:
    mix = (pd.crosstab(dg["frontalier"].astype(str), dg["trigger"], normalize="index") * 100).round(1)
    print("\nMix des déclencheurs par frontalier (%) :"); print(mix.to_string())

# ── Barres « taux de déclassement » ventilées par cause ──────────────────────
# Longueur totale = taux du groupe ; découpage = part de chaque déclencheur.
CAUSES = TRIGGER_ORDER                                   # inclut Activité + combos
cause_cols = {c: cmap.get(c, COL["dark"]) for c in CAUSES}

def rate_stacked_by_cause(col, top=10):
    denom = risk.groupby(risk[col].astype(str))["down"].agg(n="size", d="sum")
    denom["rate"] = denom["d"] / denom["n"] * 100
    mix = pd.crosstab(dg[col].astype(str), dg["trigger"])
    for c in CAUSES:
        if c not in mix.columns:
            mix[c] = 0
    share = mix[CAUSES].div(mix[CAUSES].sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    seg = share.mul(denom["rate"], axis=0)                       # longueur = taux × part
    keep = denom.sort_values("rate", ascending=False).head(top).index
    return seg.reindex(keep).iloc[::-1]                          # plus fort en haut

if panels:
    fig, axes = plt.subplots(1, len(panels), figsize=(8 * len(panels), 5.2), squeeze=False)
    for ax, col in zip(axes[0], panels):
        seg = rate_stacked_by_cause(col)
        left = np.zeros(len(seg))
        for c in CAUSES:
            ax.barh(seg.index, seg[c], left=left, color=cause_cols[c], edgecolor="white", label=c)
            left += seg[c].values
        for y, tot in enumerate(left):
            ax.text(tot, y, f" {tot:.1f}%", va="center", fontsize=9)
        ax.set_title(f"Taux de déclassement par {col} — ventilé par cause")
        ax.set_xlabel("% (pop. à risque)")
    axes[0][0].legend(fontsize=8, loc="lower right")
    plt.tight_layout(); plt.savefig(FIG_DIR / "06_taux_par_cause.png", bbox_inches="tight", facecolor="white"); plt.show()


# %% [markdown]
# # 8. Dynamique mensuelle — sorties vs entrées du portefeuille MA
#
# Barres (axe gauche) = volume de déclassements par mois, empilé par déclencheur
# (saisonnalité + cause). Lignes normalisées (axe droit) = **taux de déclassement**
# et **taux d'acquisition MA** (mouvement inverse), en % de la population MA du mois.
# Quand la ligne « sortie » passe au-dessus de la ligne « entrée », le pool MA se vide.

# %%
# Acquisitions MA (non-MA -> MA) et population MA à risque, par mois d'analyse
months, acq_ma, ma_pop = [], {}, {}
for p in periods:
    nxt = p + 1
    if nxt not in seg_wide.columns or nxt < ANALYSIS_START:
        continue
    m = idx_to_ym(nxt); months.append(m)
    acq_ma[m] = int(((seg_wide[p].notna()) & (seg_wide[p] != MA_LABEL) & (seg_wide[nxt] == MA_LABEL)).sum())
    ma_pop[m] = int((seg_wide[p] == MA_LABEL).sum())        # pool exposé = MA au mois précédent
ma_pop = pd.Series(ma_pop).reindex(months)
acq_ma = pd.Series(acq_ma).reindex(months)
by_cause = pd.crosstab(dg["mois_declassement"], dg["trigger"]).reindex(months, fill_value=0)
down_rate = by_cause.sum(axis=1) / ma_pop * 100
acq_rate  = acq_ma / ma_pop * 100

print("Déclassements par mois × déclencheur :")
print(by_cause.to_string())
print(f"\nTaux de déclassement mensuel — min {down_rate.min():.1f}% / max {down_rate.max():.1f}%")

fig, ax = plt.subplots(figsize=(14, 6))
bottom = np.zeros(len(months))
for trg in [c for c in order if c in by_cause.columns]:
    ax.bar(months, by_cause[trg], bottom=bottom, label=trg,
           color=cmap.get(trg, COL["dark"]), edgecolor="white")
    bottom += by_cause[trg].values
ax.set_ylabel("Nb de déclassements (barres)"); ax.set_xlabel("Mois")
ax.legend(loc="upper left", fontsize=8, ncol=2)
plt.xticks(rotation=45, ha="right")

ax2 = ax.twinx(); ax2.grid(False)
ax2.plot(months, down_rate.values, "o-", color=COL["accent"], lw=2.5, label="Taux de déclassement (%)")
ax2.plot(months, acq_rate.values, "s--", color=COL["dark"], lw=2, alpha=0.7, label="Taux d'acquisition MA (%)")
ax2.set_ylabel("% de la population MA (lignes)")
ax2.set_ylim(0, max(down_rate.max(), acq_rate.max()) * 1.25)
ax2.legend(loc="upper right", fontsize=8)
ax.set_title("Dynamique mensuelle du portefeuille Mass Affluent — sorties vs entrées")
plt.tight_layout(); plt.savefig(FIG_DIR / "07_dynamique_mensuelle.png", bbox_inches="tight", facecolor="white"); plt.show()


# %% [markdown]
# # 9. (Bonus) Réversibilité — déclassement durable ou temporaire ?
#
# Parmi les clients déclassés, combien repassent MA plus tard dans la fenêtre ?
# Un fort taux de retour = volatilité de frontière (à lisser) plutôt que perte
# réelle de valeur.

# %%
# dg_first reconstruit ICI pour disposer de la colonne `trigger` (ajoutée en section 4)
dg_first = dg.sort_values("d").drop_duplicates("id", keep="first").copy()

def _recovers(cid, d):
    return any(seg_wide[p].get(cid) == MA_LABEL for p in periods if p > d and p in seg_wide.columns)

dg_first["recovered"] = [_recovers(i, d) for i, d in zip(dg_first["id"], dg_first["d"])]
rec_rate = dg_first["recovered"].mean() * 100 if len(dg_first) else float("nan")
print(f"Clients déclassés repassant MA avant la fin de la fenêtre : {rec_rate:.1f}% "
      f"({int(dg_first['recovered'].sum()):,}/{len(dg_first):,})")

# ── E1. Réversibilité PAR CAUSE ──────────────────────────────────────────────
# Hypothèse : les déclassements « Flux » (un mois qui décroche) reviennent plus
# souvent que les « Avoirs » (vraie érosion) → argument pour lisser le critère.
rec_by_cause = dg_first.groupby("trigger")["recovered"].agg(
    taux_retour=lambda s: round(s.mean() * 100, 1), n="size").sort_values("taux_retour", ascending=False)
print("\nTaux de retour MA par déclencheur :")
print(rec_by_cause.to_string())

sub = rec_by_cause[rec_by_cause.index.isin(CAUSES)]
if len(sub):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(sub.index, sub["taux_retour"], color=[cause_cols.get(c, COL["dark"]) for c in sub.index],
           edgecolor="white")
    for i, (v, n) in enumerate(zip(sub["taux_retour"], sub["n"])):
        ax.text(i, v, f"{v:.0f}%\n(n={n:,})", ha="center", va="bottom", fontsize=9)
    ax.set_title("Réversibilité du déclassement par cause"); ax.set_ylabel("% repassant MA")
    ax.set_ylim(0, 105); plt.xticks(rotation=15, ha="right")
    plt.tight_layout(); plt.savefig(FIG_DIR / "08_reversibilite_cause.png", bbox_inches="tight", facecolor="white"); plt.show()


# %% [markdown]
# # 10. Ancienneté Mass Affluent avant déclassement
#
# Depuis combien de mois consécutifs un client est-il MA au moment où il décroche ?
# On mesure la **longueur de la série MA** finissant au dernier mois MA (t), puis le
# **taux de déclassement par tranche d'ancienneté** sur la population à risque.
#
# ⚠️ Ancienneté **censurée à gauche** : on n'observe qu'à partir de la période 371,
# donc un client MA de longue date apparaît au plus avec ~19 mois d'ancienneté.
# La comparaison *récents vs installés* reste valide ; l'absolu est sous-estimé.
#
# Lecture attendue : corrélation **négative** (les MA installés sont plus stables ;
# les MA récents, souvent portés par un flux fragile, décrochent davantage).

# %%
ma_bool = (seg_wide == MA_LABEL)
streak = pd.DataFrame(index=ma_bool.index)
run = pd.Series(0, index=ma_bool.index)
for p in periods:                                   # série MA consécutive finissant à p
    col = ma_bool[p].fillna(False)
    run = (run + 1).where(col, 0)                   # +1 si MA, sinon remise à 0
    streak[p] = run
streak_long = streak.reset_index().melt(id_vars="id", var_name="periode", value_name="ma_tenure")

# Ancienneté au dernier mois MA (t) pour chaque déclassement
dg = dg.merge(streak_long.rename(columns={"periode": "t"}), on=["id", "t"], how="left")
ten = dg["ma_tenure"].dropna()
print(f"Ancienneté MA avant déclassement — médiane {ten.median():.0f} mois | "
      f"moyenne {ten.mean():.1f} | part ≤ 6 mois : {(ten <= 6).mean()*100:.1f}%")

# Taux de déclassement par tranche d'ancienneté (population à risque)
risk_ten = risk.merge(streak_long, on=["id", "periode"], how="left")
risk_ten["tranche"] = pd.cut(risk_ten["ma_tenure"], bins=[0, 3, 6, 12, 10_000],
                             labels=["1-3", "4-6", "7-12", "13+"], include_lowest=True)
rate_ten = risk_ten.groupby("tranche")["down"].agg(n="size", taux=lambda s: s.mean() * 100)
print("\nTaux de déclassement par ancienneté MA :")
print(rate_ten.assign(taux=lambda d: d["taux"].round(2)).to_string())

corr = np.corrcoef(risk_ten["ma_tenure"].fillna(0), risk_ten["down"].astype(int))[0, 1]
print(f"\nCorrélation ancienneté ↔ déclassement : {corr:+.3f} "
      f"({'plus ancien = plus stable' if corr < 0 else 'à interpréter'})")

fig, axes = plt.subplots(1, 2, figsize=(15, 5))
axes[0].hist(ten.clip(upper=ten.quantile(0.98)), bins=25, color=COL["both"], edgecolor="white")
axes[0].axvline(6, color=COL["accent"], ls="--", label="6 mois")
axes[0].set_title("Ancienneté MA au moment du déclassement")
axes[0].set_xlabel("Mois MA consécutifs"); axes[0].legend()
axes[1].bar(rate_ten.index.astype(str), rate_ten["taux"], color=COL["flux"], edgecolor="white")
axes[1].set_title("Taux de déclassement par ancienneté MA")
axes[1].set_xlabel("Ancienneté (mois)"); axes[1].set_ylabel("% (pop. à risque)")
for i, v in enumerate(rate_ten["taux"]):
    axes[1].text(i, v, f"{v:.1f}%", ha="center", va="bottom", fontsize=9)
plt.tight_layout(); plt.savefig(FIG_DIR / "09_anciennete.png", bbox_inches="tight", facecolor="white"); plt.show()


# %% [markdown]
# # 11. Synthèse pour la direction — À COMPLÉTER après exécution
#
# | Hypothèse | Question | Chiffre clé (à remplir) | Verdict |
# |-----------|----------|--------------------------|---------|
# | HA | Quel déclencheur domine ? | Avoirs ___% vs Flux ___% vs Activité ___% | |
# | HI | Activité = facteur clé ? | Déclassés fin. éligibles inactifs : ___% ; part activité ___% | |
# | HB | Statut fragile ? | Borderline 62–70k : ___% | |
# | HC | Falaise ou érosion ? | Chute avoirs k=0 vs pente k−3→0 | |
# | HD | Effet frontalier ? | Taux frontalier ___% vs résident ___% | |
# | HE | Effet profil ? | Profil le plus exposé : ___ | |
# | HF | Saisonnalité / dynamique ? | Mois de pic : ___ | sortie > entrée MA ? ___ |
# | HG | Réversibilité par cause ? | Retour MA — Flux ___% vs Avoirs ___% | |
# | HH | Ancienneté protège ? | Taux 1-3 mois ___% vs 13+ ___% ; corr ___ | |
#
# **Grilles de lecture :**
# - Si **Avoirs** domine → cibler la rétention d'actifs (épargne/placement) des clients proches du seuil.
# - Si **Flux** domine → enjeu de domiciliation des revenus ; frontaliers à surveiller.
# - Forte part **borderline** + fort **retour MA** → la frontière 62k génère du bruit ;
#   envisager un lissage (moyenne 3 mois) du critère côté banque.
# - Si l'ajout du critère **activité** fait fondre les anomalies → l'inactivité est le vrai
#   mécanisme derrière les clients « financièrement MA mais classés Retail » : cibler la
#   réactivation (relance transactionnelle) plutôt que le seul financier.
# - Part d'**anomalies** encore élevée MALGRÉ l'activité → écart règle/application réelle
#   (lags, critères additionnels) : à clarifier avec les équipes métier.
#
# > Lance le script sur tes données et partage-moi les sorties : on remplit ce
# > tableau et on rédige les conclusions ensemble.
