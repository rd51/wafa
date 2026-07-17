"""Analytics tab - every chart answers a retention question the CX team
actually asks. All series computed from the real data + scored queue; the one
simulated series is labeled SIMULATED in its title."""
from __future__ import annotations

import gradio as gr
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .. import theme
from ..services import SERVICES

_LAYOUT = dict(template="plotly_dark", paper_bgcolor="#121B2E",
               plot_bgcolor="#121B2E", font=dict(color="#CBD5E1", size=12),
               margin=dict(l=40, r=20, t=48, b=40), height=330)
_BAND_ORDER = ["Low", "Medium", "High", "Critical"]


def _bar(x, y, title, color="#38BDF8", orientation="v"):
    fig = go.Figure(go.Bar(x=x, y=y, orientation=orientation,
                           marker_color=color))
    fig.update_layout(title=title, **_LAYOUT)
    return fig


def _charts():
    df = SERVICES.customer_scores()
    msgs = SERVICES.messages
    q = SERVICES.build_queue()

    seg = df.groupby("segment")["behaviour_risk"].mean().reindex(
        ["Mass", "Premium", "Private"])
    c1 = _bar(seg.index, (seg * 100).round(1),
              "Which segments carry churn risk? (mean behaviour risk %)")

    issue = msgs["issue_type"].value_counts()
    c2 = _bar(issue.index.str.replace("_", " "), issue.values,
              "What are customers writing about? (issue distribution)", "#60A5FA")

    sig = msgs["churn_signal"].value_counts().reindex(["Low", "Medium", "High"])
    c3 = go.Figure(go.Bar(x=sig.index, y=sig.values, marker_color=[
        theme.RISK_COLORS["Low"], theme.RISK_COLORS["Medium"],
        theme.RISK_COLORS["Critical"]]))
    c3.update_layout(title="How loud is the leave signal in the inbox?", **_LAYOUT)

    drivers = SERVICES.driver_counts()
    c4 = _bar(drivers.values, drivers.index,
              "Top churn drivers among at-risk customers", "#FB923C",
              orientation="h")

    clv = df.groupby("band")["clv_estimate_aed"].mean().reindex(_BAND_ORDER)
    c5 = go.Figure(go.Bar(x=clv.index, y=clv.values.round(0), marker_color=[
        theme.RISK_COLORS[b] for b in _BAND_ORDER]))
    c5.update_layout(title="Average CLV by risk band (is high-value money at risk?)",
                     yaxis_title="AED", **_LAYOUT)

    lang = msgs["language"].value_counts()
    c6 = _bar([theme.LANG_NAMES.get(l, l) for l in lang.index], lang.values,
              "Languages in the inbox (why multilingual matters)", "#7DA2CE")

    rec = q["recommended"].value_counts()
    c7 = _bar(rec.values, rec.index,
              "What the rules recommend across the queue", "#5EEAD4",
              orientation="h")

    stats = SERVICES.review_stats()
    if len(stats):
        out = stats["human_verdict"].value_counts()
        c8 = _bar(out.index, out.values,
                  "Human review outcomes (from the audit log)", "#34D399")
    else:
        c8 = go.Figure()
        c8.update_layout(title="Human review outcomes - no reviews logged yet",
                         **_LAYOUT)
        c8.add_annotation(text="Approve or reject cases in Triage to populate this chart",
                          showarrow=False, font=dict(color="#64748B"))

    rng = np.random.default_rng(7)
    base = (q["band"].isin(["High", "Critical"])).sum()
    months = pd.date_range("2026-01-01", periods=7, freq="MS").strftime("%b %Y")
    trend = np.clip(base * (0.55 + 0.09 * np.arange(7))
                    + rng.normal(0, 3, 7), 0, None).round(0)
    c9 = go.Figure(go.Scatter(x=list(months), y=trend, mode="lines+markers",
                              line=dict(color="#F87171", width=3)))
    c9.update_layout(title="SIMULATED - monthly high-risk customer trend "
                           "(illustrative trajectory, not measured data)",
                     **_LAYOUT)
    return c1, c2, c3, c4, c5, c6, c7, c8, c9


def build() -> None:
    charts = _charts()
    plots = []
    with gr.Row():
        plots += [gr.Plot(charts[0]), gr.Plot(charts[1])]
    with gr.Row():
        plots += [gr.Plot(charts[2]), gr.Plot(charts[3])]
    with gr.Row():
        plots += [gr.Plot(charts[4]), gr.Plot(charts[5])]
    with gr.Row():
        plots += [gr.Plot(charts[6]), gr.Plot(charts[7])]
    plots.append(gr.Plot(charts[8]))
    refresh = gr.Button("Refresh analytics")
    refresh.click(lambda: list(_charts()), None, plots)
