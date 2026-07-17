"""Review queue - all messages batch-scored and ranked by fused risk.
Selecting a row loads it into the Triage tab for full analysis and review."""
from __future__ import annotations

import gradio as gr

from .. import theme
from ..services import SERVICES
from ..state import FREE_INPUT

_COLS = ["message_id", "customer_id", "lang", "issue", "signal",
         "fused_risk", "band", "segment", "clv_aed", "recommended", "status"]


def _view(band_filter: str, status_filter: str):
    q = SERVICES.build_queue()
    if band_filter != "All":
        q = q[q["band"] == band_filter]
    if status_filter != "All":
        q = q[q["status"] == status_filter]
    v = q[_COLS].copy()
    v["fused_risk"] = (v["fused_risk"] * 100).round(0).astype(int)
    v["clv_aed"] = v["clv_aed"].round(0).astype(int)
    return v


def _summary():
    q = SERVICES.build_queue()
    pending = (q["status"] == "Pending Review").sum()
    return theme.metric_row(
        theme.metric("Queue size", f"{len(q)}", "all inbound messages, scored"),
        theme.metric("Pending review", f"{int(pending)}",
                     "awaiting a human decision"),
        theme.metric("Critical band", f"{(q['band'] == 'Critical').sum()}",
                     "work these first"),
        theme.metric("Confirmed leavers", f"{int(q['action'].eq('dignified_goodbye').sum())}",
                     "route to dignified goodbye"),
    )


def build(triage_handles: dict, tabs: gr.Tabs) -> None:
    gr.Markdown("Ranked by fused risk (batch-scored with the trained LSTM + "
                "churn model at startup). Click a row, then open it in Triage "
                "for the full journey and human review.")
    summary = gr.HTML(_summary())
    with gr.Row():
        band_f = gr.Dropdown(["All", "Critical", "High", "Medium", "Low"],
                             value="All", label="Risk band", scale=1)
        status_f = gr.Dropdown(["All", "Pending Review", "Approved",
                                "Approved with edits", "Overridden", "Rejected",
                                "Escalated", "Dignified Goodbye"],
                               value="All", label="Status", scale=1)
        refresh = gr.Button("Refresh", scale=0)
    table = gr.Dataframe(value=_view("All", "All"), interactive=False,
                         max_height=460)
    selected = gr.State(None)
    sel_md = gr.Markdown("*No row selected.*")
    open_btn = gr.Button("Open selected case in Triage", variant="primary")

    def on_select(band, status, evt: gr.SelectData):
        v = _view(band, status)
        if evt.index is None or evt.index[0] >= len(v):
            return None, "*No row selected.*"
        row = v.iloc[evt.index[0]]
        full = SERVICES.build_queue()
        rec = full[full.message_id == row["message_id"]].iloc[0]
        return ({"message_id": rec["message_id"], "customer_id": rec["customer_id"],
                 "text": rec["text"]},
                f"Selected **{rec['message_id']}** · {rec['customer_id']} · "
                f"{rec['band']} ({rec['fused_risk']:.0%}) — "
                f"“{rec['text'][:90]}…”")

    def open_in_triage(sel):
        if not sel:
            return (gr.Tabs(), FREE_INPUT, "", "", "auto")
        return (gr.Tabs(selected="tab_triage"), FREE_INPUT,
                sel["text"], sel["customer_id"], "auto")

    def refresh_all(band, status):
        return _view(band, status), _summary()

    table.select(on_select, [band_f, status_f], [selected, sel_md])
    for ctrl in (band_f, status_f):
        ctrl.change(refresh_all, [band_f, status_f], [table, summary])
    refresh.click(refresh_all, [band_f, status_f], [table, summary])
    open_btn.click(open_in_triage, selected,
                   [tabs, triage_handles["scenario"], triage_handles["text_in"],
                    triage_handles["cust_in"], triage_handles["lang_sel"]])
