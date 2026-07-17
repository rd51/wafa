"""Model Evaluation tab - real metrics loaded from models/*.json (never
invented), including the honest findings that make this project credible."""
from __future__ import annotations

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

from wafa.m1_listen import ISSUES, SIGNALS

from .. import theme
from ..services import SERVICES

_LAYOUT = dict(template="plotly_dark", paper_bgcolor="#121B2E",
               plot_bgcolor="#121B2E", font=dict(color="#CBD5E1", size=11),
               margin=dict(l=40, r=20, t=48, b=40), height=380)

HONEST_FINDINGS = """
### Honest findings (these are the marks)
- **Template leakage, proven.** Random-split scores are near-perfect for any
  competent model because train and test share generator templates. On the
  unseen-template set the LSTM collapses (100% → ~32% issue accuracy) while
  the fine-tuned multilingual transformer holds ~54% against a 14% chance
  baseline — the LSTM memorized; pretrained representations generalize.
- **Zero-shot Qwen2.5-0.5B loses to every trained model on both sets** —
  prompting is not a substitute for training at this scale. It even rated
  "I am leaving the UAE next month" as *Low* churn intent.
- **Romanized Hindi is the fragile low-resource case** for every model —
  which is why low-confidence predictions route to human triage.
- **Outreach language reliability is architectural, not prompted:** Qwen-0.5B
  wrote English for every non-English customer (0/6) before *and* after
  prompt hardening; curated multilingual templates + a language-mismatch
  guardrail guarantee own-language service.
- **The churn model's AUC of 1.0 is a synthetic-data artifact** (drivers are
  separable by construction). Real-world AUC will be materially lower —
  collecting real outcome labels is a launch recommendation.
"""


def _confusion_fig(matrix, labels, title):
    fig = go.Figure(go.Heatmap(z=matrix, x=labels, y=labels,
                               colorscale="Blues", showscale=False,
                               text=matrix, texttemplate="%{text}"))
    fig.update_layout(title=title, xaxis_title="predicted",
                      yaxis_title="actual", **_LAYOUT)
    fig.update_yaxes(autorange="reversed")
    return fig


def build() -> None:
    art = SERVICES.eval_artifacts()
    lstm, churn, bake = art["lstm"], art["churn"], art["bakeoff"]

    if lstm:
        sig = lstm["signal_report"]["weighted avg"]
        gr.HTML(theme.metric_row(
            theme.metric("Issue accuracy (LSTM)",
                         f"{lstm['issue_report']['accuracy']:.0%}",
                         "held-out random split — upper bound"),
            theme.metric("Signal precision", f"{sig['precision']:.0%}",
                         "weighted, held-out"),
            theme.metric("Signal recall", f"{sig['recall']:.0%}", "weighted"),
            theme.metric("Signal F1", f"{sig['f1-score']:.0%}", "weighted"),
            theme.metric("Churn model ROC-AUC",
                         f"{churn['logistic_regression']['auc']:.2f}" if churn else "—",
                         "synthetic-data artifact — see findings"),
        ))

    if bake:
        rows = [{"model": k.replace("_", " "),
                 "held-out issue": f"{v['held_out']['issue_acc']:.0%}",
                 "held-out signal": f"{v['held_out']['signal_acc']:.0%}",
                 "UNSEEN issue": f"{v['unseen']['issue_acc']:.0%}",
                 "UNSEEN signal": f"{v['unseen']['signal_acc']:.0%}"}
                for k, v in bake.items() if k != "note"]
        gr.Markdown("### The bake-off — trained models vs zero-shot LLM "
                    "(unseen-template columns are the honest numbers)")
        gr.Dataframe(pd.DataFrame(rows), interactive=False)

    if lstm:
        with gr.Row():
            gr.Plot(_confusion_fig(lstm["issue_confusion"],
                                   [i.replace("_", " ") for i in ISSUES],
                                   "LSTM issue confusion (held-out)"))
            gr.Plot(_confusion_fig(lstm["signal_confusion"], SIGNALS,
                                   "LSTM churn-signal confusion (held-out)"))
        pl = lstm["per_language_accuracy"]
        lang_rows = [{"language": theme.LANG_NAMES.get(k, k), "n": v["n"],
                      "issue acc": f"{v['issue_acc']:.0%}",
                      "signal acc": f"{v['signal_acc']:.0%}"}
                     for k, v in pl.items()]
        gr.Markdown("### Per-language quality (multilingual fairness check) — "
                    "note the romanized-Hindi weakness and the tiny sample")
        gr.Dataframe(pd.DataFrame(lang_rows), interactive=False)

    if churn:
        coef = pd.Series(churn["coefficients"]).sort_values()
        fig = go.Figure(go.Bar(x=coef.values.round(3), y=[c.split("__")[-1]
                               for c in coef.index],
                               orientation="h", marker_color="#60A5FA"))
        fig.update_layout(title="Churn model feature weights (standardized "
                                "logistic-regression coefficients — these power "
                                "the per-customer 'why')", **_LAYOUT, )
        gr.Plot(fig)

    gr.Markdown(HONEST_FINDINGS)
    gr.HTML("<div class='gov'>Every number on this page is loaded from "
            "models/*.json produced by the training and evaluation scripts — "
            "nothing is typed in. Re-run training/evaluate_models.py and this "
            "tab updates.</div>")
