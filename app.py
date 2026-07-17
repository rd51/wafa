"""
Project Wafa - retention intelligence cockpit for Falcon Bank UAE.

Run:  python app.py
Env:  WAFA_USE_LLM=0        -> curated-template drafting (instant, demo insurance)
      WAFA_CLASSIFIER=finetuned -> serve the fine-tuned DistilmBERT pair
      WAFA_PORT=7860

All business logic lives in wafa/ (M1-M3) behind dashboard/services.py;
this file only assembles the tabs. The minimal fallback UI is app_simple.py.
"""
from __future__ import annotations

import os

import gradio as gr

from dashboard import theme
from dashboard.components import (analytics, audit_view, evaluation, fairness,
                                  overview, queue_view, settings, triage)

FORCE_DARK = """
() => {
  if (!document.body.classList.contains('dark')) {
    document.body.classList.add('dark');
  }
}
"""


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Project Wafa · Falcon Bank UAE") as demo:
        with gr.Row(elem_id="wafa-header"):
            with gr.Column(scale=3):
                gr.HTML("<h1>Project Wafa <span style='color:#38BDF8'>·</span> "
                        "retention intelligence</h1>"
                        "<div class='sub'>Falcon Bank UAE — customer-experience "
                        "& retention cockpit. Wafa (وفاء) means loyalty, and it "
                        "runs both ways.</div>")
            with gr.Column(scale=2):
                header_badges = gr.HTML(settings.mode_badges())

        with gr.Tabs() as tabs:
            with gr.Tab("Overview", id="tab_overview"):
                overview.build()
            with gr.Tab("Triage", id="tab_triage"):
                triage_handles = triage.build()
            with gr.Tab("Review queue", id="tab_queue"):
                queue_view.build(triage_handles, tabs)
            with gr.Tab("Analytics", id="tab_analytics"):
                analytics.build()
            with gr.Tab("Model evaluation", id="tab_eval"):
                evaluation.build()
            with gr.Tab("Fairness & ethics", id="tab_fairness"):
                fairness.build()
            with gr.Tab("Audit log", id="tab_audit"):
                audit_view.build()
            with gr.Tab("Settings / demo controls", id="tab_settings"):
                settings.build(header_badges)

        gr.HTML("<div class='footer-disclaimer'>Synthetic data only - Falcon "
                "Bank UAE is fictional. Every AI output shows confidence and "
                "requires human approval before reaching a customer. "
                "MAIB AI 115 · Final Group Project · Project Wafa team.</div>")
    return demo


if __name__ == "__main__":
    app = build_app()
    # Bind 0.0.0.0 inside a container; hosts like Render/Railway inject $PORT.
    # Locally, WAFA_HOST/WAFA_PORT still work and default to a public bind.
    host = os.environ.get("WAFA_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("WAFA_PORT", "7860")))
    app.launch(server_name=host, server_port=port,
               css=theme.CSS, js=FORCE_DARK,
               theme=gr.themes.Base(primary_hue="sky", neutral_hue="slate"))
