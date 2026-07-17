"""Triage tab - the full journey on one screen:
scenario -> profile -> analysis -> fused risk -> action -> draft -> review.
This is the screen the live demo never leaves."""
from __future__ import annotations

import gradio as gr

from wafa import m3_act

from .. import theme
from ..services import REVIEW_DECISIONS, SERVICES, TONES
from ..state import FREE_INPUT, SCENARIOS

EMPTY = ("<div class='wcard'><span class='k'>Run an analysis to populate "
         "this panel.</span></div>")


# ------------------------------------------------------------- render helpers
def _profile_html(cid: str) -> str:
    c = SERVICES.get_customer_row(cid)
    if c is None:
        return ("<div class='warn'>No profile on file for this customer id - "
                "risk will use a neutral behaviour prior and lean on the "
                "message text.</div>")
    sal = "active" if c["salary_credit_active"] else "STOPPED"
    spike = "yes" if c["intl_transfer_spike"] else "no"
    body = theme.metric_row(
        theme.metric("Segment", str(c["segment"]), f"tenure {int(c['tenure_months'])} mo"),
        theme.metric("Avg balance", theme.aed(c["avg_balance_aed"]),
                     f"3-mo trend {c['balance_trend_3m']:+.0%}"),
        theme.metric("CLV estimate", theme.aed(c["clv_estimate_aed"]),
                     f"{int(c['products_held'])} products held"),
        theme.metric("Salary credit", sal,
                     f"remittances 3m: {int(c['remittance_count_3m'])}"),
        theme.metric("Intl transfer spike", spike,
                     f"complaints 6m: {int(c['complaints_6m'])} · branch trend "
                     f"{c['branch_visits_trend']:+.0%}"),
    )
    note = ("<div class='k' style='margin-top:8px'>nationality_region is "
            "excluded from churn scoring by design - it appears only in the "
            "Fairness &amp; Ethics tab, for auditing.</div>")
    return f"<div class='wcard'><h4>Customer {cid}</h4>{body}{note}</div>"


def _analysis_html(case: dict) -> str:
    s = case["signals"]
    lang = theme.LANG_NAMES.get(s["language"], s["language"])
    ents = s["entities"]
    ent_rows = "".join(
        f"<tr><td class='k' style='padding-right:14px'>{k.replace('_',' ')}</td>"
        f"<td class='v'>{', '.join(map(str, v))}</td></tr>"
        for k, v in ents.items()) or \
        "<tr><td class='k'>no entities detected</td></tr>"
    leaving = (theme.badge("LEAVING CONFIRMED", "#F87171")
               if s["leaving_confirmed"] else
               theme.badge("no relocation statement", "#64748B"))
    warn = ""
    if min(s["issue_confidence"], s["churn_signal_confidence"]) < 0.5:
        warn = ("<div class='warn' style='margin-top:8px'>Low model confidence "
                "- this case is routed to human triage and must be read by a "
                "person before any action.</div>")
    return (
        "<div class='wcard'><h4>What the platform understood</h4>"
        + theme.msg_html(s["text"], s["language"])
        + "<div style='margin-top:10px'>"
        + theme.badge(lang.upper(), "#38BDF8")
        + theme.conf_badge("lang", s["language_confidence"])
        + theme.badge(s["issue_type"].replace("_", " / "), "#60A5FA")
        + theme.conf_badge("issue", s["issue_confidence"])
        + theme.badge(f"CHURN SIGNAL: {s['churn_signal']}",
                      theme.RISK_COLORS.get(
                          {"High": "Critical", "Medium": "Medium",
                           "Low": "Low"}[s["churn_signal"]], "#94A3B8"))
        + theme.conf_badge("signal", s["churn_signal_confidence"])
        + leaving
        + theme.badge(f"model: {s['classifier']}", "#7DA2CE")
        + "</div>"
        + f"<table style='margin-top:10px'>{ent_rows}</table>"
        + warn + "</div>")


