"""Renders the architecture flow diagram (no owner names - ownership lives in
the Architecture Design Document's module table).
Run: python docs/make_flow_diagram.py  ->  docs/architecture_flow.png"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "architecture_flow.png"

C_INPUT = "#ECECEC"
C_LISTEN = "#E4E1F7"
C_UNDER = "#DDF2EA"
C_ACT = "#FBE9E0"
C_DASH = "#ECECEC"
EDGE = {"input": "#7A7A7A", "listen": "#5A50B5", "under": "#1D7A5F",
        "act": "#C05A2E", "dash": "#7A7A7A"}

fig, ax = plt.subplots(figsize=(11, 7.6), dpi=170)
ax.set_xlim(0, 100)
ax.set_ylim(-10, 100)
ax.axis("off")


def box(x, y, w, h, title, lines, fc, ec, title_size=10.5, line_size=8.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.4,rounding_size=1.2",
                                facecolor=fc, edgecolor=ec, linewidth=1.4))
    cy = y + h - 3.2
    ax.text(x + w / 2, cy, title, ha="center", va="center",
            fontsize=title_size, fontweight="bold", color="#222222")
    for ln in lines:
        cy -= 4.0
        ax.text(x + w / 2, cy, ln, ha="center", va="center",
                fontsize=line_size, color="#444444")


def arrow(x1, y1, x2, y2, label="", color="#555555", lx=0.0, ly=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=16, linewidth=1.5,
                                 color=color))
    if label:
        ax.text((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label, ha="center",
                va="center", fontsize=8.2, style="italic", color="#333333",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                          edgecolor="none", alpha=0.9))


# inputs
box(6, 86, 34, 10, "Customer message", ["raw text - en / ar / hi / tl"],
    C_INPUT, EDGE["input"])
box(60, 86, 34, 10, "Customer profile", ["customers.csv - behaviour + value"],
    C_INPUT, EDGE["input"])

# M1 + M2a
box(4, 56, 38, 24, "M1  LISTEN - NLP signal extraction",
    ["language ID (script + keyword rules)",
     "issue + churn-signal classifiers",
     "(trained LSTM / fine-tuned DistilmBERT)",
     "entities - leaving-confirmed check"],
    C_LISTEN, EDGE["listen"])
box(58, 60, 38, 18, "M2a  Churn propensity model",
    ["logistic regression (primary) vs XGBoost",
     "nationality_region EXCLUDED",
     "region used only for fairness audit"],
    C_UNDER, EDGE["under"])

arrow(23, 86, 23, 80.6, "text", EDGE["input"], lx=6)
arrow(77, 86, 77, 78.6, "profile row", EDGE["input"], lx=10)

# fusion
box(29, 36, 42, 14, "M2b  Risk fusion",
    ["fused = 0.55 x behaviour + 0.45 x text signal",
     "overrides: confirmed leaver / low confidence -> triage"],
    C_UNDER, EDGE["under"])

arrow(23, 55.4, 40, 50.6, "ListenSignals", EDGE["listen"], lx=-9, ly=0.5)
arrow(77, 59.4, 60, 50.6, "P(churn)", EDGE["under"], lx=9, ly=0.5)

# M3
box(6, 14, 40, 16, "M3a  Decision rules (transparent)",
    ["numbered rule table - every rule logged",
     "offer cap: 2% of CLV, else RM call",
     "confirmed leaver -> dignified goodbye"],
    C_ACT, EDGE["act"])
box(54, 14, 40, 16, "M3b  Outreach drafting",
    ["Qwen2.5-0.5B, tone-locked prompt; guardrails:",
     "urgency / invented amounts / placeholders /",
     "language mismatch -> template in customer's language"],
    C_ACT, EDGE["act"])

arrow(50, 35.4, 30, 30.6, "RiskAssessment", EDGE["under"], lx=-12, ly=0.6)
arrow(46, 22, 53.4, 22, "action + rationale", EDGE["act"], ly=3.2)

# dashboard
box(25, -8, 50, 14, "M4  Retention dashboard (Gradio)",
    ["understanding - risk + why - action - draft",
     "human approve / edit / reject -> audit log (JSONL)"],
    C_DASH, EDGE["dash"])

arrow(74, 13.4, 58, 6.6, "ActionPlan", EDGE["act"], lx=9, ly=0.5)

fig.savefig(OUT, bbox_inches="tight", facecolor="white")
print(f"saved {OUT}")
