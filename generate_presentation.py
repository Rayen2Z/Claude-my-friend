#!/usr/bin/env python3
"""Generate the CLV Acquisition Model presentation."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# -- palette --
DARK_BLUE = RGBColor(0x1B, 0x3A, 0x5C)
MED_BLUE = RGBColor(0x2C, 0x6F, 0xAD)
LIGHT_BLUE = RGBColor(0x5B, 0xA0, 0xD0)
ACCENT_GREEN = RGBColor(0x27, 0xAE, 0x60)
ACCENT_ORANGE = RGBColor(0xE6, 0x7E, 0x22)
ACCENT_RED = RGBColor(0xC0, 0x39, 0x2B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF2, 0xF2, 0xF2)
MEDIUM_GRAY = RGBColor(0x7F, 0x8C, 0x8D)
TEXT_DARK = RGBColor(0x2C, 0x3E, 0x50)
VERY_LIGHT_BLUE = RGBColor(0xEB, 0xF5, 0xFB)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW = prs.slide_width
SH = prs.slide_height


# ── helpers ──────────────────────────────────────────────────────────────────

def add_bg(slide, color=WHITE):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, left, top, width, height, fill_color, line_color=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    return shape


def add_rounded_rect(slide, left, top, width, height, fill_color, line_color=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(1.5)
    else:
        shape.line.fill.background()
    return shape


def set_text(shape, text, size=14, bold=False, color=TEXT_DARK, align=PP_ALIGN.LEFT, font_name="Calibri"):
    tf = shape.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = font_name
    p.alignment = align
    return tf


def add_para(tf, text, size=14, bold=False, color=TEXT_DARK, space_before=Pt(4), align=PP_ALIGN.LEFT, font_name="Calibri"):
    p = tf.add_paragraph()
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = font_name
    p.space_before = space_before
    p.alignment = align
    return p


def add_textbox(slide, left, top, width, height):
    return slide.shapes.add_textbox(left, top, width, height)


def title_bar(slide, title_text, subtitle_text=None):
    """Dark blue top bar with title."""
    add_rect(slide, Inches(0), Inches(0), SW, Inches(1.25), DARK_BLUE)
    tb = add_textbox(slide, Inches(0.7), Inches(0.2), Inches(11), Inches(0.6))
    set_text(tb, title_text, size=28, bold=True, color=WHITE)
    if subtitle_text:
        tb2 = add_textbox(slide, Inches(0.7), Inches(0.72), Inches(11), Inches(0.45))
        set_text(tb2, subtitle_text, size=16, color=RGBColor(0xBB, 0xDB, 0xF0))
    # thin accent line
    add_rect(slide, Inches(0), Inches(1.25), SW, Inches(0.05), MED_BLUE)


def slide_number(slide, num, total):
    tb = add_textbox(slide, Inches(12.0), Inches(7.05), Inches(1.2), Inches(0.35))
    set_text(tb, f"{num} / {total}", size=10, color=MEDIUM_GRAY, align=PP_ALIGN.RIGHT)


def bullet_card(slide, left, top, width, height, title, bullets, title_color=DARK_BLUE, fill=WHITE, border=None):
    box = add_rounded_rect(slide, left, top, width, height, fill, line_color=border or LIGHT_BLUE)
    box.text_frame.word_wrap = True
    tf = box.text_frame
    tf.margin_left = Inches(0.2)
    tf.margin_right = Inches(0.15)
    tf.margin_top = Inches(0.15)
    set_text(box, title, size=16, bold=True, color=title_color)
    for b in bullets:
        add_para(tf, f"  {b}", size=13, color=TEXT_DARK, space_before=Pt(4))
    return box


TOTAL_SLIDES = 14

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — Title
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, DARK_BLUE)

# subtle gradient band
add_rect(sl, Inches(0), Inches(3.0), SW, Inches(1.6), MED_BLUE)
add_rect(sl, Inches(0), Inches(4.6), SW, Inches(0.06), ACCENT_GREEN)

tb = add_textbox(sl, Inches(1), Inches(1.2), Inches(11), Inches(1.0))
set_text(tb, "CLV Model — New Acquisitions", size=40, bold=True, color=WHITE)

tb2 = add_textbox(sl, Inches(1), Inches(3.2), Inches(11), Inches(1.2))
tf = set_text(tb2, "Predicting NBI for Newly Acquired Clients", size=26, color=WHITE)
add_para(tf, "Quarterly T / T+1 / T+3 Sliding-Window Architecture", size=20, color=RGBColor(0xBB, 0xDB, 0xF0), space_before=Pt(12))

tb3 = add_textbox(sl, Inches(1), Inches(5.4), Inches(11), Inches(0.8))
tf3 = set_text(tb3, "Data & Analytics Team", size=16, color=RGBColor(0x99, 0xBB, 0xDD))
add_para(tf3, "May 2026", size=14, color=RGBColor(0x99, 0xBB, 0xDD), space_before=Pt(6))

slide_number(sl, 1, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — Agenda
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Agenda")

items = [
    ("1", "Business Context & Objective"),
    ("2", "Two-Model Architecture: NBI + Churn = CLV"),
    ("3", "The T / T+1 / T+3 Sliding-Window Design"),
    ("4", "Cohorts & Training Pipeline"),
    ("5", "Data Families & Feature Groups"),
    ("6", "Target Variable Design"),
    ("7", "Model Training & Evaluation"),
    ("8", "CLV Calculation: Combining NBI & Churn"),
    ("9", "Operational Cycle & Transition"),
    ("10", "Key Risks & Mitigations"),
]

y_start = Inches(1.7)
for i, (num, label) in enumerate(items):
    row_y = y_start + Inches(i * 0.52)
    circle = sl.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1.5), row_y, Inches(0.42), Inches(0.42))
    circle.fill.solid()
    circle.fill.fore_color.rgb = MED_BLUE if i % 2 == 0 else DARK_BLUE
    circle.line.fill.background()
    set_text(circle, num, size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    circle.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    tb = add_textbox(sl, Inches(2.2), row_y + Inches(0.05), Inches(9), Inches(0.4))
    set_text(tb, label, size=18, color=TEXT_DARK)

slide_number(sl, 2, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — Business Context
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Business Context & Objective", "Why a dedicated model for new clients?")

bullet_card(sl, Inches(0.5), Inches(1.6), Inches(5.8), Inches(2.5),
            "The Problem", [
                "New clients have no history — the existing CLV model cannot score them",
                "Months 0-12 are critical: engagement patterns set long-term value",
                "Business needs early predictions to allocate advisors & campaigns",
            ], title_color=ACCENT_RED, border=ACCENT_RED)

bullet_card(sl, Inches(6.8), Inches(1.6), Inches(5.8), Inches(2.5),
            "The Solution", [
                "A dedicated NBI regression model for newly acquired clients",
                "Predicts total NBI from acquisition to end of year (10-12 months)",
                "Uses early behavioral signals (4-6 months) + product snapshot",
            ], title_color=ACCENT_GREEN, border=ACCENT_GREEN)

bullet_card(sl, Inches(0.5), Inches(4.5), Inches(12.1), Inches(2.3),
            "Available Data — Jan 2023 to Mar 2026", [
                "Client files: client_id, creation date, segment (Mass Affluent / Mass Retail / MR with Potential), profession, nationality",
                "Monthly NBI: per-client, per-month NBI from internal PnL systems",
                "Equipment snapshots: quarterly CSV with product quantities held (accounts, cards, savings, insurance, credit, ...)",
            ], title_color=DARK_BLUE)

slide_number(sl, 3, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — Two-Model Architecture
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Two-Model Architecture", "NBI prediction + Churn prediction = CLV")

# NBI model box
nbi_box = add_rounded_rect(sl, Inches(0.8), Inches(1.8), Inches(3.6), Inches(3.0), VERY_LIGHT_BLUE, line_color=MED_BLUE)
tf = set_text(nbi_box, "MODEL 1 — NBI Regression", size=16, bold=True, color=DARK_BLUE, align=PP_ALIGN.CENTER)
add_para(tf, "", size=6)
add_para(tf, "Input: client features at T+1", size=13, color=TEXT_DARK, align=PP_ALIGN.CENTER)
add_para(tf, "(segment, products, early NBI, ...)", size=11, color=MEDIUM_GRAY, align=PP_ALIGN.CENTER)
add_para(tf, "", size=8)
add_para(tf, "Output:", size=13, bold=True, color=DARK_BLUE, align=PP_ALIGN.CENTER)
add_para(tf, "Predicted NBI (10-12 months)", size=14, bold=True, color=ACCENT_GREEN, align=PP_ALIGN.CENTER)
add_para(tf, "", size=8)
add_para(tf, "Status: IN DEVELOPMENT", size=12, bold=True, color=MED_BLUE, align=PP_ALIGN.CENTER)

# Churn model box
churn_box = add_rounded_rect(sl, Inches(5.0), Inches(1.8), Inches(3.6), Inches(3.0), RGBColor(0xFD, 0xED, 0xEC), line_color=ACCENT_RED)
tf2 = set_text(churn_box, "MODEL 2 — Churn Classification", size=16, bold=True, color=ACCENT_RED, align=PP_ALIGN.CENTER)
add_para(tf2, "", size=6)
add_para(tf2, "Input: same client features", size=13, color=TEXT_DARK, align=PP_ALIGN.CENTER)
add_para(tf2, "+ engagement signals", size=11, color=MEDIUM_GRAY, align=PP_ALIGN.CENTER)
add_para(tf2, "", size=8)
add_para(tf2, "Output:", size=13, bold=True, color=DARK_BLUE, align=PP_ALIGN.CENTER)
add_para(tf2, "P(churn) → Survival S(t)", size=14, bold=True, color=ACCENT_RED, align=PP_ALIGN.CENTER)
add_para(tf2, "", size=8)
add_para(tf2, "Status: PHASE 2", size=12, bold=True, color=MEDIUM_GRAY, align=PP_ALIGN.CENTER)

# Arrow to CLV
arrow = sl.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(5.15), Inches(5.0), Inches(3.3), Inches(0.7))
arrow.fill.solid()
arrow.fill.fore_color.rgb = DARK_BLUE
arrow.line.fill.background()
arrow.rotation = 0.0
tf_a = set_text(arrow, "COMBINE", size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# CLV box
clv_box = add_rounded_rect(sl, Inches(3.5), Inches(5.85), Inches(6.6), Inches(1.2), DARK_BLUE)
tf3 = set_text(clv_box, "CLV = Σ  [ NBI_predicted × growth^t × S(t) / (1+r)^t ]", size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
add_para(tf3, "3-year discounted lifetime value for new client", size=13, color=RGBColor(0xBB, 0xDB, 0xF0), align=PP_ALIGN.CENTER)

# Transition note
tb = add_textbox(sl, Inches(9.2), Inches(2.0), Inches(3.8), Inches(2.6))
tf4 = set_text(tb, "Lifecycle Transition", size=15, bold=True, color=DARK_BLUE)
add_para(tf4, "", size=6)
add_para(tf4, "Months 0 – 12", size=13, bold=True, color=MED_BLUE)
add_para(tf4, "This model (new acquisitions)", size=12, color=TEXT_DARK)
add_para(tf4, "", size=6)
add_para(tf4, "Month 12+", size=13, bold=True, color=MED_BLUE)
add_para(tf4, "Transition to established CLV model (existing 3-year model)", size=12, color=TEXT_DARK)

slide_number(sl, 4, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — T/T+1/T+3 Windows — Concept
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Sliding-Window Design: T / T+1 / T+3", "Quarterly cadence aligned with business operations")

# Three definition boxes across the top
for i, (label, desc, col, hl) in enumerate([
    ("T", "Acquisition Quarter", VERY_LIGHT_BLUE, MED_BLUE),
    ("T+1", "Observation Window End\n(Snapshot & Features)", RGBColor(0xE8, 0xF8, 0xE8), ACCENT_GREEN),
    ("T+3", "Target Window End\n(NBI Total)", RGBColor(0xFD, 0xED, 0xEC), ACCENT_RED),
]):
    x = Inches(0.6 + i * 4.2)
    box = add_rounded_rect(sl, x, Inches(1.65), Inches(3.7), Inches(1.3), col, line_color=hl)
    tf = set_text(box, label, size=24, bold=True, color=hl, align=PP_ALIGN.CENTER)
    add_para(tf, desc, size=13, color=TEXT_DARK, align=PP_ALIGN.CENTER, space_before=Pt(6))

# Timeline diagram
y_base = Inches(3.35)
# Header
tb = add_textbox(sl, Inches(0.5), y_base, Inches(12), Inches(0.4))
set_text(tb, "Example: Cohort Q1 2024", size=16, bold=True, color=DARK_BLUE)

# Quarter bars
quarters = [("Q1 2024\n(T)", MED_BLUE), ("Q2 2024\n(T+1)", ACCENT_GREEN),
            ("Q3 2024\n(T+2)", MEDIUM_GRAY), ("Q4 2024\n(T+3)", ACCENT_RED)]
bar_w = Inches(2.8)
bar_h = Inches(0.65)
bar_y = y_base + Inches(0.5)
for i, (qlabel, qcol) in enumerate(quarters):
    x = Inches(0.6 + i * 3.0)
    r = add_rounded_rect(sl, x, bar_y, bar_w, bar_h, qcol)
    set_text(r, qlabel, size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    r.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

# Client A (January) — full width
client_y = bar_y + Inches(1.0)
tb = add_textbox(sl, Inches(0.6), client_y, Inches(3.5), Inches(0.3))
set_text(tb, "Client A (joined January)", size=13, bold=True, color=DARK_BLUE)

obs_a = add_rounded_rect(sl, Inches(0.6), client_y + Inches(0.35), Inches(5.8), Inches(0.4),
                          RGBColor(0xD4, 0xE6, 0xF1), line_color=MED_BLUE)
set_text(obs_a, "6 months observation", size=11, color=MED_BLUE, align=PP_ALIGN.CENTER)

target_a = add_rounded_rect(sl, Inches(0.6), client_y + Inches(0.8), Inches(11.8), Inches(0.4),
                             RGBColor(0xFA, 0xDB, 0xD8), line_color=ACCENT_RED)
set_text(target_a, "12 months NBI target (n_mois_nbi = 12)", size=11, color=ACCENT_RED, align=PP_ALIGN.CENTER)

# Client B (March) — shorter
client_y2 = client_y + Inches(1.5)
tb = add_textbox(sl, Inches(0.6), client_y2, Inches(3.5), Inches(0.3))
set_text(tb, "Client B (joined March)", size=13, bold=True, color=DARK_BLUE)

obs_b = add_rounded_rect(sl, Inches(2.4), client_y2 + Inches(0.35), Inches(4.0), Inches(0.4),
                          RGBColor(0xD4, 0xE6, 0xF1), line_color=MED_BLUE)
set_text(obs_b, "4 months obs.", size=11, color=MED_BLUE, align=PP_ALIGN.CENTER)

target_b = add_rounded_rect(sl, Inches(2.4), client_y2 + Inches(0.8), Inches(9.98), Inches(0.4),
                             RGBColor(0xFA, 0xDB, 0xD8), line_color=ACCENT_RED)
set_text(target_b, "10 months NBI target (n_mois_nbi = 10)", size=11, color=ACCENT_RED, align=PP_ALIGN.CENTER)

slide_number(sl, 5, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — Window Variability
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Window Variability & Key Features", "Position in the acquisition quarter determines window lengths")

# Table
headers = ["Month in T", "n_mois_observation", "n_mois_nbi", "Example (Q1)"]
rows = [
    ["1st month", "6 months", "12 months", "January → Jun (obs) / Dec (target)"],
    ["2nd month", "5 months", "11 months", "February → Jun (obs) / Dec (target)"],
    ["3rd month", "4 months", "10 months", "March → Jun (obs) / Dec (target)"],
]

table_top = Inches(1.65)
col_widths = [Inches(2.2), Inches(2.8), Inches(2.5), Inches(5.0)]
table_shape = sl.shapes.add_table(len(rows) + 1, len(headers),
                                   Inches(0.5), table_top,
                                   sum(w for w in col_widths), Inches(1.8))
table = table_shape.table

for i, w in enumerate(col_widths):
    table.columns[i].width = w

for j, h in enumerate(headers):
    cell = table.cell(0, j)
    cell.text = h
    for p in cell.text_frame.paragraphs:
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER
    cell.fill.solid()
    cell.fill.fore_color.rgb = DARK_BLUE

for i, row in enumerate(rows):
    for j, val in enumerate(row):
        cell = table.cell(i + 1, j)
        cell.text = val
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(12)
            p.font.color.rgb = TEXT_DARK
            p.alignment = PP_ALIGN.CENTER
        cell.fill.solid()
        cell.fill.fore_color.rgb = WHITE if i % 2 == 0 else LIGHT_GRAY

# Key insight boxes
bullet_card(sl, Inches(0.5), Inches(3.8), Inches(5.8), Inches(3.2),
            "Why This Design Works", [
                "Quarterly cadence matches business operations",
                "Equipment snapshot at T+1 = state at prediction time",
                "Minimum 3 full months guaranteed even for late joiners",
                "10+ quarterly cohorts for training (vs 2-3 annual)",
                "Transparent, auditable windowing logic",
            ], title_color=ACCENT_GREEN, border=ACCENT_GREEN)

bullet_card(sl, Inches(6.8), Inches(3.8), Inches(5.8), Inches(3.2),
            "Key Mitigation Features", [
                "n_mois_nbi (10/11/12) lets the model relativize duration",
                "n_mois_observation (4/5/6) captures feature maturity",
                "pnb_mensuel_moyen normalizes for fair comparisons",
                "pnb_remaining isolates signal beyond mechanical floor",
                "Hypotheses HA11-HA13 validate these design choices",
            ], title_color=MED_BLUE, border=MED_BLUE)

slide_number(sl, 6, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 7 — Cohorts & Training Pipeline
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Cohorts & Training Pipeline", "Walk-forward temporal validation — no future leakage")

# Cohort grid
cohort_data = [
    ("Q1 2023", "Q2 2023", "Q4 2023", "TRAIN"),
    ("Q2 2023", "Q3 2023", "Q1 2024", "TRAIN"),
    ("Q3 2023", "Q4 2023", "Q2 2024", "TRAIN"),
    ("Q4 2023", "Q1 2024", "Q3 2024", "TRAIN"),
    ("Q1 2024", "Q2 2024", "Q4 2024", "TRAIN"),
    ("Q2 2024", "Q3 2024", "Q1 2025", "TRAIN"),
    ("Q3 2024", "Q4 2024", "Q2 2025", "TRAIN"),
    ("Q4 2024", "Q1 2025", "Q3 2025", "TRAIN"),
    ("Q1 2025", "Q2 2025", "Q4 2025", "TEST"),
    ("Q2 2025", "Q3 2025", "Q1 2026", "TEST"),
    ("Q4 2025", "Q1 2026", "Q3 2026", "SCORE"),
]

tbl_shape = sl.shapes.add_table(len(cohort_data) + 1, 4,
                                 Inches(0.5), Inches(1.6),
                                 Inches(8.5), Inches(5.2))
tbl = tbl_shape.table
tbl.columns[0].width = Inches(2.0)
tbl.columns[1].width = Inches(2.2)
tbl.columns[2].width = Inches(2.0)
tbl.columns[3].width = Inches(2.3)

for j, h in enumerate(["Cohort (T)", "Observation (T+1)", "Target End (T+3)", "Usage"]):
    cell = tbl.cell(0, j)
    cell.text = h
    for p in cell.text_frame.paragraphs:
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER
    cell.fill.solid()
    cell.fill.fore_color.rgb = DARK_BLUE

for i, (c, o, t, u) in enumerate(cohort_data):
    for j, val in enumerate([c, o, t, u]):
        cell = tbl.cell(i + 1, j)
        cell.text = val
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(11)
            p.alignment = PP_ALIGN.CENTER
            if u == "TRAIN":
                p.font.color.rgb = TEXT_DARK
            elif u == "TEST":
                p.font.color.rgb = ACCENT_ORANGE
                p.font.bold = True if j == 3 else False
            else:
                p.font.color.rgb = ACCENT_GREEN
                p.font.bold = True if j == 3 else False
        if u == "TRAIN":
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if i % 2 == 0 else LIGHT_GRAY
        elif u == "TEST":
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(0xFE, 0xF5, 0xE7)
        else:
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(0xE8, 0xF8, 0xE8)

# Side annotation
bullet_card(sl, Inches(9.4), Inches(1.6), Inches(3.6), Inches(5.2),
            "Pipeline Logic", [
                "8 cohorts for training",
                "2 cohorts for testing (temporal holdout)",
                "Score = latest cohort with T+1 snapshot available",
                "",
                "Walk-forward validation: 7 iterations, never train on future data",
                "",
                "Re-trained every quarter with expanding window",
            ], title_color=DARK_BLUE, border=DARK_BLUE)

slide_number(sl, 7, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — Data Families
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Data Families & Feature Groups", "Four pillars of predictive signal")

families = [
    ("Declarative\nFeatures", DARK_BLUE, [
        "Segment (Mass Affluent, Mass Retail, MR w/ Potential)",
        "Profession (Cadre, Salarie, Jeune Actif, ...)",
        "Trimestre & annee d'acquisition",
        "n_mois_observation, n_mois_nbi",
        "Nationality, age, canal (if available)",
    ]),
    ("Behavioral\n(Early NBI)", MED_BLUE, [
        "pnb_m1 ... pnb_m6 (monthly NBI)",
        "pnb_cumul_obs (cumulated observed NBI)",
        "pnb_cumul_3m (first 3 months)",
        "obs_slope (NBI trend)",
        "obs_volatility, obs_active_months",
    ]),
    ("Equipment\n(T+1 Snapshot)", ACCENT_GREEN, [
        "qty_* (quantity per product held)",
        "n_produits_total (product count)",
        "Accounts, cards, savings, insurance, credit, ...",
        "Flow columns (inflow, outflow, liquid cash)",
        "Salary domiciliation (key signal)",
    ]),
    ("Interaction\nFeatures", ACCENT_ORANGE, [
        "segment × n_produits",
        "pnb_cumul_obs / n_produits",
        "obs_slope × n_produits",
        "Derived at training time",
        "Capture cross-effects",
    ]),
]

for i, (title, color, bullets) in enumerate(families):
    x = Inches(0.4 + i * 3.2)
    # Header
    hdr = add_rounded_rect(sl, x, Inches(1.7), Inches(2.95), Inches(0.85), color)
    set_text(hdr, title, size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    hdr.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    # Bullet list
    body = add_rounded_rect(sl, x, Inches(2.6), Inches(2.95), Inches(4.3), WHITE, line_color=color)
    body.text_frame.word_wrap = True
    body.text_frame.margin_left = Inches(0.15)
    body.text_frame.margin_top = Inches(0.1)
    tf = body.text_frame
    for j, b in enumerate(bullets):
        if j == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = f"• {b}"
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_DARK
        p.space_before = Pt(5)

slide_number(sl, 8, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 9 — Target Variable
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Target Variable Design", "What we predict and why")

# Main target
main = add_rounded_rect(sl, Inches(0.5), Inches(1.7), Inches(7.5), Inches(1.6), VERY_LIGHT_BLUE, line_color=DARK_BLUE)
tf = set_text(main, "Primary Target: pnb_total", size=20, bold=True, color=DARK_BLUE)
add_para(tf, "", size=4)
add_para(tf, "pnb_total = SUM( pnb_m1 ... pnb_m{n_mois_nbi} )", size=16, bold=True, color=MED_BLUE, font_name="Consolas")
add_para(tf, "Raw cumulated NBI from acquisition to end of T+3 (10-12 months)", size=13, color=TEXT_DARK, space_before=Pt(6))
add_para(tf, "n_mois_nbi provided as feature so the model learns to relativize", size=13, color=MEDIUM_GRAY)

# Alternative target
alt = add_rounded_rect(sl, Inches(8.5), Inches(1.7), Inches(4.5), Inches(1.6), RGBColor(0xFD, 0xED, 0xEC), line_color=ACCENT_ORANGE)
tf2 = set_text(alt, "Alternative: pnb_remaining", size=16, bold=True, color=ACCENT_ORANGE)
add_para(tf2, "", size=4)
add_para(tf2, "= pnb_total − pnb_cumul_obs", size=14, bold=True, color=ACCENT_RED, font_name="Consolas")
add_para(tf2, "Isolates the unseen portion", size=12, color=TEXT_DARK, space_before=Pt(6))
add_para(tf2, "Tested in hypothesis HA12", size=12, color=MEDIUM_GRAY)

# Why ~12 months
bullet_card(sl, Inches(0.5), Inches(3.7), Inches(5.8), Inches(3.2),
            "Why T+3 (≈12 months)?", [
                "Natural annual banking cycle (card fees, insurance premiums)",
                "Credits need 3-6 months to generate NBI — shorter horizon misses this",
                "Quarterly alignment enables operational deployment",
                "After 12 months, client transitions to established CLV model",
                "10-12 month range captures the first full year of relationship",
            ], title_color=DARK_BLUE, border=DARK_BLUE)

# Mechanical floor warning
bullet_card(sl, Inches(6.8), Inches(3.7), Inches(5.8), Inches(3.2),
            "⚠  Mechanical Correlation Floor", [
                "pnb_cumul_obs is a SUBSET of pnb_total",
                "Creates artificial correlation ≈ sqrt(n_obs / n_nbi)",
                "r(obs, total) inflated by ~0.15-0.25 vs true signal",
                "HA4b tests correlation on pnb_remaining to isolate real signal",
                "Not data leakage — but must be accounted for in evaluation",
            ], title_color=ACCENT_ORANGE, border=ACCENT_ORANGE)

slide_number(sl, 9, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 10 — Model Training
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Model Training & Evaluation")

# Model card
model_card = add_rounded_rect(sl, Inches(0.5), Inches(1.7), Inches(5.5), Inches(3.0), VERY_LIGHT_BLUE, line_color=MED_BLUE)
tf = set_text(model_card, "Model: Gradient Boosting Regressor", size=18, bold=True, color=DARK_BLUE)
add_para(tf, "", size=6)
add_para(tf, "n_estimators = 300", size=13, color=TEXT_DARK, font_name="Consolas")
add_para(tf, "max_depth = 4", size=13, color=TEXT_DARK, font_name="Consolas")
add_para(tf, "learning_rate = 0.05", size=13, color=TEXT_DARK, font_name="Consolas")
add_para(tf, "loss = 'huber'  (robust to NBI outliers)", size=13, color=TEXT_DARK, font_name="Consolas")
add_para(tf, "subsample = 0.8", size=13, color=TEXT_DARK, font_name="Consolas")
add_para(tf, "min_samples_leaf = 20", size=13, color=TEXT_DARK, font_name="Consolas")

# Metrics
metrics_card = add_rounded_rect(sl, Inches(6.5), Inches(1.7), Inches(6.3), Inches(3.0), WHITE, line_color=DARK_BLUE)
tf2 = set_text(metrics_card, "Evaluation Metrics", size=18, bold=True, color=DARK_BLUE)
add_para(tf2, "", size=6)
add_para(tf2, "MAE (Mean Absolute Error) — target: < 20% of mean NBI", size=13, color=TEXT_DARK)
add_para(tf2, "RMSE — penalizes large errors", size=13, color=TEXT_DARK, space_before=Pt(6))
add_para(tf2, "R² — target: > 0.30 (limited data)", size=13, color=TEXT_DARK, space_before=Pt(6))
add_para(tf2, "MAPE — target: < 30%", size=13, color=TEXT_DARK, space_before=Pt(6))
add_para(tf2, "", size=6)
add_para(tf2, "All measured on temporal holdout (not k-fold)", size=12, bold=True, color=MED_BLUE)

# Walk-forward
bullet_card(sl, Inches(0.5), Inches(5.1), Inches(12.3), Inches(1.9),
            "Walk-Forward Temporal Validation (7 iterations)", [
                "Iter 1: Train Q1-Q2 2023 → Test Q3 2023  |  Iter 2: Train Q1-Q3 2023 → Test Q4 2023  |  ...  |  Iter 7: Train Q1 2023 - Q2 2024 → Test Q3 2024",
                "Expanding training window, single-quarter test set — simulates real deployment, zero future leakage",
                "Huber loss handles negative-NBI clients and outliers without distorting the overall fit",
            ], title_color=DARK_BLUE, border=DARK_BLUE)

slide_number(sl, 10, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 11 — CLV Calculation
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "CLV Calculation", "Combining NBI prediction and churn into a single lifetime value")

# Formula box
formula_box = add_rounded_rect(sl, Inches(1.0), Inches(1.7), Inches(11.3), Inches(1.8), DARK_BLUE)
tf = set_text(formula_box, "", size=10)
tf.paragraphs[0].alignment = PP_ALIGN.CENTER
add_para(tf, "CLV  =  Σ(t=1..3)  [ NBI_predicted  ×  growth^(t-1)  ×  S(t)  /  (1 + r)^t ]", size=24, bold=True, color=WHITE, align=PP_ALIGN.CENTER, font_name="Consolas")
add_para(tf, "", size=8)
add_para(tf, "3-year discounted customer lifetime value for newly acquired clients", size=15, color=RGBColor(0xBB, 0xDB, 0xF0), align=PP_ALIGN.CENTER)

# Component breakdown - 4 cards
components = [
    ("NBI_predicted", "NBI Regression\nModel", MED_BLUE, [
        "Output of this model",
        "Predicted NBI for the first ≈12 months",
        "Used as the annual revenue baseline",
    ]),
    ("growth", "Growth Factor", ACCENT_GREEN, [
        "Annual NBI growth rate",
        "To be calibrated (~1.05-1.10)",
        "Accounts for maturation of the relationship",
    ]),
    ("S(t)", "Survival\nProbability", ACCENT_RED, [
        "From churn classification model (Phase 2)",
        "S(t) = P(client still active at year t)",
        "S(1) ≈ 0.85-0.95 typically",
    ]),
    ("(1+r)^t", "Discount\nFactor", ACCENT_ORANGE, [
        "Time value of money",
        "r = 5% (bank's cost of capital)",
        "Future revenue worth less than today",
    ]),
]

for i, (symbol, title, color, bullets) in enumerate(components):
    x = Inches(0.4 + i * 3.2)
    hdr = add_rounded_rect(sl, x, Inches(3.8), Inches(2.95), Inches(0.75), color)
    set_text(hdr, f"{symbol}", size=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    hdr.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    body = add_rounded_rect(sl, x, Inches(4.6), Inches(2.95), Inches(2.2), WHITE, line_color=color)
    body.text_frame.word_wrap = True
    body.text_frame.margin_left = Inches(0.12)
    body.text_frame.margin_top = Inches(0.08)
    tf = body.text_frame
    for j, b in enumerate(bullets):
        if j == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = f"• {b}"
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_DARK
        p.space_before = Pt(4)

slide_number(sl, 11, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 12 — CLV Example
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "CLV Calculation — Worked Example")

# Example values
tb = add_textbox(sl, Inches(0.5), Inches(1.7), Inches(12), Inches(0.4))
set_text(tb, "Mass Affluent client, joined Q1 2024, predicted NBI = 3,500 EUR / year", size=16, bold=True, color=DARK_BLUE)

# Table
tbl_shape = sl.shapes.add_table(5, 6, Inches(0.5), Inches(2.3), Inches(12), Inches(2.5))
tbl = tbl_shape.table
col_ws = [Inches(1.5), Inches(2.2), Inches(2.0), Inches(2.0), Inches(2.3), Inches(2.0)]
for i, w in enumerate(col_ws):
    tbl.columns[i].width = w

headers = ["Year t", "NBI × growth^(t-1)", "S(t)", "Discount (1.05)^t", "Annual CLV", "Cumulated"]
values = [
    ["1", "3,500 × 1.00 = 3,500", "0.92", "1.050", "3,067", "3,067"],
    ["2", "3,500 × 1.08 = 3,780", "0.85", "1.103", "2,916", "5,983"],
    ["3", "3,500 × 1.17 = 4,082", "0.78", "1.158", "2,748", "8,731"],
    ["Total", "", "", "", "", "8,731 EUR"],
]

for j, h in enumerate(headers):
    cell = tbl.cell(0, j)
    cell.text = h
    for p in cell.text_frame.paragraphs:
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER
    cell.fill.solid()
    cell.fill.fore_color.rgb = DARK_BLUE

for i, row in enumerate(values):
    for j, val in enumerate(row):
        cell = tbl.cell(i + 1, j)
        cell.text = val
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(12)
            p.alignment = PP_ALIGN.CENTER
            if i == 3:
                p.font.bold = True
                p.font.color.rgb = DARK_BLUE
            else:
                p.font.color.rgb = TEXT_DARK
        cell.fill.solid()
        if i == 3:
            cell.fill.fore_color.rgb = RGBColor(0xD4, 0xE6, 0xF1)
        else:
            cell.fill.fore_color.rgb = WHITE if i % 2 == 0 else LIGHT_GRAY

# Key assumptions
bullet_card(sl, Inches(0.5), Inches(5.1), Inches(5.8), Inches(2.0),
            "Assumptions (to calibrate)", [
                "Growth rate: 8% per year (relationship maturation)",
                "Discount rate: 5% (cost of capital)",
                "Churn: ~8% / year (S declines over time)",
            ], title_color=MEDIUM_GRAY, border=MEDIUM_GRAY)

bullet_card(sl, Inches(6.8), Inches(5.1), Inches(5.8), Inches(2.0),
            "Interpretation", [
                "This client is worth 8,731 EUR over 3 years",
                "Enables: advisor allocation, campaign ROI, portfolio valuation",
                "After month 12 → transition to established CLV model",
            ], title_color=ACCENT_GREEN, border=ACCENT_GREEN)

slide_number(sl, 12, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 13 — Operational Cycle
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Operational Cycle & Transition", "Quarterly scoring rhythm")

# Timeline — 4 steps
steps = [
    ("1", "End of Quarter", "Collect new data:\n• NBI files updated\n• Equipment snapshot ready\n• New clients identified", MED_BLUE),
    ("2", "Retrain Model", "Expand training set:\n• Add latest completed cohort\n• Walk-forward validation\n• Compare to previous model", DARK_BLUE),
    ("3", "Score New Clients", "For the latest T cohort:\n• Apply model at T+1\n• Predict NBI to T+3\n• Compute CLV", ACCENT_GREEN),
    ("4", "Deliver & Monitor", "Output to business:\n• Client-level CLV scores\n• Segment-level aggregates\n• Performance monitoring", ACCENT_ORANGE),
]

for i, (num, title, desc, color) in enumerate(steps):
    x = Inches(0.4 + i * 3.2)
    circle = sl.shapes.add_shape(MSO_SHAPE.OVAL, x + Inches(1.1), Inches(1.7), Inches(0.7), Inches(0.7))
    circle.fill.solid()
    circle.fill.fore_color.rgb = color
    circle.line.fill.background()
    set_text(circle, num, size=22, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    circle.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER

    tb = add_textbox(sl, x, Inches(2.55), Inches(2.95), Inches(0.4))
    set_text(tb, title, size=15, bold=True, color=color, align=PP_ALIGN.CENTER)

    body = add_rounded_rect(sl, x, Inches(3.0), Inches(2.95), Inches(2.0), WHITE, line_color=color)
    body.text_frame.word_wrap = True
    body.text_frame.margin_left = Inches(0.12)
    body.text_frame.margin_top = Inches(0.1)
    set_text(body, desc, size=12, color=TEXT_DARK)

# Transition box
trans = add_rounded_rect(sl, Inches(0.5), Inches(5.4), Inches(12.3), Inches(1.6), DARK_BLUE)
tf = set_text(trans, "Client Lifecycle Transition", size=18, bold=True, color=WHITE)
add_para(tf, "", size=6)
add_para(tf, "Month 0 → 12:  THIS MODEL scores the client once at T+1, prediction valid until T+3", size=14, color=RGBColor(0xBB, 0xDB, 0xF0))
add_para(tf, "Month 12+:      Client has 4+ quarters of history → transitions to the established CLV model (3-year horizon)", size=14, color=RGBColor(0xBB, 0xDB, 0xF0), space_before=Pt(6))
add_para(tf, "No overlap or lissage needed — clean handoff between models", size=13, color=MEDIUM_GRAY, space_before=Pt(8))

slide_number(sl, 13, TOTAL_SLIDES)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 14 — Risks & Next Steps
# ═══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(sl, WHITE)
title_bar(sl, "Key Risks, Mitigations & Next Steps")

bullet_card(sl, Inches(0.5), Inches(1.7), Inches(5.8), Inches(2.8),
            "⚠  Risks & Limits", [
                "Variable window (10-12 mo) biases raw NBI comparisons",
                "Mechanical correlation floor inflates R² on pnb_total",
                "Cohort drift: 2023 clients may differ from 2025",
                "Seasonality confounded with window length",
                "Cross-border clients may need special treatment",
            ], title_color=ACCENT_RED, border=ACCENT_RED)

bullet_card(sl, Inches(6.8), Inches(1.7), Inches(5.8), Inches(2.8),
            "✓  Mitigations", [
                "n_mois_nbi as feature + HA11 validates normalization",
                "HA12 tests pnb_remaining as cleaner target",
                "Quarterly retraining limits drift impact",
                "HA7 uses pnb_mensuel_moyen for fair seasonal comparison",
                "Frontalier flag as feature if available",
            ], title_color=ACCENT_GREEN, border=ACCENT_GREEN)

bullet_card(sl, Inches(0.5), Inches(4.9), Inches(12.1), Inches(2.2),
            "Next Steps", [
                "1. Run & validate 13 hypotheses (HA1-HA13) on preprocessed data",
                "2. Exploratory Data Analysis (EDA) — distributions, correlations, outliers",
                "3. Train Gradient Boosting V0 with walk-forward validation",
                "4. Evaluate, iterate on feature engineering, test pnb_remaining target",
                "5. Phase 2: develop churn model → combine into full CLV pipeline",
            ], title_color=DARK_BLUE, border=DARK_BLUE)

slide_number(sl, 14, TOTAL_SLIDES)

# ── save ─────────────────────────────────────────────────────────────────────
out_path = "Acquisition_model/CLV_Acquisition_Model_Presentation.pptx"
prs.save(out_path)
print(f"Presentation saved to {out_path}")
print(f"Total slides: {len(prs.slides)}")