def _risk_html(case: dict) -> str:
    r, s = case["risk"], case["signals"]
    pct = r["fused_risk"] * 100
    checks = []
    if r["needs_human_triage"]:
        checks.append("Low NLP confidence - read the original message first.")
    if s["leaving_confirmed"]:
        checks.append("Relocation stated - verify, then use the goodbye pathway.")
    if r["behaviour_score"] < 0.35 and r["text_score"] >= 0.9:
        checks.append("Behaviour looks calm but the text says otherwise - "
                      "trust the text; behaviour lags language.")
    if r["behaviour_score"] >= 0.75 and r["text_score"] <= 0.2:
        checks.append("Quiet high-risk profile - the message is routine but "
                      "the behaviour is draining; consider proactive contact.")
    if r["clv_estimate_aed"] >= 100000:
        checks.append("High-value relationship - escalate to a named RM if in doubt.")
    checks_html = "".join(f"<li>{c}</li>" for c in checks) or \
        "<li>Nothing unusual - standard review applies.</li>"
    reasons = "".join(f"<li>{x}</li>" for x in r["reasons"])
    formula = (f"fused_risk = 0.55 × behaviour ({r['behaviour_score']:.0%}) "
               f"+ 0.45 × text ({r['text_score']:.0%}) = {r['fused_risk']:.0%}")
    overrides = ("Overrides: confirmed leaver floors risk at 85% and routes to "
                 "the dignified goodbye · low NLP confidence forces human "
                 "triage · nationality/region is never an input.")
    return (
        "<div class='wcard'><h4>Fused churn risk"
        f"&nbsp;&nbsp;{theme.risk_badge(r['risk_band'])}</h4>"
        f"<div style='font-size:30px;font-weight:700;color:"
        f"{theme.RISK_COLORS[r['risk_band']]}'>{pct:.0f} / 100</div>"
        + theme.gauge(pct, r["risk_band"])
        + f"<div class='rulebox'>{formula}</div>"
        + f"<div class='k' style='margin-top:6px'>{overrides}</div>"
        + f"<h4 style='margin-top:12px'>Top churn drivers</h4><ul>{reasons}</ul>"
        + f"<h4>What the reviewer should check</h4><ul>{checks_html}</ul>"
        + "</div>")


def _action_html(case: dict) -> str:
    r, plan = case["risk"], case["plan"]
    offer = plan["offer_value_aed"]
    cap = m3_act.OFFER_CAP_PCT * r["clv_estimate_aed"]
    clv_at_risk = r["fused_risk"] * r["clv_estimate_aed"]
    econ = (f"Offer {theme.aed(offer)} vs cap {theme.aed(cap)} (2% of CLV) - "
            + ("within budget" if plan["offer_within_budget"] else
               "EXCEEDS budget, downgraded")
            if offer > 0 else "No monetary offer - relationship action only.")
    econ_cls = "ok" if plan["offer_within_budget"] else "crit"
    rules = "\n".join(plan["rationale"])
    flags = plan["guardrail_flags"]
    flags_html = ("<div class='warn' style='margin-top:8px'><b>Guardrails "
                  f"tripped ({len(flags)})</b> - LLM draft replaced by the "
                  "curated template:<br>" + "<br>".join(flags) + "</div>"
                  if flags else
                  "<div class='ok' style='margin-top:8px'>Guardrails: clean - "
                  "no violations detected in the served draft.</div>")
    return (
        "<div class='wcard'><h4>Recommended action&nbsp;&nbsp;"
        + theme.badge("HUMAN APPROVAL REQUIRED", "#FBBF24") + "</h4>"
        + f"<div class='v' style='font-size:18px'>{plan['action_label']}</div>"
        + theme.metric_row(
            theme.metric("CLV at risk", theme.aed(clv_at_risk),
                         "fused risk × CLV (assumption: full value exposed)"),
            theme.metric("Offer cost", theme.aed(offer) if offer else "—",
                         "cap = 2% of CLV"),
            theme.metric("If no action", f"{case['risk']['fused_risk']:.0%}",
                         "probability the relationship is lost"),
        )
        + f"<div class='{econ_cls}' style='margin-top:8px'>{econ}</div>"
        + f"<h4 style='margin-top:12px'>Decision rules fired (verbatim)</h4>"
        + f"<div class='rulebox'>{rules}</div>"
        + "<div class='k' style='margin-top:6px'>Policy: no retention "
        "pressure on confirmed leavers · offers must be honest and within "
        "budget · every rule above is readable code in wafa/m3_act.py.</div>"
        + flags_html + "</div>")


def _timeline_html(case: dict) -> str:
    steps = "".join(
        f"<div class='tstep {'human' if st['actor'] == 'human_reviewer' else ''}'>"
        f"<div class='t'>{st['t']} · {st['actor']}"
        + (f" · conf {st['conf']:.0%}" if st.get("conf") else "") + "</div>"
        f"<div class='s'><b>{st['step']}</b> - {st['summary']}</div></div>"
        for st in case["timeline"])
    return (f"<div class='wcard'><h4>Case timeline&nbsp;&nbsp;"
            f"{theme.status_badge(case['status'])}</h4>"
            f"<div class='timeline'>{steps}</div></div>")


