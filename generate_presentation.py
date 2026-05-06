#!/usr/bin/env python3
"""Generate the CLV Acquisition Model presentation — French, calmer theme."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# -- calm palette --
SLATE = RGBColor(0x34, 0x49, 0x5E)
OCEAN = RGBColor(0x4A, 0x7C, 0x94)
SAGE = RGBColor(0x6B, 0x9E, 0x78)
WARM_SAND = RGBColor(0xC4, 0xA8, 0x82)
SOFT_CORAL = RGBColor(0xCF, 0x7C, 0x6E)
MUTED_ROSE = RGBColor(0xB5, 0x6B, 0x6B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
OFF_WHITE = RGBColor(0xFA, 0xF9, 0xF6)
LIGHT_WARM = RGBColor(0xF5, 0xF0, 0xEB)
LIGHT_SAGE = RGBColor(0xEE, 0xF4, 0xEF)
LIGHT_OCEAN = RGBColor(0xEC, 0xF3, 0xF6)
TEXT_MAIN = RGBColor(0x2D, 0x3B, 0x45)
TEXT_MUTED = RGBColor(0x7A, 0x86, 0x8E)
DIVIDER = RGBColor(0xD5, 0xD0, 0xCA)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW = prs.slide_width
SH = prs.slide_height

TOTAL = 14

def add_bg(slide, color=OFF_WHITE):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color

def rect(slide, l, t, w, h, color, line=None):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = color
    if line: s.line.color.rgb = line; s.line.width = Pt(1)
    else: s.line.fill.background()
    return s

def rrect(slide, l, t, w, h, color, line=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = color
    if line: s.line.color.rgb = line; s.line.width = Pt(1.2)
    else: s.line.fill.background()
    return s

def txb(slide, l, t, w, h):
    return slide.shapes.add_textbox(l, t, w, h)

def stxt(shape, text, sz=14, bold=False, color=TEXT_MAIN, align=PP_ALIGN.LEFT, fn="Calibri"):
    tf = shape.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.text = text
    p.font.size = Pt(sz); p.font.bold = bold; p.font.color.rgb = color; p.font.name = fn; p.alignment = align
    return tf

def apar(tf, text, sz=14, bold=False, color=TEXT_MAIN, sp=Pt(4), align=PP_ALIGN.LEFT, fn="Calibri"):
    p = tf.add_paragraph(); p.text = text
    p.font.size = Pt(sz); p.font.bold = bold; p.font.color.rgb = color; p.font.name = fn
    p.space_before = sp; p.alignment = align
    return p

def title_bar(sl, title, sub=None):
    rect(sl, Inches(0), Inches(0), SW, Inches(1.15), SLATE)
    t = txb(sl, Inches(0.8), Inches(0.18), Inches(11), Inches(0.55))
    stxt(t, title, sz=26, bold=True, color=WHITE)
    if sub:
        t2 = txb(sl, Inches(0.8), Inches(0.65), Inches(11), Inches(0.4))
        stxt(t2, sub, sz=15, color=RGBColor(0xBF, 0xCC, 0xD4))
    rect(sl, Inches(0), Inches(1.15), SW, Inches(0.04), OCEAN)

def snum(sl, n):
    t = txb(sl, Inches(12.1), Inches(7.05), Inches(1.1), Inches(0.35))
    stxt(t, f"{n} / {TOTAL}", sz=10, color=TEXT_MUTED, align=PP_ALIGN.RIGHT)

def card(sl, l, t, w, h, title, bullets, tc=SLATE, bg=WHITE, border=DIVIDER):
    b = rrect(sl, l, t, w, h, bg, line=border)
    b.text_frame.word_wrap = True; b.text_frame.margin_left = Inches(0.2)
    b.text_frame.margin_right = Inches(0.15); b.text_frame.margin_top = Inches(0.15)
    stxt(b, title, sz=15, bold=True, color=tc)
    for bu in bullets:
        apar(b.text_frame, f"  {bu}", sz=12, color=TEXT_MAIN, sp=Pt(4))
    return b

# ══════════════════════════════════════════════════════════════════════════════
# 1 — Title
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, SLATE)
rect(sl, Inches(0), Inches(3.0), SW, Inches(1.5), OCEAN)
rect(sl, Inches(0), Inches(4.5), SW, Inches(0.05), SAGE)

t = txb(sl, Inches(1), Inches(1.2), Inches(11), Inches(1.0))
stxt(t, "Modele CLV — Nouvelles Acquisitions", sz=38, bold=True, color=WHITE)
t2 = txb(sl, Inches(1), Inches(3.2), Inches(11), Inches(1.1))
tf = stxt(t2, "Prediction du PNB des nouveaux clients", sz=24, color=WHITE)
apar(tf, "Architecture trimestrielle T / T+1 / T+3", sz=18, color=RGBColor(0xBF, 0xCC, 0xD4), sp=Pt(10))
t3 = txb(sl, Inches(1), Inches(5.4), Inches(11), Inches(0.8))
tf3 = stxt(t3, "Equipe Data & Analytics", sz=15, color=RGBColor(0x99, 0xAA, 0xBB))
apar(tf3, "Mai 2026", sz=13, color=RGBColor(0x99, 0xAA, 0xBB), sp=Pt(4))
snum(sl, 1)

# ══════════════════════════════════════════════════════════════════════════════
# 2 — Sommaire
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl); title_bar(sl, "Sommaire")
items = [
    "Contexte metier et objectif",
    "Architecture bi-modele : PNB + Attrition = CLV",
    "Fenetrage glissant T / T+1 / T+3",
    "Cohortes et pipeline d'entrainement",
    "Familles de donnees et features",
    "Definition de la variable cible",
    "Entrainement et evaluation du modele",
    "Calcul de la CLV : combinaison PNB et attrition",
    "Cycle operationnel et transition",
    "Risques et prochaines etapes",
]
for i, label in enumerate(items):
    y = Inches(1.65) + Inches(i * 0.52)
    c = sl.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1.5), y, Inches(0.4), Inches(0.4))
    c.fill.solid(); c.fill.fore_color.rgb = OCEAN if i % 2 == 0 else SLATE; c.line.fill.background()
    stxt(c, str(i+1), sz=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    c.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    t = txb(sl, Inches(2.2), y + Inches(0.04), Inches(9), Inches(0.38))
    stxt(t, label, sz=17, color=TEXT_MAIN)
snum(sl, 2)

# ══════════════════════════════════════════════════════════════════════════════
# 3 — Contexte
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Contexte Metier et Objectif", "Pourquoi un modele dedie aux nouveaux clients ?")

card(sl, Inches(0.5), Inches(1.6), Inches(5.8), Inches(2.5),
     "Le probleme", [
         "Les nouveaux clients n'ont pas d'historique — le modele CLV existant ne peut pas les scorer",
         "Les 12 premiers mois sont critiques : les comportements d'engagement se fixent",
         "Le business a besoin de predictions precoces pour allouer conseillers et campagnes",
     ], tc=SOFT_CORAL, border=SOFT_CORAL)

card(sl, Inches(6.8), Inches(1.6), Inches(5.8), Inches(2.5),
     "La solution", [
         "Un modele de regression PNB dedie aux nouvelles acquisitions",
         "Predit le PNB total de l'acquisition a la fin de l'annee (10-12 mois)",
         "Utilise les signaux comportementaux precoces (4-6 mois) + snapshot produits",
     ], tc=SAGE, border=SAGE)

card(sl, Inches(0.5), Inches(4.5), Inches(12.1), Inches(2.3),
     "Donnees disponibles — Janvier 2023 a Mars 2026", [
         "Fichiers clients : client_id, date creation, segment (Mass Affluent / Mass Retail / MR with Potential), profession, nationalite",
         "PNB mensuel : par client, par mois, depuis les systemes PnL internes",
         "Snapshots equipements : CSV trimestriels avec quantites de produits detenus (comptes, cartes, epargne, assurance, credit, ...)",
     ], tc=SLATE)
snum(sl, 3)

# ══════════════════════════════════════════════════════════════════════════════
# 4 — Architecture bi-modele
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Architecture Bi-Modele", "Prediction PNB + Prediction Attrition = CLV")

nbi = rrect(sl, Inches(0.8), Inches(1.8), Inches(3.6), Inches(3.0), LIGHT_OCEAN, line=OCEAN)
tf = stxt(nbi, "MODELE 1 — Regression PNB", sz=15, bold=True, color=SLATE, align=PP_ALIGN.CENTER)
apar(tf, "", sz=5)
apar(tf, "Entree : features client a T+1", sz=12, color=TEXT_MAIN, align=PP_ALIGN.CENTER)
apar(tf, "(segment, produits, PNB precoce, ...)", sz=11, color=TEXT_MUTED, align=PP_ALIGN.CENTER)
apar(tf, "", sz=8)
apar(tf, "Sortie :", sz=12, bold=True, color=SLATE, align=PP_ALIGN.CENTER)
apar(tf, "PNB predit (10-12 mois)", sz=14, bold=True, color=SAGE, align=PP_ALIGN.CENTER)
apar(tf, "", sz=8)
apar(tf, "Statut : EN COURS", sz=11, bold=True, color=OCEAN, align=PP_ALIGN.CENTER)

churn = rrect(sl, Inches(5.0), Inches(1.8), Inches(3.6), Inches(3.0), RGBColor(0xF8, 0xEE, 0xED), line=SOFT_CORAL)
tf2 = stxt(churn, "MODELE 2 — Classification Attrition", sz=15, bold=True, color=SOFT_CORAL, align=PP_ALIGN.CENTER)
apar(tf2, "", sz=5)
apar(tf2, "Entree : memes features client", sz=12, color=TEXT_MAIN, align=PP_ALIGN.CENTER)
apar(tf2, "+ signaux d'engagement", sz=11, color=TEXT_MUTED, align=PP_ALIGN.CENTER)
apar(tf2, "", sz=8)
apar(tf2, "Sortie :", sz=12, bold=True, color=SLATE, align=PP_ALIGN.CENTER)
apar(tf2, "P(attrition) → Survie S(t)", sz=14, bold=True, color=SOFT_CORAL, align=PP_ALIGN.CENTER)
apar(tf2, "", sz=8)
apar(tf2, "Statut : PHASE 2", sz=11, bold=True, color=TEXT_MUTED, align=PP_ALIGN.CENTER)

arrow = sl.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(5.15), Inches(5.0), Inches(3.3), Inches(0.65))
arrow.fill.solid(); arrow.fill.fore_color.rgb = SLATE; arrow.line.fill.background()
stxt(arrow, "COMBINAISON", sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

clv = rrect(sl, Inches(3.5), Inches(5.8), Inches(6.6), Inches(1.2), SLATE)
tf3 = stxt(clv, "CLV = Σ  [ PNB_predit × croissance^t × S(t) / (1+r)^t ]", sz=17, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
apar(tf3, "Valeur vie client actualisee sur 3 ans", sz=12, color=RGBColor(0xBF, 0xCC, 0xD4), align=PP_ALIGN.CENTER)

t = txb(sl, Inches(9.2), Inches(2.0), Inches(3.8), Inches(2.6))
tf4 = stxt(t, "Transition du cycle de vie", sz=14, bold=True, color=SLATE)
apar(tf4, "", sz=5)
apar(tf4, "Mois 0 – 12", sz=12, bold=True, color=OCEAN)
apar(tf4, "Ce modele (nouvelles acquisitions)", sz=11, color=TEXT_MAIN)
apar(tf4, "", sz=5)
apar(tf4, "Mois 12+", sz=12, bold=True, color=OCEAN)
apar(tf4, "Bascule vers le modele CLV etabli (horizon 3 ans existant)", sz=11, color=TEXT_MAIN)
snum(sl, 4)

# ══════════════════════════════════════════════════════════════════════════════
# 5 — Fenetrage T/T+1/T+3
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Fenetrage Glissant : T / T+1 / T+3", "Cadence trimestrielle alignee sur les operations")

for i, (lb, desc, bg, hl) in enumerate([
    ("T", "Trimestre d'acquisition", LIGHT_OCEAN, OCEAN),
    ("T+1", "Fin fenetre d'observation\n(Snapshot & Features)", LIGHT_SAGE, SAGE),
    ("T+3", "Fin fenetre cible\n(PNB total)", RGBColor(0xF8, 0xEE, 0xED), SOFT_CORAL),
]):
    x = Inches(0.6 + i * 4.2)
    b = rrect(sl, x, Inches(1.6), Inches(3.7), Inches(1.25), bg, line=hl)
    tf = stxt(b, lb, sz=22, bold=True, color=hl, align=PP_ALIGN.CENTER)
    apar(tf, desc, sz=12, color=TEXT_MAIN, align=PP_ALIGN.CENTER, sp=Pt(5))

y0 = Inches(3.2)
t = txb(sl, Inches(0.5), y0, Inches(12), Inches(0.35))
stxt(t, "Exemple : Cohorte Q1 2024", sz=15, bold=True, color=SLATE)

quarters = [("Q1 2024\n(T)", OCEAN), ("Q2 2024\n(T+1)", SAGE), ("Q3 2024\n(T+2)", TEXT_MUTED), ("Q4 2024\n(T+3)", SOFT_CORAL)]
bw, bh, by = Inches(2.8), Inches(0.6), y0 + Inches(0.45)
for i, (ql, qc) in enumerate(quarters):
    r = rrect(sl, Inches(0.6 + i * 3.0), by, bw, bh, qc)
    stxt(r, ql, sz=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    r.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

cy = by + Inches(0.9)
t = txb(sl, Inches(0.6), cy, Inches(4), Inches(0.28))
stxt(t, "Client A (entre en janvier)", sz=12, bold=True, color=SLATE)
rrect(sl, Inches(0.6), cy+Inches(0.32), Inches(5.8), Inches(0.38), LIGHT_OCEAN, line=OCEAN)
stxt(rrect(sl, Inches(0.6), cy+Inches(0.32), Inches(5.8), Inches(0.38), LIGHT_OCEAN, line=OCEAN),
     "6 mois d'observation", sz=10, color=OCEAN, align=PP_ALIGN.CENTER)
rrect_t = rrect(sl, Inches(0.6), cy+Inches(0.75), Inches(11.8), Inches(0.38), RGBColor(0xF8, 0xEE, 0xED), line=SOFT_CORAL)
stxt(rrect_t, "12 mois de PNB cible (n_mois_nbi = 12)", sz=10, color=SOFT_CORAL, align=PP_ALIGN.CENTER)

cy2 = cy + Inches(1.4)
t = txb(sl, Inches(0.6), cy2, Inches(4), Inches(0.28))
stxt(t, "Client B (entre en mars)", sz=12, bold=True, color=SLATE)
rrect(sl, Inches(2.4), cy2+Inches(0.32), Inches(4.0), Inches(0.38), LIGHT_OCEAN, line=OCEAN)
stxt(rrect(sl, Inches(2.4), cy2+Inches(0.32), Inches(4.0), Inches(0.38), LIGHT_OCEAN, line=OCEAN),
     "4 mois d'obs.", sz=10, color=OCEAN, align=PP_ALIGN.CENTER)
rrect_t2 = rrect(sl, Inches(2.4), cy2+Inches(0.75), Inches(10.0), Inches(0.38), RGBColor(0xF8, 0xEE, 0xED), line=SOFT_CORAL)
stxt(rrect_t2, "10 mois de PNB cible (n_mois_nbi = 10)", sz=10, color=SOFT_CORAL, align=PP_ALIGN.CENTER)
snum(sl, 5)

# ══════════════════════════════════════════════════════════════════════════════
# 6 — Variabilite des fenetres
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Variabilite des Fenetres", "La position dans le trimestre determine la longueur des fenetres")

headers = ["Mois dans T", "n_mois_observation", "n_mois_nbi", "Exemple (Q1)"]
rows = [
    ["1er mois", "6 mois", "12 mois", "Janvier → Juin (obs) / Dec (cible)"],
    ["2e mois", "5 mois", "11 mois", "Fevrier → Juin (obs) / Dec (cible)"],
    ["3e mois", "4 mois", "10 mois", "Mars → Juin (obs) / Dec (cible)"],
]
cw = [Inches(2.2), Inches(2.8), Inches(2.5), Inches(5.0)]
ts = sl.shapes.add_table(4, 4, Inches(0.5), Inches(1.6), sum(cw), Inches(1.8))
tbl = ts.table
for i, w in enumerate(cw): tbl.columns[i].width = w
for j, h in enumerate(headers):
    c = tbl.cell(0, j); c.text = h
    for p in c.text_frame.paragraphs: p.font.size=Pt(12); p.font.bold=True; p.font.color.rgb=WHITE; p.alignment=PP_ALIGN.CENTER
    c.fill.solid(); c.fill.fore_color.rgb = SLATE
for i, row in enumerate(rows):
    for j, v in enumerate(row):
        c = tbl.cell(i+1, j); c.text = v
        for p in c.text_frame.paragraphs: p.font.size=Pt(11); p.font.color.rgb=TEXT_MAIN; p.alignment=PP_ALIGN.CENTER
        c.fill.solid(); c.fill.fore_color.rgb = WHITE if i%2==0 else LIGHT_WARM

card(sl, Inches(0.5), Inches(3.8), Inches(5.8), Inches(3.2),
     "Avantages du design", [
         "Cadence trimestrielle alignee sur les operations business",
         "Snapshot equipements a T+1 = etat au moment de la prediction",
         "Minimum 3 mois complets garantis meme pour les entrants tardifs",
         "10+ cohortes trimestrielles d'entrainement (vs 2-3 annuelles)",
         "Fenetrage transparent et auditable",
     ], tc=SAGE, border=SAGE)

card(sl, Inches(6.8), Inches(3.8), Inches(5.8), Inches(3.2),
     "Features de controle", [
         "n_mois_nbi (10/11/12) permet au modele de relativiser la duree",
         "n_mois_observation (4/5/6) capture la maturite des features",
         "pnb_moyen_obs : PNB mensuel moyen sur la fenetre d'observation",
         "pnb_moyen_remaining : PNB mensuel moyen sur la fenetre de prediction",
         "Hypotheses HA11-HA13 valident ces choix de design",
     ], tc=OCEAN, border=OCEAN)
snum(sl, 6)

# ══════════════════════════════════════════════════════════════════════════════
# 7 — Cohortes
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Cohortes et Pipeline d'Entrainement", "Validation temporelle walk-forward — zero fuite de donnees futures")

cd = [
    ("Q1 2023","Q2 2023","Q4 2023","TRAIN"), ("Q2 2023","Q3 2023","Q1 2024","TRAIN"),
    ("Q3 2023","Q4 2023","Q2 2024","TRAIN"), ("Q4 2023","Q1 2024","Q3 2024","TRAIN"),
    ("Q1 2024","Q2 2024","Q4 2024","TRAIN"), ("Q2 2024","Q3 2024","Q1 2025","TRAIN"),
    ("Q3 2024","Q4 2024","Q2 2025","TRAIN"), ("Q4 2024","Q1 2025","Q3 2025","TRAIN"),
    ("Q1 2025","Q2 2025","Q4 2025","TEST"),  ("Q2 2025","Q3 2025","Q1 2026","TEST"),
    ("Q4 2025","Q1 2026","Q3 2026","SCORE"),
]
ts = sl.shapes.add_table(12, 4, Inches(0.5), Inches(1.6), Inches(8.5), Inches(5.2))
tbl = ts.table
tbl.columns[0].width=Inches(2.0); tbl.columns[1].width=Inches(2.2); tbl.columns[2].width=Inches(2.0); tbl.columns[3].width=Inches(2.3)
for j, h in enumerate(["Cohorte (T)", "Observation (T+1)", "Fin cible (T+3)", "Usage"]):
    c = tbl.cell(0, j); c.text = h
    for p in c.text_frame.paragraphs: p.font.size=Pt(11); p.font.bold=True; p.font.color.rgb=WHITE; p.alignment=PP_ALIGN.CENTER
    c.fill.solid(); c.fill.fore_color.rgb = SLATE
for i, (a, b, cc, u) in enumerate(cd):
    for j, v in enumerate([a, b, cc, u]):
        c = tbl.cell(i+1, j); c.text = v
        for p in c.text_frame.paragraphs:
            p.font.size=Pt(10); p.alignment=PP_ALIGN.CENTER
            if u=="TRAIN": p.font.color.rgb=TEXT_MAIN
            elif u=="TEST": p.font.color.rgb=WARM_SAND; p.font.bold=(j==3)
            else: p.font.color.rgb=SAGE; p.font.bold=(j==3)
        c.fill.solid()
        if u=="TRAIN": c.fill.fore_color.rgb = WHITE if i%2==0 else LIGHT_WARM
        elif u=="TEST": c.fill.fore_color.rgb = RGBColor(0xFB, 0xF4, 0xED)
        else: c.fill.fore_color.rgb = LIGHT_SAGE

card(sl, Inches(9.4), Inches(1.6), Inches(3.6), Inches(5.2),
     "Logique du pipeline", [
         "8 cohortes pour l'entrainement",
         "2 cohortes pour le test (holdout temporel)",
         "Score = derniere cohorte dont le snapshot T+1 est disponible",
         "",
         "Walk-forward : 7 iterations, jamais d'entrainement sur des donnees futures",
         "",
         "Re-entraine chaque trimestre avec fenetre d'entrainement croissante",
     ], tc=SLATE, border=SLATE)
snum(sl, 7)

# ══════════════════════════════════════════════════════════════════════════════
# 8 — Familles de donnees
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Familles de Donnees et Features", "Quatre piliers du signal predictif")

families = [
    ("Features\nDeclaratives", SLATE, [
        "Segment (Mass Affluent, Mass Retail, MR w/ Potential)",
        "Profession (Cadre, Salarie, Jeune Actif, ...)",
        "Trimestre et annee d'acquisition",
        "n_mois_observation, n_mois_nbi",
        "Nationalite, age, canal (si disponibles)",
    ]),
    ("Comportementales\n(PNB precoce)", OCEAN, [
        "pnb_m1 ... pnb_m6 (PNB mensuel)",
        "pnb_cumul_obs (PNB cumule observe)",
        "pnb_moyen_obs (PNB moyen / mois obs)",
        "obs_slope (tendance PNB)",
        "obs_volatility, obs_active_months",
    ]),
    ("Equipements\n(Snapshot T+1)", SAGE, [
        "qty_* (quantite par produit detenu)",
        "n_produits_total (nombre de produits)",
        "Comptes, cartes, epargne, assurance, credit, ...",
        "Colonnes de flux (encours, entrees/sorties)",
        "Domiciliation du salaire (signal cle)",
    ]),
    ("Features\nd'Interaction", WARM_SAND, [
        "segment × n_produits",
        "pnb_cumul_obs / n_produits",
        "obs_slope × n_produits",
        "Construites a l'entrainement",
        "Capturent les effets croises",
    ]),
]
for i, (title, color, bullets) in enumerate(families):
    x = Inches(0.4 + i * 3.2)
    hdr = rrect(sl, x, Inches(1.65), Inches(2.95), Inches(0.8), color)
    stxt(hdr, title, sz=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    hdr.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    body = rrect(sl, x, Inches(2.5), Inches(2.95), Inches(4.4), WHITE, line=color)
    body.text_frame.word_wrap = True; body.text_frame.margin_left = Inches(0.15); body.text_frame.margin_top = Inches(0.1)
    tf = body.text_frame
    for j, b in enumerate(bullets):
        if j == 0: p = tf.paragraphs[0]
        else: p = tf.add_paragraph()
        p.text = f"• {b}"; p.font.size = Pt(11); p.font.color.rgb = TEXT_MAIN; p.space_before = Pt(5)
snum(sl, 8)

# ══════════════════════════════════════════════════════════════════════════════
# 9 — Variable cible
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Definition de la Variable Cible", "Ce que le modele predit et pourquoi")

main = rrect(sl, Inches(0.5), Inches(1.65), Inches(7.5), Inches(1.7), LIGHT_OCEAN, line=OCEAN)
tf = stxt(main, "Cible principale : pnb_total", sz=18, bold=True, color=SLATE)
apar(tf, "", sz=4)
apar(tf, "pnb_total = SUM( pnb_m1 ... pnb_m{n_mois_nbi} )", sz=15, bold=True, color=OCEAN, fn="Consolas")
apar(tf, "PNB cumule brut de l'acquisition a la fin de T+3 (10-12 mois)", sz=12, color=TEXT_MAIN, sp=Pt(6))
apar(tf, "n_mois_nbi fourni comme feature pour que le modele relativise la duree", sz=12, color=TEXT_MUTED)

alt = rrect(sl, Inches(8.5), Inches(1.65), Inches(4.5), Inches(1.7), RGBColor(0xF8, 0xEE, 0xED), line=WARM_SAND)
tf2 = stxt(alt, "Alternative : pnb_remaining", sz=15, bold=True, color=WARM_SAND)
apar(tf2, "", sz=4)
apar(tf2, "= pnb_total - pnb_cumul_obs", sz=13, bold=True, color=SOFT_CORAL, fn="Consolas")
apar(tf2, "Isole la partie non observee", sz=11, color=TEXT_MAIN, sp=Pt(6))
apar(tf2, "Testee dans l'hypothese HA12", sz=11, color=TEXT_MUTED)

card(sl, Inches(0.5), Inches(3.7), Inches(5.8), Inches(3.2),
     "Pourquoi T+3 (~12 mois) ?", [
         "Cycle bancaire annuel naturel (cotisations carte, assurance)",
         "Un credit met 3-6 mois a generer du PNB — horizon plus court insuffisant",
         "Alignement trimestriel pour un deploiement operationnel direct",
         "Apres 12 mois, le client bascule vers le modele CLV etabli",
         "10-12 mois capture la premiere annee complete de relation",
     ], tc=SLATE, border=SLATE)

card(sl, Inches(6.8), Inches(3.7), Inches(5.8), Inches(3.2),
     "Plancher mecanique de correlation", [
         "pnb_cumul_obs est un SOUS-ENSEMBLE de pnb_total",
         "Cree une correlation artificielle ~ sqrt(n_obs / n_nbi)",
         "r(obs, total) gonfle de ~0.15-0.25 par rapport au vrai signal",
         "HA4b teste la correlation sur pnb_remaining pour isoler le signal reel",
         "Ce n'est PAS du data leakage — mais doit etre pris en compte en evaluation",
     ], tc=WARM_SAND, border=WARM_SAND)
snum(sl, 9)

# ══════════════════════════════════════════════════════════════════════════════
# 10 — Entrainement
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Entrainement et Evaluation du Modele")

mc = rrect(sl, Inches(0.5), Inches(1.65), Inches(5.5), Inches(2.8), LIGHT_OCEAN, line=OCEAN)
tf = stxt(mc, "Modele : Gradient Boosting Regressor", sz=17, bold=True, color=SLATE)
apar(tf, "", sz=5)
for line in ["n_estimators = 300", "max_depth = 4", "learning_rate = 0.05",
             "loss = 'huber'  (robuste aux outliers PNB)", "subsample = 0.8", "min_samples_leaf = 20"]:
    apar(tf, line, sz=12, color=TEXT_MAIN, fn="Consolas")

mc2 = rrect(sl, Inches(6.5), Inches(1.65), Inches(6.3), Inches(2.8), WHITE, line=SLATE)
tf2 = stxt(mc2, "Metriques d'evaluation", sz=17, bold=True, color=SLATE)
apar(tf2, "", sz=5)
apar(tf2, "MAE (Erreur Absolue Moyenne) — cible : < 20% du PNB moyen", sz=12, color=TEXT_MAIN)
apar(tf2, "RMSE — penalise les erreurs importantes", sz=12, color=TEXT_MAIN, sp=Pt(5))
apar(tf2, "R² — cible : > 0.30 (donnees limitees)", sz=12, color=TEXT_MAIN, sp=Pt(5))
apar(tf2, "MAPE — cible : < 30%", sz=12, color=TEXT_MAIN, sp=Pt(5))
apar(tf2, "", sz=5)
apar(tf2, "Toutes mesurees sur holdout temporel (pas de k-fold)", sz=11, bold=True, color=OCEAN)

card(sl, Inches(0.5), Inches(4.8), Inches(12.3), Inches(2.1),
     "Validation Walk-Forward Temporelle (7 iterations)", [
         "Iter 1 : Train Q1-Q2 2023 → Test Q3 2023  |  Iter 2 : Train Q1-Q3 2023 → Test Q4 2023  |  ...  |  Iter 7 : Train Q1 2023 - Q2 2024 → Test Q3 2024",
         "Fenetre d'entrainement croissante, test sur un seul trimestre — simule le deploiement reel, zero fuite temporelle",
         "La perte Huber gere les clients a PNB negatif et les outliers sans biaiser l'ensemble du fit",
     ], tc=SLATE, border=SLATE)
snum(sl, 10)

# ══════════════════════════════════════════════════════════════════════════════
# 11 — Calcul CLV
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Calcul de la CLV", "Combinaison de la prediction PNB et du taux de survie")

fb = rrect(sl, Inches(1.0), Inches(1.65), Inches(11.3), Inches(1.7), SLATE)
tf = stxt(fb, "", sz=10)
tf.paragraphs[0].alignment = PP_ALIGN.CENTER
apar(tf, "CLV  =  Σ(t=1..3)  [ PNB_predit  ×  croissance^(t-1)  ×  S(t)  /  (1 + r)^t ]", sz=22, bold=True, color=WHITE, align=PP_ALIGN.CENTER, fn="Consolas")
apar(tf, "", sz=6)
apar(tf, "Valeur vie client actualisee sur 3 ans pour les nouvelles acquisitions", sz=14, color=RGBColor(0xBF, 0xCC, 0xD4), align=PP_ALIGN.CENTER)

comps = [
    ("PNB_predit", "Modele de\nRegression PNB", OCEAN, [
        "Sortie de ce modele", "PNB predit pour les ~12 premiers mois", "Sert de revenu annuel de base",
    ]),
    ("croissance", "Facteur de\nCroissance", SAGE, [
        "Taux de croissance annuel du PNB", "A calibrer (~1.05-1.10)", "Compte la maturation de la relation",
    ]),
    ("S(t)", "Probabilite\nde Survie", SOFT_CORAL, [
        "Issue du modele d'attrition (Phase 2)", "S(t) = P(client encore actif a l'annee t)", "S(1) ≈ 0.85-0.95 typiquement",
    ]),
    ("(1+r)^t", "Facteur\nd'Actualisation", WARM_SAND, [
        "Valeur temps de l'argent", "r = 5% (cout du capital de la banque)", "Les revenus futurs valent moins qu'aujourd'hui",
    ]),
]
for i, (sym, title, color, bul) in enumerate(comps):
    x = Inches(0.4 + i * 3.2)
    hdr = rrect(sl, x, Inches(3.65), Inches(2.95), Inches(0.7), color)
    stxt(hdr, sym, sz=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    hdr.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    body = rrect(sl, x, Inches(4.4), Inches(2.95), Inches(2.3), WHITE, line=color)
    body.text_frame.word_wrap = True; body.text_frame.margin_left = Inches(0.12); body.text_frame.margin_top = Inches(0.08)
    tf = body.text_frame
    for j, b in enumerate(bul):
        if j == 0: p = tf.paragraphs[0]
        else: p = tf.add_paragraph()
        p.text = f"• {b}"; p.font.size = Pt(11); p.font.color.rgb = TEXT_MAIN; p.space_before = Pt(4)
snum(sl, 11)

# ══════════════════════════════════════════════════════════════════════════════
# 12 — Exemple CLV
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Calcul CLV — Exemple Chiffre")

t = txb(sl, Inches(0.5), Inches(1.65), Inches(12), Inches(0.35))
stxt(t, "Client Mass Affluent, entre au Q1 2024, PNB predit = 3 500 EUR / an", sz=15, bold=True, color=SLATE)

ts = sl.shapes.add_table(5, 6, Inches(0.5), Inches(2.2), Inches(12), Inches(2.4))
tbl = ts.table
cws = [Inches(1.5), Inches(2.2), Inches(2.0), Inches(2.0), Inches(2.3), Inches(2.0)]
for i, w in enumerate(cws): tbl.columns[i].width = w
for j, h in enumerate(["Annee t", "PNB × croissance^(t-1)", "S(t)", "Actualisation", "CLV annuelle", "Cumule"]):
    c = tbl.cell(0, j); c.text = h
    for p in c.text_frame.paragraphs: p.font.size=Pt(11); p.font.bold=True; p.font.color.rgb=WHITE; p.alignment=PP_ALIGN.CENTER
    c.fill.solid(); c.fill.fore_color.rgb = SLATE
vals = [
    ["1", "3 500 × 1.00 = 3 500", "0.92", "1.050", "3 067", "3 067"],
    ["2", "3 500 × 1.08 = 3 780", "0.85", "1.103", "2 916", "5 983"],
    ["3", "3 500 × 1.17 = 4 082", "0.78", "1.158", "2 748", "8 731"],
    ["Total", "", "", "", "", "8 731 EUR"],
]
for i, row in enumerate(vals):
    for j, v in enumerate(row):
        c = tbl.cell(i+1, j); c.text = v
        for p in c.text_frame.paragraphs:
            p.font.size=Pt(11); p.alignment=PP_ALIGN.CENTER
            if i==3: p.font.bold=True; p.font.color.rgb=SLATE
            else: p.font.color.rgb=TEXT_MAIN
        c.fill.solid()
        if i==3: c.fill.fore_color.rgb = LIGHT_OCEAN
        else: c.fill.fore_color.rgb = WHITE if i%2==0 else LIGHT_WARM

card(sl, Inches(0.5), Inches(4.9), Inches(5.8), Inches(2.1),
     "Hypotheses (a calibrer)", [
         "Taux de croissance : 8% par an (maturation relation)",
         "Taux d'actualisation : 5% (cout du capital)",
         "Attrition : ~8% / an (S decroit dans le temps)",
     ], tc=TEXT_MUTED, border=DIVIDER)

card(sl, Inches(6.8), Inches(4.9), Inches(5.8), Inches(2.1),
     "Interpretation", [
         "Ce client vaut 8 731 EUR sur 3 ans",
         "Utilisation : allocation conseillers, ROI campagnes, valorisation portefeuille",
         "Apres le mois 12 → transition vers le modele CLV etabli",
     ], tc=SAGE, border=SAGE)
snum(sl, 12)

# ══════════════════════════════════════════════════════════════════════════════
# 13 — Cycle operationnel
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Cycle Operationnel et Transition", "Rythme de scoring trimestriel")

steps = [
    ("1", "Fin de trimestre", "Collecte des donnees :\n• Fichiers PNB mis a jour\n• Snapshot equipements\n• Nouveaux clients identifies", OCEAN),
    ("2", "Re-entrainement", "Expansion du jeu :\n• Ajout derniere cohorte completee\n• Validation walk-forward\n• Comparaison au modele precedent", SLATE),
    ("3", "Scoring", "Pour la derniere cohorte T :\n• Application du modele a T+1\n• Prediction PNB a T+3\n• Calcul de la CLV", SAGE),
    ("4", "Livraison", "Sorties business :\n• Scores CLV par client\n• Agregats par segment\n• Suivi de performance", WARM_SAND),
]
for i, (num, title, desc, color) in enumerate(steps):
    x = Inches(0.4 + i * 3.2)
    c = sl.shapes.add_shape(MSO_SHAPE.OVAL, x + Inches(1.1), Inches(1.65), Inches(0.65), Inches(0.65))
    c.fill.solid(); c.fill.fore_color.rgb = color; c.line.fill.background()
    stxt(c, num, sz=20, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    c.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    t = txb(sl, x, Inches(2.45), Inches(2.95), Inches(0.35))
    stxt(t, title, sz=14, bold=True, color=color, align=PP_ALIGN.CENTER)
    body = rrect(sl, x, Inches(2.85), Inches(2.95), Inches(2.0), WHITE, line=color)
    body.text_frame.word_wrap = True; body.text_frame.margin_left = Inches(0.12); body.text_frame.margin_top = Inches(0.1)
    stxt(body, desc, sz=11, color=TEXT_MAIN)

trans = rrect(sl, Inches(0.5), Inches(5.2), Inches(12.3), Inches(1.8), SLATE)
tf = stxt(trans, "Transition du cycle de vie client", sz=17, bold=True, color=WHITE)
apar(tf, "", sz=5)
apar(tf, "Mois 0 → 12 :  CE MODELE score le client une fois a T+1, prediction valable jusqu'a T+3", sz=13, color=RGBColor(0xBF, 0xCC, 0xD4))
apar(tf, "Mois 12+ :       Le client a 4+ trimestres d'historique → bascule vers le modele CLV etabli (horizon 3 ans)", sz=13, color=RGBColor(0xBF, 0xCC, 0xD4), sp=Pt(5))
apar(tf, "Pas de chevauchement ni de lissage necessaire — passage propre entre les deux modeles", sz=12, color=TEXT_MUTED, sp=Pt(7))
snum(sl, 13)

# ══════════════════════════════════════════════════════════════════════════════
# 14 — Risques et prochaines etapes
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(sl)
title_bar(sl, "Risques, Mitigations et Prochaines Etapes")

card(sl, Inches(0.5), Inches(1.65), Inches(5.8), Inches(2.7),
     "Risques et limites", [
         "Fenetre variable (10-12 mois) biaise les comparaisons de PNB brut",
         "Plancher mecanique de correlation gonfle le R² sur pnb_total",
         "Derive des cohortes : clients 2023 ≠ clients 2025",
         "Saisonnalite confondue avec la longueur de fenetre",
         "Clients frontaliers : profil PNB potentiellement different",
     ], tc=SOFT_CORAL, border=SOFT_CORAL)

card(sl, Inches(6.8), Inches(1.65), Inches(5.8), Inches(2.7),
     "Mitigations", [
         "n_mois_nbi comme feature + HA11 valide la normalisation",
         "HA12 teste pnb_remaining comme cible plus propre",
         "Re-entrainement trimestriel limite l'impact de la derive",
         "HA7 utilise pnb_mensuel_moyen pour comparer equitablement",
         "Variable frontalier comme feature si disponible",
     ], tc=SAGE, border=SAGE)

card(sl, Inches(0.5), Inches(4.7), Inches(12.1), Inches(2.3),
     "Prochaines etapes", [
         "1. Executer et valider les 13 hypotheses (HA1-HA13) sur les donnees preprocessees",
         "2. Analyse Exploratoire des Donnees (EDA) — distributions, correlations, outliers",
         "3. Entrainer le Gradient Boosting V0 avec validation walk-forward",
         "4. Evaluer, iterer sur le feature engineering, tester la cible pnb_remaining",
         "5. Phase 2 : developper le modele d'attrition → combiner dans le pipeline CLV complet",
     ], tc=SLATE, border=SLATE)
snum(sl, 14)

# ── save ─────────────────────────────────────────────────────────────────────
out = "Acquisition_model/presentation/CLV_Acquisition_Model_Presentation.pptx"
prs.save(out)
print(f"Saved: {out} ({len(prs.slides)} slides)")
