"""Settings / demo controls - every toggle here changes real behaviour."""
from __future__ import annotations

import gradio as gr

from .. import theme
from ..services import SERVICES


def mode_badges() -> str:
    clf = SERVICES.classifier_mode()
    llm = SERVICES.llm_enabled()
    return (
        theme.badge("SYNTHETIC DATA — DEMO", "#7DA2CE")
        + theme.badge(f"CLASSIFIER: {'fine-tuned DistilmBERT' if clf == 'finetuned' else 'trained LSTM'}",
                      "#38BDF8")
        + theme.badge(f"DRAFTING: {'Qwen2.5-0.5B + guardrails' if llm else 'curated templates (instant)'}",
                      "#60A5FA")
        + theme.badge("HUMAN APPROVAL REQUIRED", "#FBBF24"))


def build(header_badges: gr.HTML) -> None:
    gr.Markdown("### Engine")
    clf = gr.Radio(["lstm", "finetuned"], value=SERVICES.classifier_mode(),
                   label="Active classifier (WAFA_CLASSIFIER)",
                   info="lstm = instant, perfect on reference data · finetuned "
                        "= DistilmBERT pair, ~10 s first load, generalizes far "
                        "better to novel wording (54% vs 32% unseen issue acc)")
    llm = gr.Checkbox(value=SERVICES.llm_enabled(),
                      label="Use Qwen2.5-0.5B for outreach drafts (WAFA_USE_LLM)",
                      info="On: real LLM drafts, 30-60 s each on CPU, guardrails "
                           "+ template fallback. Off: curated multilingual "
                           "templates, instant - the demo-insurance mode.")
    status = gr.Markdown("")

    def set_clf(mode):
        SERVICES.set_classifier(mode)
        warm = (" First fine-tuned prediction will load two DistilmBERT "
                "models (~10 s)." if mode == "finetuned" else "")
        return f"✅ Classifier set to **{mode}**.{warm}", mode_badges()

    def set_llm(enabled):
        SERVICES.set_llm(enabled)
        return (f"✅ Drafting mode: **{'Qwen + guardrails' if enabled else 'templates only'}**.",
                mode_badges())

    clf.change(set_clf, clf, [status, header_badges])
    llm.change(set_llm, llm, [status, header_badges])

    gr.Markdown("### Demo notes")
    gr.HTML(
        "<div class='gov'>Runs fully offline once models are cached - no paid "
        "APIs anywhere. Break-glass: templates-only mode above, or "
        "<code>python app_simple.py</code> for the minimal fallback UI. "
        "Scenario data, models and metrics all come from the repository "
        "files, so the demo is reproducible on any laptop with "
        "<code>pip install -r requirements.txt</code>.</div>")
    gr.HTML(
        "<div class='gov'>Future backend: every dashboard callback already "
        "routes through dashboard/services.py, whose methods map 1:1 to the "
        "planned REST endpoints (POST /api/analyze-message, /api/fuse-risk, "
        "/api/recommend-action, /api/generate-outreach, /api/review-decision, "
        "GET /api/analytics, /api/audit-log). Swapping Gradio for FastAPI "
        "re-exposes these functions - no logic rewrite.</div>")