def _all_panels(case: dict):
    return (_profile_html(case["signals"]["customer_id"]),
            _analysis_html(case), _risk_html(case), _action_html(case),
            _timeline_html(case))


# --------------------------------------------------------------- tab builder
def build() -> dict:
    case_state = gr.State(None)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Case intake")
            scenario = gr.Dropdown([FREE_INPUT] + list(SCENARIOS),
                                   value=FREE_INPUT, label="Demo scenario",
                                   info="Six scripted journeys drawn from real data rows")
            scenario_blurb = gr.Markdown(visible=False)
            text_in = gr.Textbox(label="Customer message", lines=4,
                                 placeholder="Paste a message in English, Arabic, Hindi (romanized) or Tagalog…")
            with gr.Row():
                cust_in = gr.Textbox(label="Customer ID", value="FB1000", scale=1)
                lang_sel = gr.Dropdown(["auto", "en", "ar", "hi", "tl"],
                                       value="auto", label="Language", scale=1,
                                       info="auto = platform detects")
            tone_sel = gr.Dropdown(TONES, value="Professional",
                                   label="Outreach tone (LLM drafts only)",
                                   info="Curated templates are tone-fixed; this steers Qwen when it drafts")
            with gr.Row():
                run_btn = gr.Button("Run analysis", variant="primary")
                reset_btn = gr.Button("Reset demo")
            status_md = gr.Markdown("")
        with gr.Column(scale=2):
            profile_html = gr.HTML(EMPTY)
            analysis_html = gr.HTML(EMPTY)

    with gr.Row():
        risk_html = gr.HTML(EMPTY)
        action_html = gr.HTML(EMPTY)

    gr.Markdown("### Outreach draft — nothing reaches a customer without the review below")
    with gr.Row():
        with gr.Column(scale=2):
            draft_box = gr.Textbox(label="Draft (editable before approval)",
                                   lines=7, interactive=True)
            draft_meta = gr.HTML("")
            with gr.Row():
                regen_btn = gr.Button("Regenerate draft")
                save_btn = gr.Button("Save draft edits")
            with gr.Accordion("Show the exact LLM prompt (ethics: tone constraints)",
                              open=False):
                prompt_box = gr.Textbox(label="Prompt", lines=8, interactive=False)
        with gr.Column(scale=1):
            gr.Markdown("### Human review")
            note_box = gr.Textbox(label="Reviewer note (goes to the audit log)",
                                  lines=2)
            override_sel = gr.Dropdown(
                [f"{k} — {v}" for k, v in m3_act.ACTION_LABELS.items()
                 if k != "human_triage"],
                label="Override action (used with the Override button)")
            with gr.Row():
                approve_btn = gr.Button("Approve & send", variant="primary")
                edit_btn = gr.Button("Approve with edits")
            with gr.Row():
                override_btn = gr.Button("Override action")
                reject_btn = gr.Button("Reject", variant="stop")
            with gr.Row():
                escalate_btn = gr.Button("Escalate to RM")
                goodbye_btn = gr.Button("Mark dignified goodbye")
            review_md = gr.Markdown("")

    timeline_html = gr.HTML(EMPTY)

    # ------------------------------------------------------------ callbacks
    def pick_scenario(name):
        if name == FREE_INPUT:
            return (gr.Markdown(visible=False), "", "FB1000", "auto")
        sc = SCENARIOS[name]
        return (gr.Markdown(f"*{sc['blurb']}*", visible=True),
                sc["text"], sc["customer_id"], "auto")

    def run(scenario_name, text, cid, lang, tone, progress=gr.Progress()):
        text = (text or "").strip()
        if not text:
            return (None, "⚠️ **Paste a message or pick a scenario first.**",
                    EMPTY, EMPTY, EMPTY, EMPTY, EMPTY,
                    gr.Textbox(value=""), "", "", "")
        mid = (SCENARIOS[scenario_name]["message_id"]
               if scenario_name != FREE_INPUT else "LIVE")
        progress(0.1, desc="M1 - reading the message")
        llm_note = ("Qwen2.5-0.5B drafting (30-60 s on CPU)…"
                    if SERVICES.llm_enabled() else "template drafting (instant)")
        progress(0.4, desc=f"M2 fusion + M3 rules · {llm_note}")
        try:
            case = SERVICES.run_case(text, (cid or "UNKNOWN").strip(), mid,
                                     lang, tone)
        except Exception as e:
            return (None, f"❌ **Analysis failed:** {e}", EMPTY, EMPTY, EMPTY,
                    EMPTY, EMPTY, gr.Textbox(value=""), "", "", "")
        progress(1.0, desc="done")
        plan = case["plan"]
        meta = (theme.badge(f"written by: {plan['draft_source']}", "#38BDF8")
                + theme.badge(f"language: {theme.LANG_NAMES[plan['draft_language']]}",
                              "#60A5FA")
                + theme.badge("REQUIRES HUMAN APPROVAL", "#FBBF24"))
        p, a, r, act, tl = _all_panels(case)
        return (case, f"✅ Analysis complete — status: **{case['status']}**",
                p, a, r, act, tl,
                gr.Textbox(value=plan["draft_message"],
                           rtl=plan["draft_language"] == "ar"),
                meta, plan["prompt_used"] or "(template draft - no LLM prompt)",
                "")

    def regenerate(case, tone, progress=gr.Progress()):
        if not case:
            return case, gr.Textbox(), "", "⚠️ Run an analysis first."
        progress(0.3, desc="Redrafting…")
        plan = SERVICES.generate_outreach(
            case["signals"], case["risk"], case["action"],
            case["rationale"], case["offer"], tone)
        case["plan"] = plan
        case["timeline"].append({"t": _ts(), "step": "Outreach re-drafted",
                                 "actor": "ai_system",
                                 "summary": f"tone={tone}, served by {plan['draft_source']}",
                                 "conf": None})
        meta = (theme.badge(f"written by: {plan['draft_source']}", "#38BDF8")
                + theme.badge(f"language: {theme.LANG_NAMES[plan['draft_language']]}", "#60A5FA")
                + theme.badge("REQUIRES HUMAN APPROVAL", "#FBBF24"))
        return (case, gr.Textbox(value=plan["draft_message"],
                                 rtl=plan["draft_language"] == "ar"),
                meta, "🔁 Draft regenerated.")

    def save_edits(case, draft):
        if not case:
            return case, "⚠️ Run an analysis first."
        case["plan"]["draft_message"] = draft
        case["timeline"].append({"t": _ts(), "step": "Draft edited",
                                 "actor": "human_reviewer",
                                 "summary": "reviewer saved manual edits",
                                 "conf": None})
        return case, "💾 Edits saved to the working draft."

    def decide(decision):
        def _fn(case, draft, note, override_label):
            if not case:
                return case, "⚠️ Run an analysis first.", EMPTY, EMPTY
            if case["status"] in REVIEW_DECISIONS:
                return (case, f"ℹ️ Already decided: **{case['status']}** — "
                        "run a new analysis for a fresh case.",
                        _action_html(case), _timeline_html(case))
            override = (override_label.split(" — ")[0]
                        if decision == "Overridden" and override_label else None)
            case = SERVICES.review_decision(case, decision, note or "",
                                            draft, override)
            return (case,
                    f"✅ **{decision}** recorded and audit-logged"
                    + (f" — note: *{note}*" if note else ""),
                    _action_html(case), _timeline_html(case))
        return _fn

    scenario.change(pick_scenario, scenario,
                    [scenario_blurb, text_in, cust_in, lang_sel])
    run_btn.click(run, [scenario, text_in, cust_in, lang_sel, tone_sel],
                  [case_state, status_md, profile_html, analysis_html,
                   risk_html, action_html, timeline_html, draft_box,
                   draft_meta, prompt_box, review_md])
    reset_btn.click(
        lambda: (None, "", EMPTY, EMPTY, EMPTY, EMPTY, EMPTY,
                 gr.Textbox(value=""), "", "", "", FREE_INPUT),
        None,
        [case_state, status_md, profile_html, analysis_html, risk_html,
         action_html, timeline_html, draft_box, draft_meta, prompt_box,
         review_md, scenario])
    regen_btn.click(regenerate, [case_state, tone_sel],
                    [case_state, draft_box, draft_meta, review_md])
    save_btn.click(save_edits, [case_state, draft_box], [case_state, review_md])
    for btn, dec in [(approve_btn, "Approved"), (edit_btn, "Approved with edits"),
                     (override_btn, "Overridden"), (reject_btn, "Rejected"),
                     (escalate_btn, "Escalated"),
                     (goodbye_btn, "Dignified Goodbye")]:
        btn.click(decide(dec), [case_state, draft_box, note_box, override_sel],
                  [case_state, review_md, action_html, timeline_html])

    return {"scenario": scenario, "text_in": text_in, "cust_in": cust_in,
            "lang_sel": lang_sel, "run_btn": run_btn}


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
