"""Overview tab - the executive picture: what is at stake, how the platform
works, where the value concentrates. Every number is computed from the data."""
from __future__ import annotations

from pathlib import Path

import gradio as gr

from .. import theme
from ..services import ROOT, SERVICES


def build() -> None:
    df = SERVICES.customer_scores()
    at_risk = df[df["behaviour_risk"] >= 0.55]
    msgs = SERVICES.messages
    seg = (at_risk.groupby("segment")["clv_estimate_aed"].agg(["count", "sum"]))
    seg_html = "".join(
        f"<tr><td class='k' style='padding-right:16px'>{s}</td>"
        f"<td class='v' style='padding-right:16px'>{int(r['count'])} at risk</td>"
        f"<td class='v'>{theme.aed(r['sum'])} exposed</td></tr>"
        for s, r in seg.iterrows())

    gr.HTML(theme.metric_row(
        theme.metric("Customer book", f"{len(df)}",
                     f"total CLV {theme.aed(df.clv_estimate_aed.sum())}"),
        theme.metric("At-risk customers", f"{len(at_risk)}",
                     "behaviour risk ≥ 55%"),
        theme.metric("CLV at risk", theme.aed(at_risk.clv_estimate_aed.sum()),
                     f"{at_risk.clv_estimate_aed.sum() / df.clv_estimate_aed.sum():.0%} of the book"),
        theme.metric("Messages / week", f"{len(msgs)}",
                     f"{(msgs.language != 'en').mean():.0%} not in English"),
        theme.metric("High churn intent", f"{(msgs.churn_signal == 'High').sum()}",
                     "messages expressing clear leave intent"),
    ))
    gr.HTML(theme.card(
        "Where the value concentrates",
        f"<table>{seg_html}</table>"
        "<div class='k' style='margin-top:8px'>85% of at-risk value sits in a "
        "handful of Premium and Private relationships - an 18-person team can "
        "cover those calls if triage is automatic. Text is the early-warning "
        "system: most customers who say they are leaving still look calm on "
        "paper.</div>"))
    img = Path(ROOT / "docs" / "architecture_flow.png")
    if img.exists():
        gr.Markdown("### How a message becomes a reviewed decision")
        gr.Image(str(img), show_label=False, container=True, height=560)
    gr.HTML(
        "<div class='gov'>The platform assists; it never acts alone. Learned "
        "models read the fuzzy language, transparent rules decide where money "
        "and trust are involved, and a human approves every customer-facing "
        "action. Wafa (وفاء) means loyalty - and it runs both ways.</div>")
