#!/usr/bin/env python3
"""Generate the CLV Acquisition Model presentation — vibrant modern design."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ── Premium palette ─────────────────────────────────────────────────────────
# Light-dominant, eye-friendly for corporate presentations
CHARCOAL = RGBColor(0x33, 0x41, 0x55)
DARK_TEXT = RGBColor(0x0F, 0x17, 0x2A)
SLATE_TEXT = RGBColor(0x47, 0x55, 0x69)
LIGHT_TEXT = RGBColor(0x94, 0xA3, 0xB8)
SNOW = RGBColor(0xF8, 0xFA, 0xFC)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
WARM_GRAY = RGBColor(0xF1, 0xF5, 0xF9)
BORDER_GRAY = RGBColor(0xE2, 0xE8, 0xF0)

# Product family colors — consistent throughout
CYAN = RGBColor(0x06, 0xB6, 0xD4)       # Epargne
VIOLET = RGBColor(0x7C, 0x3A, 0xED)     # Investissements
PINK = RGBColor(0xEC, 0x48, 0x99)       # Credit immobilier
AMBER = RGBColor(0xF5, 0x9E, 0x0B)      # Autres credits
LIME = RGBColor(0x84, 0xCC, 0x16)       # Autre PNB

# Light versions for card backgrounds
CYAN_LIGHT = RGBColor(0xEC, 0xFE, 0xFF)
VIOLET_LIGHT = RGBColor(0xF5, 0xF3, 0xFF)
PINK_LIGHT = RGBColor(0xFD, 0xF2, 0xF8)
AMBER_LIGHT = RGBColor(0xFF, 0xFB, 0xEB)
LIME_LIGHT = RGBColor(0xF7, 0xFE, 0xE7)

CORAL = RGBColor(0xF4, 0x3F, 0x5E)      # Emphasis/accent
CORAL_LIGHT = RGBColor(0xFF, 0xF1, 0xF2)

FAMILY_COLORS = [CYAN, VIOLET, PINK, AMBER, LIME]
FAMILY_LIGHTS = [CYAN_LIGHT, VIOLET_LIGHT, PINK_LIGHT, AMBER_LIGHT, LIME_LIGHT]
FAMILY_NAMES = ["Epargne", "Investissements", "Credit Immobilier", "Autres Credits", "Autre PNB"]

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW = prs.slide_width
SH = prs.slide_height

TOTAL = 15


def add_bg(slide, color=SNOW):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def rect(slide, l, t, w, h, color, line=None):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = color
    if line:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    return s


def rrect(slide, l, t, w, h, color, line=None, line_w=1.2):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = color
    if line:
        s.line.color.rgb = line
        s.line.width = Pt(line_w)
    else:
        s.line.fill.background()
    return s


def txb(slide, l, t, w, h):
    return slide.shapes.add_textbox(l, t, w, h)


def stxt(shape, text, sz=14, bold=False, color=DARK_TEXT, align=PP_ALIGN.LEFT, fn="Calibri"):
    tf = shape.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(sz)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = fn
    p.alignment = align
    return tf


def apar(tf, text, sz=14, bold=False, color=DARK_TEXT, sp=Pt(4), align=PP_ALIGN.LEFT, fn="Calibri"):
    p = tf.add_paragraph()
    p.text = text
    p.font.size = Pt(sz)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = fn
    p.space_before = sp
    p.alignment = align
    return p


def title_bar(sl, title, sub=None, accent_color=VIOLET):
    rect(sl, Inches(0), Inches(0), SW, Inches(1.1), CHARCOAL)
    rect(sl, Inches(0), Inches(1.1), SW, Inches(0.06), accent_color)
    t = txb(sl, Inches(0.8), Inches(0.15), Inches(11), Inches(0.55))
    stxt(t, title, sz=26, bold=True, color=WHITE)
    if sub:
        t2 = txb(sl, Inches(0.8), Inches(0.62), Inches(11), Inches(0.4))
        stxt(t2, sub, sz=14, color=LIGHT_TEXT)


def snum(sl, n):
    t = txb(sl, Inches(12.0), Inches(7.05), Inches(1.2), Inches(0.35))
    stxt(t, f"{n} / {TOTAL}", sz=10, color=LIGHT_TEXT, align=PP_ALIGN.RIGHT)


def card(sl, l, t, w, h, title, bullets, accent=CHARCOAL, bg=WHITE):
    rect(sl, l, t, Pt(4), h, accent)
    b = rrect(sl, l, t, w, h, bg, line=BORDER_GRAY)
    b.text_frame.word_wrap = True
    b.text_frame.margin_left = Inches(0.25)
    b.text_frame.margin_right = Inches(0.15)
    b.text_frame.margin_top = Inches(0.15)
    stxt(b, title, sz=15, bold=True, color=accent)
    for bu in bullets:
        apar(b.text_frame, f"  {bu}", sz=12, color=DARK_TEXT, sp=Pt(4))
    rect(sl, l, t, Pt(4), h, accent)
    return b


def family_pill(sl, x, y, w, h, idx):
    s = rrect(sl, x, y, w, h, FAMILY_COLORS[idx])
    stxt(s, FAMILY_NAMES[idx], sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    s.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    return s


# ══════════════════════════════════════════════════════════════════════════════
# 1 — Title
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)

rect(sl, Inches(0), Inches(0), SW, Inches(3.2), CHARCOAL)
for i, c in enumerate(FAMILY_COLORS):
    rect(sl, Inches(i * 2.667), Inches(3.2), Inches(2.667), Inches(0.08), c)

t = txb(sl, Inches(1.2), Inches(0.8), Inches(11), Inches(1.0))
stxt(t, "Modele CLV", sz=44, bold=True, color=WHITE)
t2 = txb(sl, Inches(1.2), Inches(1.6), Inches(11), Inches(0.6))
stxt(t2, "Nouvelles Acquisitions", sz=32, color=RGBColor(0xBD, 0xC5, 0xD1))

t3 = txb(sl, Inches(1.2), Inches(3.8), Inches(11), Inches(1.5))
tf = stxt(t3, "Prediction de la valeur vie client sur 5 ans", sz=20, color=DARK_TEXT)
apar(tf, "5 familles de produits  |  Snapshot a M+3  |  Calibration par deciles", sz=15, color=SLATE_TEXT, sp=Pt(10))

for i in range(5):
    family_pill(sl, Inches(1.2 + i * 2.2), Inches(5.6), Inches(2.0), Inches(0.4), i)

t4 = txb(sl, Inches(1.2), Inches(6.4), Inches(11), Inches(0.8))
tf4 = stxt(t4, "Equipe Data & Analytics", sz=14, color=SLATE_TEXT)
apar(tf4, "Juin 2026", sz=12, color=LIGHT_TEXT, sp=Pt(4))
snum(sl, 1)

# ══════════════════════════════════════════════════════════════════════════════
# 2 — Sommaire
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Sommaire", accent_color=CYAN)

items = [
    ("Contexte metier et objectif", CYAN),
    ("Architecture a 5 sous-modeles", VIOLET),
    ("Les 5 familles de produits", PINK),
    ("Snapshot fixe a M+3", AMBER),
    ("Donnees et pipeline", LIME),
    ("Features du modele", CYAN),
    ("Calibration par deciles", VIOLET),
    ("Formule CLV et decomposition", PINK),
    ("Churn implicite", AMBER),
    ("Exemple CLV chiffre", LIME),
    ("Validation et metriques", CYAN),
    ("Hypotheses et roadmap", VIOLET),
    ("Prochaines etapes", PINK),
]
for i, (label, color) in enumerate(items):
    y = Inches(1.55) + Inches(i * 0.44)
    pill = rrect(sl, Inches(1.2), y, Inches(0.45), Inches(0.35), color)
    stxt(pill, str(i + 3), sz=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    pill.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    t = txb(sl, Inches(1.9), y + Inches(0.02), Inches(9), Inches(0.32))
    stxt(t, label, sz=16, color=DARK_TEXT)
snum(sl, 2)

# ══════════════════════════════════════════════════════════════════════════════
# 3 — Contexte
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Contexte Metier et Objectif", "Pourquoi un modele dedie aux nouveaux clients ?", CYAN)

card(sl, Inches(0.5), Inches(1.55), Inches(5.8), Inches(2.6),
     "Le probleme", [
         "Les nouveaux clients n'ont pas d'historique — le modele CLV existant ne peut pas les scorer",
         "Les premiers mois sont critiques pour l'engagement et la retention",
         "Le business a besoin de predictions precoces pour allouer les conseillers et les campagnes",
         "Il faut identifier d'ou vient la valeur : epargne, investissements, credit, ou services",
     ], accent=CORAL)

card(sl, Inches(6.8), Inches(1.55), Inches(5.8), Inches(2.6),
     "La solution", [
         "5 sous-modeles XGBoost predisant les encours par famille de produit",
         "Snapshot fixe a M+3 : donnees fiables, prediction precoce",
         "Calibration par deciles : predictions lisses et interpretables",
         "CLV decomposee par famille sur un horizon de 5 ans",
     ], accent=CYAN)

card(sl, Inches(0.5), Inches(4.5), Inches(12.1), Inches(2.5),
     "Contexte Luxembourg", [
         "Banque luxembourgeoise — clientele de residents et de frontaliers (France, Belgique, Allemagne)",
         "Segments : Mass Affluent, Mass Retail, Mass Retail with Potential",
         "Enrichissement geographique : STATEC (Institut national de la statistique du Luxembourg)",
         "Les frontaliers ont des salaires plus eleves et des besoins specifiques (transfrontalier)",
         "Donnees disponibles : Janvier 2023 a Mars 2026 (clients, PNB mensuel, equipements trimestriels)",
     ], accent=CHARCOAL)
snum(sl, 3)

# ══════════════════════════════════════════════════════════════════════════════
# 4 — Architecture
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Architecture a 5 Sous-Modeles", "Encours → Marge → NBI → Decile → CLV", VIOLET)

# Input box
inp = rrect(sl, Inches(4.0), Inches(1.5), Inches(5.3), Inches(0.65), WARM_GRAY, line=BORDER_GRAY)
stxt(inp, "Snapshot client a M+3 (equipements, encours, NBI 3 mois, declaratif)",
     sz=12, bold=True, color=CHARCOAL, align=PP_ALIGN.CENTER)
inp.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

# 5 model boxes
model_labels = [
    ("XGBoost\nEpargne", "encours"),
    ("XGBoost\nInvest.", "encours"),
    ("XGBoost\nCr. Immo", "encours"),
    ("XGBoost\nAut. Credits", "encours"),
    ("XGBoost\nAutre PNB", "NBI direct"),
]
for i, (label, pred_type) in enumerate(model_labels):
    x = Inches(0.3 + i * 2.55)
    box = rrect(sl, x, Inches(2.5), Inches(2.3), Inches(1.0), FAMILY_LIGHTS[i], line=FAMILY_COLORS[i], line_w=2)
    stxt(box, label, sz=12, bold=True, color=FAMILY_COLORS[i], align=PP_ALIGN.CENTER)
    box.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    arrow_t = txb(sl, x + Inches(0.6), Inches(3.55), Inches(1.1), Inches(0.3))
    stxt(arrow_t, f"↓ {pred_type}", sz=10, color=SLATE_TEXT, align=PP_ALIGN.CENTER)

# Margin multiplication row
margins = ["x t_s", "x t_i", "x t_m", "x t_c", "(direct)"]
for i, m in enumerate(margins):
    x = Inches(0.3 + i * 2.55)
    mg = rrect(sl, x, Inches(3.85), Inches(2.3), Inches(0.45), WHITE, line=FAMILY_COLORS[i])
    stxt(mg, m, sz=12, bold=True, color=FAMILY_COLORS[i], align=PP_ALIGN.CENTER)
    mg.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

# NBI row
for i in range(5):
    x = Inches(0.3 + i * 2.55)
    nbi = rrect(sl, x, Inches(4.5), Inches(2.3), Inches(0.45), FAMILY_COLORS[i])
    nbi_labels = ["NBI Ep.", "NBI Inv.", "NBI Immo", "NBI Cr.", "NBI Autre"]
    stxt(nbi, nbi_labels[i], sz=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    nbi.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

# Decile row
dec = rrect(sl, Inches(0.3), Inches(5.15), Inches(12.7), Inches(0.55), WARM_GRAY, line=CHARCOAL)
stxt(dec, "Calibration par deciles D1-D10 → chaque client recoit la moyenne observee de son decile",
     sz=13, bold=True, color=CHARCOAL, align=PP_ALIGN.CENTER)
dec.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

# CLV box
clv = rrect(sl, Inches(2.5), Inches(5.95), Inches(8.3), Inches(1.1), CHARCOAL)
tf = stxt(clv, "CLV = Σ(t=1..5) [ NBI_total × g^(t-1) / (1+r)^t ]",
          sz=20, bold=True, color=WHITE, align=PP_ALIGN.CENTER, fn="Consolas")
apar(tf, "Valeur vie client actualisee sur 5 ans — decomposable par famille",
     sz=12, color=LIGHT_TEXT, align=PP_ALIGN.CENTER, sp=Pt(6))
snum(sl, 4)

# ══════════════════════════════════════════════════════════════════════════════
# 5 — Les 5 familles
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Les 5 Familles de Produits", "Chaque famille a son propre sous-modele et sa propre table de deciles", PINK)

families_data = [
    ("Epargne\nBilan", "Solde moyen des\ncomptes d'epargne", "EUR\n(encours)", "x t_s\n(marge epargne)"),
    ("Investissements\nFinanciers", "Valeur des\nplacements (AuM)", "EUR\n(encours)", "x t_i\n(marge invest.)"),
    ("Credit\nImmobilier", "Encours des\nprets immobiliers", "EUR\n(encours)", "x t_m\n(marge immo)"),
    ("Autres\nCredits", "Encours credits\nconso, revolving", "EUR\n(encours)", "x t_c\n(marge credit)"),
    ("Autre\nPNB", "Commissions,\nassurances, cartes", "EUR\n(NBI direct)", "Pas de\nconversion"),
]

for i, (name, pred, unit, conv) in enumerate(families_data):
    x = Inches(0.3 + i * 2.55)
    header = rrect(sl, x, Inches(1.5), Inches(2.3), Inches(0.85), FAMILY_COLORS[i])
    stxt(header, name, sz=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    header.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    body = rrect(sl, x, Inches(2.4), Inches(2.3), Inches(3.6), WHITE, line=FAMILY_COLORS[i], line_w=1.5)
    body.text_frame.word_wrap = True
    body.text_frame.margin_left = Inches(0.12)
    body.text_frame.margin_top = Inches(0.12)
    tf = stxt(body, "Prediction", sz=11, bold=True, color=SLATE_TEXT)
    apar(tf, pred, sz=12, color=DARK_TEXT, sp=Pt(3))
    apar(tf, "", sz=6)
    apar(tf, "Unite", sz=11, bold=True, color=SLATE_TEXT, sp=Pt(8))
    apar(tf, unit, sz=12, color=DARK_TEXT, sp=Pt(3))
    apar(tf, "", sz=6)
    apar(tf, "Conversion NBI", sz=11, bold=True, color=SLATE_TEXT, sp=Pt(8))
    apar(tf, conv, sz=12, bold=True, color=FAMILY_COLORS[i], sp=Pt(3))

# Bottom note
note = rrect(sl, Inches(0.5), Inches(6.3), Inches(12.3), Inches(0.8), WARM_GRAY, line=BORDER_GRAY)
tf = stxt(note, "Les modeles 1-4 predisent des encours convertis en NBI via les marges fournies par la Finance (deja recues).",
          sz=12, color=DARK_TEXT, align=PP_ALIGN.CENTER)
apar(tf, "Le modele 5 predit du NBI directement (commissions et frais non lies a un encours).",
     sz=12, color=SLATE_TEXT, align=PP_ALIGN.CENTER, sp=Pt(3))
snum(sl, 5)

# ══════════════════════════════════════════════════════════════════════════════
# 6 — Snapshot M+3
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Snapshot Fixe a M+3", "3 mois apres l'acquisition — le compromis entre signal et operationnalite", AMBER)

# Timeline
rect(sl, Inches(1.0), Inches(2.3), Inches(11.3), Inches(0.04), BORDER_GRAY)
points = [
    ("M+0", "Acquisition", Inches(1.0), CORAL),
    ("M+1", "", Inches(4.0), BORDER_GRAY),
    ("M+2", "", Inches(6.8), BORDER_GRAY),
    ("M+3", "Snapshot", Inches(9.5), CYAN),
]
for label, desc, x, c in points:
    dot = sl.shapes.add_shape(MSO_SHAPE.OVAL, x - Inches(0.12), Inches(2.18), Inches(0.28), Inches(0.28))
    dot.fill.solid()
    dot.fill.fore_color.rgb = c
    dot.line.fill.background()
    t = txb(sl, x - Inches(0.4), Inches(2.5), Inches(0.85), Inches(0.3))
    stxt(t, label, sz=13, bold=True, color=c, align=PP_ALIGN.CENTER)
    if desc:
        t2 = txb(sl, x - Inches(0.5), Inches(2.75), Inches(1.05), Inches(0.25))
        stxt(t2, desc, sz=11, color=SLATE_TEXT, align=PP_ALIGN.CENTER)

# Observation window
obs_rect = rrect(sl, Inches(1.0), Inches(1.7), Inches(8.7), Inches(0.45), CYAN_LIGHT, line=CYAN)
stxt(obs_rect, "3 mois d'observation — fenetre fixe pour tous les clients",
     sz=12, bold=True, color=CYAN, align=PP_ALIGN.CENTER)
obs_rect.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

# Why M+3
card(sl, Inches(0.5), Inches(3.4), Inches(3.8), Inches(3.5),
     "Pourquoi M+3 ?", [
         "A M+0 : aucune information comportementale",
         "A M+3 : premiers encours, equipements, signal NBI",
         "A M+6+ : prediction trop tardive pour le business",
         "Compromis optimal entre qualite du signal et utilite operationnelle",
     ], accent=AMBER)

card(sl, Inches(4.7), Inches(3.4), Inches(3.8), Inches(3.5),
     "Donnees disponibles a M+3", [
         "Encours par famille de produit",
         "Snapshot equipements trimestriel",
         "NBI total des 3 premiers mois",
         "Tendance et volatilite du NBI",
         "Nombre de produits detenus",
     ], accent=CYAN)

card(sl, Inches(8.9), Inches(3.4), Inches(3.8), Inches(3.5),
     "Avantages vs ancien design", [
         "Fenetre fixe : pas de variabilite n_mois_observation",
         "Tous les clients traites de maniere identique",
         "Pas de feature de controle (n_mois_nbi) necessaire",
         "Pipeline plus simple et plus interpretable",
     ], accent=LIME)
snum(sl, 6)

# ══════════════════════════════════════════════════════════════════════════════
# 7 — Donnees et pipeline
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Donnees et Pipeline", "Sources, format et flux de donnees", LIME)

# Data sources table
headers = ["Fichier", "Contenu", "Format", "Statut"]
rows = [
    ["Encours epargne", "Solde mensuel d'epargne", "client_id + indices mois", "A extraire"],
    ["Encours investissements", "AuM mensuel", "client_id + indices mois", "A extraire"],
    ["Encours credit immo", "Encours prets immo", "client_id + indices mois", "A extraire"],
    ["Encours autres credits", "Credits conso/revolving", "client_id + indices mois", "A extraire"],
    ["NBI autre", "Commissions, assurances", "client_id + indices mois", "A extraire"],
    ["Fichiers PNB", "NBI total mensuel", "client_id + indices mois", "Disponible"],
    ["Fichiers Stock", "Acquisitions (segment, etc.)", "CSV mensuel", "Disponible"],
    ["Fichiers Equipements", "Produits detenus", "CSV trimestriel", "Disponible"],
    ["Taux de marge", "t_s, t_i, t_m, t_c", "Fournis par Finance", "Recu"],
]

ts = sl.shapes.add_table(len(rows) + 1, 4, Inches(0.5), Inches(1.5), Inches(12.3), Inches(4.5))
tbl = ts.table
tbl.columns[0].width = Inches(3.0)
tbl.columns[1].width = Inches(3.5)
tbl.columns[2].width = Inches(3.3)
tbl.columns[3].width = Inches(2.5)
for j, h in enumerate(headers):
    c = tbl.cell(0, j)
    c.text = h
    for p in c.text_frame.paragraphs:
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER
    c.fill.solid()
    c.fill.fore_color.rgb = CHARCOAL
for i, row in enumerate(rows):
    for j, v in enumerate(row):
        c = tbl.cell(i + 1, j)
        c.text = v
        for p in c.text_frame.paragraphs:
            p.font.size = Pt(11)
            p.font.color.rgb = DARK_TEXT
            p.alignment = PP_ALIGN.CENTER if j > 1 else PP_ALIGN.LEFT
        c.fill.solid()
        if row[3] == "Recu":
            c.fill.fore_color.rgb = LIME_LIGHT
        elif row[3] == "Disponible":
            c.fill.fore_color.rgb = CYAN_LIGHT
        else:
            c.fill.fore_color.rgb = WHITE if i % 2 == 0 else WARM_GRAY

note2 = txb(sl, Inches(0.5), Inches(6.2), Inches(12), Inches(0.6))
tf = stxt(note2, "Encodage mois bancaires : Janvier 1994 = indice 1 | Formule : indice = (annee - 1994) × 12 + mois",
          sz=12, color=SLATE_TEXT)
apar(tf, "Validation cle : somme des 5 familles ≈ NBI total existant (fichiers PNB)",
     sz=12, bold=True, color=CHARCOAL, sp=Pt(3))
snum(sl, 7)

# ══════════════════════════════════════════════════════════════════════════════
# 8 — Features
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Features du Modele", "4 familles de variables d'entree — snapshot a M+3", CYAN)

feat_data = [
    ("Declaratif", VIOLET, [
        "Segment client",
        "Profession",
        "Age, genre",
        "Commune de residence",
        "Canal d'acquisition",
        "Trimestre d'acquisition",
    ]),
    ("Equipements\n(M+3)", CYAN, [
        "Nombre de produits total",
        "Detail par type de produit",
        "Compte courant, carte",
        "Livret, assurance vie",
        "Domiciliation salaire",
        "Credit en cours (oui/non)",
    ]),
    ("Comportemental\n(3 mois)", AMBER, [
        "NBI total des 3 premiers mois",
        "NBI moyen mensuel",
        "Tendance NBI (pente)",
        "Volatilite NBI",
        "Nombre de mois actifs",
        "Signal predictif (si H1 valide)",
    ]),
    ("Encours\n(M+3)", PINK, [
        "Encours epargne",
        "Encours investissements",
        "Encours credit immo",
        "Encours autres credits",
        "Valeurs au mois 3 exactement",
        "Base solide du modele (H2)",
    ]),
]

for i, (title, color, bullets) in enumerate(feat_data):
    x = Inches(0.3 + i * 3.2)
    hdr = rrect(sl, x, Inches(1.5), Inches(3.0), Inches(0.75), color)
    stxt(hdr, title, sz=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    hdr.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    body = rrect(sl, x, Inches(2.3), Inches(3.0), Inches(4.2), WHITE, line=color, line_w=1.5)
    body.text_frame.word_wrap = True
    body.text_frame.margin_left = Inches(0.15)
    body.text_frame.margin_top = Inches(0.1)
    tf = body.text_frame
    for j, b in enumerate(bullets):
        if j == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = f"  {b}"
        p.font.size = Pt(12)
        p.font.color.rgb = DARK_TEXT
        p.space_before = Pt(6)

note3 = txb(sl, Inches(0.5), Inches(6.7), Inches(12), Inches(0.4))
stxt(note3, "Tous les clients ont exactement 3 mois d'observation — pas de fenetre variable.",
     sz=12, bold=True, color=CHARCOAL)
snum(sl, 8)

# ══════════════════════════════════════════════════════════════════════════════
# 9 — Calibration par deciles
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Calibration par Deciles", "Lissage des predictions pour des resultats stables et interpretables", VIOLET)

# 3-step process
steps_data = [
    ("1", "Prediction brute", "Le XGBoost produit\nune prediction en EUR\n(encours ou NBI)\npour chaque client", VIOLET),
    ("2", "Affectation decile", "La prediction place le\nclient dans un decile\nD1 (bas) a D10 (haut)\nbase sur le training set", PINK),
    ("3", "Valeur finale", "Le client recoit la\nmoyenne observee reelle\nde son decile\n(pas la prediction brute)", CYAN),
]

for i, (num, title, desc, color) in enumerate(steps_data):
    x = Inches(0.5 + i * 4.2)
    circle = sl.shapes.add_shape(MSO_SHAPE.OVAL, x + Inches(1.3), Inches(1.55), Inches(0.65), Inches(0.65))
    circle.fill.solid()
    circle.fill.fore_color.rgb = color
    circle.line.fill.background()
    stxt(circle, num, sz=22, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    circle.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    t = txb(sl, x, Inches(2.35), Inches(3.5), Inches(0.35))
    stxt(t, title, sz=15, bold=True, color=color, align=PP_ALIGN.CENTER)

    body = rrect(sl, x, Inches(2.75), Inches(3.5), Inches(1.5), WHITE, line=color)
    body.text_frame.word_wrap = True
    body.text_frame.margin_left = Inches(0.12)
    body.text_frame.margin_top = Inches(0.1)
    stxt(body, desc, sz=12, color=DARK_TEXT, align=PP_ALIGN.CENTER)

# Arrow between steps
for i in range(2):
    x = Inches(4.1 + i * 4.2)
    arrow = txb(sl, x, Inches(1.65), Inches(0.5), Inches(0.5))
    stxt(arrow, "→", sz=28, bold=True, color=BORDER_GRAY, align=PP_ALIGN.CENTER)

card(sl, Inches(0.5), Inches(4.6), Inches(5.8), Inches(2.5),
     "Pourquoi les deciles ?", [
         "Elimine les outliers : un client predit a 500K recoit la moyenne du D10",
         "Predictions stables et interpretables pour le business",
         "Chaque sous-modele a sa propre table de deciles (5 tables)",
         "Approche validee par BCEF (modele precedent)",
     ], accent=VIOLET)

card(sl, Inches(6.8), Inches(4.6), Inches(5.8), Inches(2.5),
     "Calcul out-of-fold", [
         "Les bornes de deciles sont calculees sur des predictions out-of-fold",
         "Evite l'overfitting de la calibration sur le jeu d'entrainement",
         "Les moyennes par decile doivent etre monotones (D1 < D2 < ... < D10)",
         "Validation : stabilite des deciles entre les cohortes d'entrainement",
     ], accent=CYAN)
snum(sl, 9)

# ══════════════════════════════════════════════════════════════════════════════
# 10 — Formule CLV
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Formule CLV et Decomposition", "Projection actualisee sur 5 ans — decomposable par famille", PINK)

# Main formula
fb = rrect(sl, Inches(1.5), Inches(1.55), Inches(10.3), Inches(1.3), CHARCOAL)
tf = stxt(fb, "", sz=6)
tf.paragraphs[0].alignment = PP_ALIGN.CENTER
apar(tf, "CLV = Σ(t=1..5) [ NBI_total × g^(t-1) / (1+r)^t ]",
     sz=22, bold=True, color=WHITE, align=PP_ALIGN.CENTER, fn="Consolas")
apar(tf, "g = facteur de croissance annuel  |  r = taux d'actualisation  |  Pas de terme S(t)",
     sz=13, color=LIGHT_TEXT, align=PP_ALIGN.CENTER, sp=Pt(8))

# NBI composition
nbi_box = rrect(sl, Inches(0.5), Inches(3.15), Inches(12.3), Inches(0.65), WARM_GRAY, line=BORDER_GRAY)
stxt(nbi_box, "NBI_total = (encours_ep × t_s) + (encours_inv × t_i) + (encours_immo × t_m) + (encours_cr × t_c) + nbi_autre",
     sz=14, bold=True, color=CHARCOAL, align=PP_ALIGN.CENTER, fn="Consolas")
nbi_box.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

# Decomposition by family
t = txb(sl, Inches(0.5), Inches(4.1), Inches(12), Inches(0.35))
stxt(t, "Decomposition de la CLV par famille de produits", sz=15, bold=True, color=CHARCOAL)

decomp = [
    ("CLV_epargne", "NBI_ep × g_ep^(t-1) / (1+r)^t"),
    ("CLV_invest", "NBI_inv × g_inv^(t-1) / (1+r)^t"),
    ("CLV_immo", "NBI_immo × g_immo^(t-1) / (1+r)^t"),
    ("CLV_aut_cr", "NBI_cr × g_cr^(t-1) / (1+r)^t"),
    ("CLV_aut_pnb", "NBI_autre × g_pnb^(t-1) / (1+r)^t"),
]
for i, (name, formula) in enumerate(decomp):
    y = Inches(4.55) + Inches(i * 0.45)
    pill = rrect(sl, Inches(0.5), y, Inches(2.2), Inches(0.38), FAMILY_COLORS[i])
    stxt(pill, name, sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    pill.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    t = txb(sl, Inches(2.9), y + Inches(0.05), Inches(8), Inches(0.3))
    stxt(t, f"= Σ(t=1..5) [ {formula} ]", sz=12, color=DARK_TEXT, fn="Consolas")

note4 = txb(sl, Inches(0.5), Inches(7.0), Inches(12), Inches(0.3))
stxt(note4, "Permet d'identifier d'ou vient la valeur de chaque client et d'adapter les strategies commerciales par famille.",
     sz=12, color=SLATE_TEXT)
snum(sl, 10)

# ══════════════════════════════════════════════════════════════════════════════
# 11 — Churn implicite
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Churn Implicite", "Pas de modele de churn separe — l'attrition est capturee dans les donnees", AMBER)

# Main concept
main_box = rrect(sl, Inches(0.5), Inches(1.55), Inches(12.3), Inches(1.5), AMBER_LIGHT, line=AMBER, line_w=2)
main_box.text_frame.word_wrap = True
main_box.text_frame.margin_left = Inches(0.3)
main_box.text_frame.margin_top = Inches(0.15)
tf = stxt(main_box, "Principe : l'attrition est implicitement capturee dans les valeurs cumulees",
          sz=17, bold=True, color=CHARCOAL)
apar(tf, "", sz=4)
apar(tf, "Les donnees d'entrainement couvrent jusqu'a 5 ans post-acquisition. Un client qui part apres 2 ans aura des encours "
     "nuls pour les annees 3-5. Sa valeur cumulee sera donc naturellement plus basse, et les moyennes de deciles integreront "
     "ce taux d'attrition.",
     sz=13, color=DARK_TEXT, sp=Pt(6))

# Example timeline
t = txb(sl, Inches(0.5), Inches(3.4), Inches(12), Inches(0.35))
stxt(t, "Exemple : deux clients dans le meme decile", sz=15, bold=True, color=CHARCOAL)

# Client A - stays
rect(sl, Inches(0.5), Inches(4.0), Inches(2.4), Inches(0.4), CYAN)
stxt(rect(sl, Inches(0.5), Inches(4.0), Inches(2.4), Inches(0.4), CYAN),
     "An 1", sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
rect(sl, Inches(3.0), Inches(4.0), Inches(2.4), Inches(0.4), CYAN)
stxt(rect(sl, Inches(3.0), Inches(4.0), Inches(2.4), Inches(0.4), CYAN),
     "An 2", sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
rect(sl, Inches(5.5), Inches(4.0), Inches(2.4), Inches(0.4), CYAN)
stxt(rect(sl, Inches(5.5), Inches(4.0), Inches(2.4), Inches(0.4), CYAN),
     "An 3", sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
rect(sl, Inches(8.0), Inches(4.0), Inches(2.4), Inches(0.4), CYAN)
stxt(rect(sl, Inches(8.0), Inches(4.0), Inches(2.4), Inches(0.4), CYAN),
     "An 4", sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
rect(sl, Inches(10.5), Inches(4.0), Inches(2.2), Inches(0.4), CYAN)
stxt(rect(sl, Inches(10.5), Inches(4.0), Inches(2.2), Inches(0.4), CYAN),
     "An 5", sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
t = txb(sl, Inches(0.5), Inches(4.45), Inches(5), Inches(0.3))
stxt(t, "Client A — reste 5 ans → valeur cumulee elevee", sz=11, bold=True, color=CYAN)

# Client B - leaves
rect(sl, Inches(0.5), Inches(5.0), Inches(2.4), Inches(0.4), CORAL)
stxt(rect(sl, Inches(0.5), Inches(5.0), Inches(2.4), Inches(0.4), CORAL),
     "An 1", sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
rect(sl, Inches(3.0), Inches(5.0), Inches(2.4), Inches(0.4), CORAL)
stxt(rect(sl, Inches(3.0), Inches(5.0), Inches(2.4), Inches(0.4), CORAL),
     "An 2", sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
for yr, x in [("An 3", Inches(5.5)), ("An 4", Inches(8.0)), ("An 5", Inches(10.5))]:
    w = Inches(2.2) if yr == "An 5" else Inches(2.4)
    r = rrect(sl, x, Inches(5.0), w, Inches(0.4), WHITE, line=BORDER_GRAY)
    stxt(r, f"{yr} (0 EUR)", sz=11, color=LIGHT_TEXT, align=PP_ALIGN.CENTER)
    r.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
t = txb(sl, Inches(0.5), Inches(5.45), Inches(5), Inches(0.3))
stxt(t, "Client B — part apres 2 ans → valeur cumulee basse", sz=11, bold=True, color=CORAL)

card(sl, Inches(0.5), Inches(6.0), Inches(12.3), Inches(1.1),
     "La tenure comme proxy", [
         "La duree de presence est fortement correlee avec la valeur cumulee → les deciles capturent naturellement l'attrition",
         "Pas besoin de probabilite de survie S(t) dans la formule CLV — l'effet est deja dans les moyennes de deciles",
     ], accent=AMBER)
snum(sl, 11)

# ══════════════════════════════════════════════════════════════════════════════
# 12 — Exemple CLV
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Exemple CLV Chiffre", "Decomposition par famille de produit", LIME)

t = txb(sl, Inches(0.5), Inches(1.5), Inches(12), Inches(0.35))
stxt(t, "Client Mass Affluent — Snapshot a M+3 — Affecte au decile D7 dans chaque famille",
     sz=14, bold=True, color=CHARCOAL)

# Decile values table
headers = ["Famille", "Encours/NBI decile", "Marge", "NBI annuel"]
rows_data = [
    ("Epargne", "45 000 EUR", "x 1.2%", "540 EUR", CYAN),
    ("Investissements", "28 000 EUR", "x 0.8%", "224 EUR", VIOLET),
    ("Credit immobilier", "180 000 EUR", "x 0.5%", "900 EUR", PINK),
    ("Autres credits", "5 000 EUR", "x 3.0%", "150 EUR", AMBER),
    ("Autre PNB", "— (NBI direct)", "—", "380 EUR", LIME),
]

ts2 = sl.shapes.add_table(6, 4, Inches(0.5), Inches(2.0), Inches(7.5), Inches(2.8))
tbl2 = ts2.table
tbl2.columns[0].width = Inches(2.2)
tbl2.columns[1].width = Inches(2.3)
tbl2.columns[2].width = Inches(1.5)
tbl2.columns[3].width = Inches(1.5)
for j, h in enumerate(headers):
    c = tbl2.cell(0, j)
    c.text = h
    for p in c.text_frame.paragraphs:
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER
    c.fill.solid()
    c.fill.fore_color.rgb = CHARCOAL
for i, (fam, enc, marg, nbi, fc) in enumerate(rows_data):
    for j, v in enumerate([fam, enc, marg, nbi]):
        c = tbl2.cell(i + 1, j)
        c.text = v
        for p in c.text_frame.paragraphs:
            p.font.size = Pt(11)
            p.font.color.rgb = DARK_TEXT
            p.font.bold = (j == 3)
            p.alignment = PP_ALIGN.CENTER
        c.fill.solid()
        c.fill.fore_color.rgb = FAMILY_LIGHTS[i]

# Total NBI
total_box = rrect(sl, Inches(8.5), Inches(2.0), Inches(4.3), Inches(1.2), CHARCOAL)
tf = stxt(total_box, "NBI annuel total", sz=13, color=LIGHT_TEXT, align=PP_ALIGN.CENTER)
apar(tf, "2 194 EUR", sz=30, bold=True, color=WHITE, align=PP_ALIGN.CENTER, sp=Pt(6))

# CLV projection
clv_box = rrect(sl, Inches(8.5), Inches(3.5), Inches(4.3), Inches(1.3), VIOLET_LIGHT, line=VIOLET)
tf = stxt(clv_box, "CLV 5 ans (r=5%, g=3%)", sz=13, color=VIOLET, align=PP_ALIGN.CENTER)
apar(tf, "≈ 10 200 EUR", sz=28, bold=True, color=VIOLET, align=PP_ALIGN.CENTER, sp=Pt(6))
apar(tf, "Valeur actualisee", sz=11, color=SLATE_TEXT, align=PP_ALIGN.CENTER, sp=Pt(4))

# Pie-chart-like decomposition
t = txb(sl, Inches(0.5), Inches(5.2), Inches(12), Inches(0.35))
stxt(t, "Decomposition de la CLV par source de valeur", sz=14, bold=True, color=CHARCOAL)

decomp_data = [
    ("Epargne", "25%", "2 550 EUR"),
    ("Invest.", "10%", "1 020 EUR"),
    ("Cr. Immo", "41%", "4 180 EUR"),
    ("Aut. Cr.", "7%", "714 EUR"),
    ("Aut. PNB", "17%", "1 734 EUR"),
]
for i, (name, pct, val) in enumerate(decomp_data):
    x = Inches(0.5 + i * 2.5)
    bar = rrect(sl, x, Inches(5.7), Inches(2.2), Inches(1.3), FAMILY_LIGHTS[i], line=FAMILY_COLORS[i])
    tf = stxt(bar, name, sz=13, bold=True, color=FAMILY_COLORS[i], align=PP_ALIGN.CENTER)
    apar(tf, pct, sz=22, bold=True, color=FAMILY_COLORS[i], align=PP_ALIGN.CENTER, sp=Pt(4))
    apar(tf, val, sz=11, color=SLATE_TEXT, align=PP_ALIGN.CENTER, sp=Pt(2))
snum(sl, 12)

# ══════════════════════════════════════════════════════════════════════════════
# 13 — Validation
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Validation et Metriques", "Walk-forward temporelle — zero fuite de donnees futures", CYAN)

card(sl, Inches(0.5), Inches(1.55), Inches(5.8), Inches(2.5),
     "Validation walk-forward", [
         "Entrainer sur les cohortes anciennes, valider sur les recentes",
         "Fenetre d'entrainement croissante a chaque iteration",
         "Simule le deploiement reel : jamais de donnees futures dans le train",
         "Pas de k-fold classique (risque de fuite temporelle)",
     ], accent=CYAN)

card(sl, Inches(6.8), Inches(1.55), Inches(5.8), Inches(2.5),
     "Algorithme : XGBoost", [
         "Gestion native des valeurs manquantes (NaN)",
         "Aligne avec l'approche BCEF (modele precedent)",
         "Performant sur les donnees tabulaires",
         "5 modeles independants — un par famille de produit",
     ], accent=VIOLET)

# Metrics table
headers = ["Metrique", "Scope", "Description"]
metrics = [
    ["MAE", "Par sous-modele", "Erreur absolue moyenne (EUR)"],
    ["R²", "Par sous-modele", "Coefficient de determination"],
    ["Spearman", "Par sous-modele", "Correlation de rang (classement)"],
    ["MAE agregat", "NBI total", "Somme des NBI par famille vs NBI total"],
    ["Monotonie", "Deciles", "D1 < D2 < ... < D10 pour chaque modele"],
    ["Coherence", "Global", "Somme 5 familles ≈ NBI total (fichiers PNB)"],
]
ts3 = sl.shapes.add_table(len(metrics) + 1, 3, Inches(0.5), Inches(4.4), Inches(12.3), Inches(2.8))
tbl3 = ts3.table
tbl3.columns[0].width = Inches(2.0)
tbl3.columns[1].width = Inches(2.5)
tbl3.columns[2].width = Inches(7.8)
for j, h in enumerate(headers):
    c = tbl3.cell(0, j)
    c.text = h
    for p in c.text_frame.paragraphs:
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER
    c.fill.solid()
    c.fill.fore_color.rgb = CHARCOAL
for i, row in enumerate(metrics):
    for j, v in enumerate(row):
        c = tbl3.cell(i + 1, j)
        c.text = v
        for p in c.text_frame.paragraphs:
            p.font.size = Pt(11)
            p.font.color.rgb = DARK_TEXT
            p.alignment = PP_ALIGN.LEFT if j == 2 else PP_ALIGN.CENTER
        c.fill.solid()
        c.fill.fore_color.rgb = WHITE if i % 2 == 0 else WARM_GRAY
snum(sl, 13)

# ══════════════════════════════════════════════════════════════════════════════
# 14 — Hypotheses et roadmap
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Hypotheses et Roadmap", "8 hypotheses a verifier avant la construction du modele", VIOLET)

hyp_data = [
    ("H1", "Le NBI a 3 mois est-il predictif du NBI long terme ?", CYAN),
    ("H2", "Les encours a M+3 sont-ils predictifs ?", VIOLET),
    ("H3", "Les 5 familles ont-elles des profils differents ?", PINK),
    ("H4", "Chaque famille a-t-elle assez de non-zeros ?", AMBER),
    ("H5", "L'equipement a M+3 est-il stable dans le temps ?", LIME),
    ("H6", "Les taux de croissance sont-ils stables ?", CYAN),
    ("H7", "Les clients multi-equipes restent-ils plus longtemps ?", VIOLET),
    ("H8", "Le modele est-il stable entre cohortes ?", PINK),
]
for i, (code, question, color) in enumerate(hyp_data):
    y = Inches(1.5) + Inches(i * 0.6)
    pill = rrect(sl, Inches(0.5), y, Inches(0.7), Inches(0.4), color)
    stxt(pill, code, sz=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    pill.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    t = txb(sl, Inches(1.4), y + Inches(0.05), Inches(6), Inches(0.35))
    stxt(t, question, sz=13, color=DARK_TEXT)

# Roadmap
phases = [
    ("Phase 0", "Nettoyage et\ndocumentation", LIME, "FAIT"),
    ("Phase 1", "Extraction et\nvalidation donnees", AMBER, "EN COURS"),
    ("Phase 2", "Analyse exploratoire\net hypotheses", CYAN, "A FAIRE"),
    ("Phase 3", "Construction\ndu modele", VIOLET, "A FAIRE"),
    ("Phase 4", "Assemblage\nCLV", PINK, "A FAIRE"),
]
t = txb(sl, Inches(8.2), Inches(1.5), Inches(5), Inches(0.35))
stxt(t, "Roadmap du projet", sz=15, bold=True, color=CHARCOAL)

for i, (phase, desc, color, status) in enumerate(phases):
    y = Inches(2.0) + Inches(i * 1.0)
    pill = rrect(sl, Inches(8.2), y, Inches(1.3), Inches(0.4), color)
    stxt(pill, phase, sz=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    pill.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    t = txb(sl, Inches(9.7), y, Inches(2.2), Inches(0.6))
    tf = stxt(t, desc, sz=11, color=DARK_TEXT)
    st = txb(sl, Inches(12.0), y + Inches(0.05), Inches(1.2), Inches(0.35))
    s_color = LIME if status == "FAIT" else (AMBER if status == "EN COURS" else SLATE_TEXT)
    stxt(st, status, sz=10, bold=True, color=s_color, align=PP_ALIGN.RIGHT)
snum(sl, 14)

# ══════════════════════════════════════════════════════════════════════════════
# 15 — Prochaines etapes
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl)
title_bar(sl, "Prochaines Etapes", accent_color=PINK)

steps_next = [
    ("1", "Finaliser l'extraction des donnees d'encours", "Extraire les encours mensuels par famille (epargne, investissements, credit immo, autres credits) et le NBI autre (commissions, assurances)", CYAN),
    ("2", "Valider la coherence des donnees", "Executer la checklist de validation : somme des 5 familles ≈ NBI total, qualite des donnees, zero-inflation par famille", VIOLET),
    ("3", "Verifier les 8 hypotheses (H1-H8)", "Confirmer le pouvoir predictif du snapshot M+3, la stabilite des familles, et la faisabilite de 5 sous-modeles", PINK),
    ("4", "Construire et entrainer les 5 sous-modeles", "XGBoost par famille, calibration par deciles out-of-fold, validation walk-forward temporelle", AMBER),
    ("5", "Assembler la CLV et deployer", "Combiner les 5 NBI, projeter sur 5 ans, decomposer par famille, scorer les nouvelles cohortes", LIME),
]

for i, (num, title, desc, color) in enumerate(steps_next):
    y = Inches(1.5) + Inches(i * 1.15)
    circle = sl.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.7), y + Inches(0.05), Inches(0.55), Inches(0.55))
    circle.fill.solid()
    circle.fill.fore_color.rgb = color
    circle.line.fill.background()
    stxt(circle, num, sz=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    circle.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    t = txb(sl, Inches(1.5), y, Inches(11), Inches(0.35))
    stxt(t, title, sz=16, bold=True, color=color)
    t2 = txb(sl, Inches(1.5), y + Inches(0.35), Inches(11), Inches(0.55))
    stxt(t2, desc, sz=12, color=SLATE_TEXT)

# Bottom bar with family colors
for i, c in enumerate(FAMILY_COLORS):
    rect(sl, Inches(i * 2.667), Inches(7.15), Inches(2.667), Inches(0.06), c)

snum(sl, 15)

# ── save ─────────────────────────────────────────────────────────────────────
out = "Acquisition_model/presentation/CLV_Acquisition_Model_Presentation.pptx"
prs.save(out)
print(f"Saved: {out} ({len(prs.slides)} slides)")
