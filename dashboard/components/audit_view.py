"""Audit log tab - the append-only record every governance conversation
starts from: what the AI did, what the human decided, when and why."""
from __future__ import annotations

import gradio as gr

from ..services import SERVICES


def build() -> None:
    gr.Markdown(
        "Append-only record (`logs/audit_log.jsonl`). `type=event` rows are "
        "AI pipeline steps; `type=decision` rows carry the human verdict, the "
        "reviewer note, and the final message. Nothing here can be edited "
        "from the UI - that is the point.")
    table = gr.Dataframe(value=SERVICES.audit_df(), interactive=False,
                         max_height=520)
    refresh = gr.Button("Refresh")
    refresh.click(lambda: SERVICES.audit_df(), None, table)
