"""Fairness & Ethics tab - the governance posture, with measured evidence.
nationality_region appears ONLY here, and only as an audit dimension."""
from __future__ import annotations

import gradio as gr
import pandas as pd

from .. import theme
from ..services import SERVICES

GOVERNANCE = [
    ("Nationality excluded from scoring",
     "nationality_region is never a model feature; the churn model cannot see it."),
    ("Audit-only use of region",
     "Region appears only on this tab, to check that outcomes do not skew by group."),
    ("Human approval required",
     "No outreach reaches a customer without an explicit reviewer decision."),
    ("No manipulative retention",
     "The prompt bans urgency and pressure; guardrails enforce it; offers are capped at 2% of CLV."),
    ("Dignified goodbye",
     "Confirmed leavers are structurally unreachable by retention offers - they get help leaving well."),
    ("Model confidence is visible",
     "Every prediction shows its confidence; low confidence routes to human triage."),
    ("Reviewer accountability",
     "Every decision records who (AI vs human), what, when and why in an append-only audit log."),
    ("Synthetic data",
     "All customers and messages are synthetic; no real customer data or paid APIs are used."),
]


def _rates_by_segment() -> tuple[pd.DataFrame, str]:
    stats = SERVICES.review_stats()
    if not len(stats):
        return pd.DataFrame(), ("<div class='gov'>No review decisions logged "
                                "yet - approve/reject cases in Triage and this "
                                "audit fills in.</div>")
    g = stats.groupby("segment")["human_verdict"]
    rows = []
    for seg, verdicts in g:
        n = len(verdicts)
        rows.append({
            "segment": seg, "reviews": n,
            "approval rate": f"{verdicts.str.startswith('Approved').mean():.0%}",
            "override rate": f"{(verdicts == 'Overridden').mean():.0%}",
            "rejection rate": f"{(verdicts == 'Rejected').mean():.0%}",
        })
    df = pd.DataFrame(rows)
    rej = stats.groupby("segment")["human_verdict"].apply(
        lambda v: (v == "Rejected").mean())
    counts = stats.groupby("segment").size()
    overall = (stats["human_verdict"] == "Rejected").mean()
    flagged = [s for s in rej.index
               if counts[s] >= 5 and rej[s] > max(0.15, overall * 1.5)]
    if flagged:
        note = (f"<div class='warn'><b>Disproportion warning:</b> segment(s) "
                f"{', '.join(flagged)} receive rejections well above the "
                f"overall rate ({overall:.0%}) - review for bias before the "
                "next cycle.</div>")
    else:
        note = ("<div class='ok'>No disproportionate negative-decision "
                "pattern detected across segments at current sample sizes.</div>")
    return df, note


def build() -> None:
    gr.HTML("".join(
        f"<div class='gov'><b>{t}.</b> {d}</div>" for t, d in GOVERNANCE))

    df = SERVICES.customer_scores()
    gr.Markdown("### Risk distribution by segment (model inputs include segment)")
    seg = df.groupby("segment").agg(
        customers=("customer_id", "count"),
        mean_risk=("behaviour_risk", lambda s: f"{s.mean():.0%}"),
        at_risk=("behaviour_risk", lambda s: int((s >= 0.55).sum()))).reset_index()
    gr.Dataframe(seg, interactive=False)

    gr.Markdown("### Risk distribution by nationality_region — **audit only**, "
                "never a model input")
    reg = df.groupby("nationality_region").agg(
        customers=("customer_id", "count"),
        mean_predicted_risk=("behaviour_risk", lambda s: f"{s.mean():.0%}"),
        actual_churn_rate=("churned", lambda s: f"{s.mean():.0%}")).reset_index()
    gr.Dataframe(reg, interactive=False)
    gr.HTML("<div class='gov'>Pass criterion: predicted risk should track the "
            "actual churn rate within each region. If a region's predicted "
            "risk ran ahead of its actual outcomes, the model would have found "
            "a nationality proxy despite the exclusion - that is what this "
            "table exists to catch. Full audit: models/churn_eval.json.</div>")

    gr.Markdown("### Review decisions by segment (live, from the audit log)")
    init_df, init_html = _rates_by_segment()
    tbl = gr.Dataframe(value=init_df, interactive=False)
    note = gr.HTML(init_html)
    refresh = gr.Button("Refresh review-rate audit")
    refresh.click(_rates_by_segment, None, [tbl, note])
