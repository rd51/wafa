"""
Service layer: every dashboard callback goes through here, never straight to
the models. Each public method maps 1:1 to a future REST endpoint
(POST /api/analyze-message, POST /api/fuse-risk, POST /api/recommend-action,
POST /api/generate-outreach, POST /api/review-decision, GET /api/audit-log,
GET /api/analytics ...), so swapping Gradio callbacks for FastAPI routes later
means re-exposing these functions, not rewriting logic.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from wafa import audit, m1_listen, m2_understand, m3_act
from wafa.contracts import ActionPlan, ListenSignals, RiskAssessment

ROOT = Path(__file__).resolve().parent.parent

TONES = ["Professional", "Warm", "Concise", "Arabic Formal", "Supportive"]
REVIEW_DECISIONS = ["Approved", "Approved with edits", "Overridden",
                    "Rejected", "Escalated", "Dignified Goodbye"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class WafaServices:
    """Singleton facade over M1/M2/M3 + data + audit."""

    def __init__(self) -> None:
        self.customers = pd.read_csv(ROOT / "data" / "customers.csv")
        self.messages = pd.read_csv(ROOT / "data" / "messages.csv")
        self._queue: pd.DataFrame | None = None
        self._queue_status: dict[str, str] = {}
        self._cust_scores: pd.DataFrame | None = None

    # ------------------------------------------------------------- config
    @staticmethod
    def classifier_mode() -> str:
        return os.environ.get("WAFA_CLASSIFIER", "lstm")

    @staticmethod
    def llm_enabled() -> bool:
        return os.environ.get("WAFA_USE_LLM", "1") != "0"

    @staticmethod
    def set_classifier(mode: str) -> None:
        os.environ["WAFA_CLASSIFIER"] = mode

    @staticmethod
    def set_llm(enabled: bool) -> None:
        os.environ["WAFA_USE_LLM"] = "1" if enabled else "0"

    def get_customer_row(self, cid: str):
        m = self.customers[self.customers.customer_id == cid]
        return m.iloc[0] if len(m) else None

    # -------------------------------------------------- core pipeline calls
    def analyze_message(self, text: str, customer_id: str,
                        message_id: str = "LIVE",
                        lang_override: str | None = None) -> ListenSignals:
        signals = m1_listen.listen(text, customer_id, message_id)
        if lang_override and lang_override != "auto":
            signals["language"] = lang_override
            signals["language_confidence"] = 1.0
        return signals

    def fuse_risk(self, signals: ListenSignals) -> RiskAssessment:
        return m2_understand.assess_risk(signals)

    def recommend_action(self, signals: ListenSignals,
                         risk: RiskAssessment) -> tuple[str, list[str], float]:
        return m3_act.decide(signals, risk)

    def generate_outreach(self, signals: ListenSignals, risk: RiskAssessment,
                          action: str, rationale: list[str], offer: float,
                          tone: str | None = None) -> ActionPlan:
        draft, lang, source, flags, prompt = m3_act.draft_outreach(
            signals, risk, action, rationale, offer, tone=tone)
        cap = m3_act.OFFER_CAP_PCT * risk["clv_estimate_aed"]
        return {
            "customer_id": signals["customer_id"], "action": action,
            "action_label": m3_act.ACTION_LABELS[action],
            "rationale": rationale, "offer_value_aed": offer,
            "offer_within_budget": offer <= cap if offer > 0 else True,
            "draft_message": draft, "draft_language": lang,
            "draft_source": source, "guardrail_flags": flags,
            "prompt_used": prompt,
        }

    def run_case(self, text: str, customer_id: str, message_id: str = "LIVE",
                 lang_override: str | None = None,
                 tone: str | None = None, with_draft: bool = True) -> dict:
        """The full journey for one message; returns a case dict with an
        in-memory timeline the triage tab renders."""
        timeline: list[dict] = []

        def step(name, actor, summary, conf=None):
            timeline.append({"t": _now(), "step": name, "actor": actor,
                             "summary": summary, "conf": conf})

        step("Message received", "ai_system", f"{len(text)} chars, customer {customer_id}")
        signals = self.analyze_message(text, customer_id, message_id, lang_override)
        step("Language detected", "ai_system",
             f"{signals['language']}", signals["language_confidence"])
        step("Issue classified", "ai_system",
             f"{signals['issue_type']} (model: {signals['classifier']})",
             signals["issue_confidence"])
        step("Churn signal detected", "ai_system",
             signals["churn_signal"], signals["churn_signal_confidence"])
        ents = ", ".join(f"{k}: {v}" for k, v in signals["entities"].items()) or "none"
        step("Entities extracted", "ai_system", ents)

        risk = self.fuse_risk(signals)
        step("Behaviour model scored", "ai_system",
             f"P(churn) = {risk['behaviour_score']:.0%}"
             + ("" if risk["profile_found"] else " (no profile - neutral prior)"))
        step("Fused risk calculated", "ai_system",
             f"{risk['fused_risk']:.0%} -> {risk['risk_band']}")

        action, rationale, offer = self.recommend_action(signals, risk)
        step("Action recommended", "ai_system", m3_act.ACTION_LABELS[action])

        plan = None
        if with_draft:
            plan = self.generate_outreach(signals, risk, action, rationale,
                                          offer, tone)
            src = ("LLM (Qwen2.5-0.5B)" if plan["draft_source"] == "llm"
                   else "curated template")
            note = (f" - guardrails tripped: {len(plan['guardrail_flags'])}"
                    if plan["guardrail_flags"] else "")
            step("Outreach drafted", "ai_system",
                 f"{src} in {plan['draft_language']}{note}")

        audit.log_event("case_analyzed", "ai_system",
                        f"{message_id} {signals['issue_type']} "
                        f"{signals['churn_signal']} -> {risk['risk_band']} "
                        f"-> {action}",
                        confidence=signals["issue_confidence"],
                        customer_id=customer_id, message_id=message_id)
        return {"signals": signals, "risk": risk, "action": action,
                "rationale": rationale, "offer": offer, "plan": plan,
                "status": "Pending Review" if with_draft else "Drafted",
                "timeline": timeline}

    # ------------------------------------------------------------- review
    def review_decision(self, case: dict, decision: str, note: str,
                        final_draft: str, override_action: str | None = None) -> dict:
        signals, risk, plan = case["signals"], case["risk"], dict(case["plan"])
        if decision == "Overridden" and override_action:
            plan["action"] = override_action
            plan["action_label"] = m3_act.ACTION_LABELS.get(
                override_action, override_action)
        if decision == "Dignified Goodbye":
            plan["action"] = "dignified_goodbye"
            plan["action_label"] = m3_act.ACTION_LABELS["dignified_goodbye"]
        final = "" if decision == "Rejected" else (final_draft or plan["draft_message"])
        audit.log_decision(signals, risk, plan, decision, final, reviewer_note=note)
        case["status"] = decision
        case["timeline"].append({
            "t": _now(), "step": "Human reviewed", "actor": "human_reviewer",
            "summary": decision + (f' - "{note}"' if note else ""), "conf": None})
        case["timeline"].append({
            "t": _now(), "step": "Final decision logged", "actor": "ai_system",
            "summary": "appended to logs/audit_log.jsonl", "conf": None})
        self._queue_status[signals["message_id"]] = decision
        return case

    # -------------------------------------------------------------- queue
    def build_queue(self) -> pd.DataFrame:
        """Batch-score every message (LSTM batched + churn model) and rank by
        fused risk - the review queue the retention team would work down."""
        if self._queue is not None:
            return self._annotated_queue()
        msgs = self.messages
        model = m1_listen._get_lstm()
        if model is not None:
            x = model.vectorizer(np.array(msgs["text"].tolist()))
            p_issue, p_signal = model.model.predict(x, batch_size=64, verbose=0)
            issues = [m1_listen.ISSUES[i] for i in p_issue.argmax(1)]
            i_conf = p_issue.max(1)
            sigs = [m1_listen.SIGNALS[i] for i in p_signal.argmax(1)]
            s_conf = p_signal.max(1)
        else:  # heuristic fallback keeps the queue alive without the model
            hs = [m1_listen._heuristic_classify(t) for t in msgs["text"]]
            issues, i_conf, sigs, s_conf = ([h[0] for h in hs], [h[1] for h in hs],
                                            [h[2] for h in hs], [h[3] for h in hs])
        rows = []
        for j, m in enumerate(msgs.itertuples()):
            signals: ListenSignals = {
                "message_id": m.message_id, "customer_id": m.customer_id,
                "text": m.text, "language": m.language, "language_confidence": 1.0,
                "issue_type": issues[j], "issue_confidence": float(i_conf[j]),
                "churn_signal": sigs[j], "churn_signal_confidence": float(s_conf[j]),
                "leaving_confirmed": m1_listen.leaving_confirmed(m.text),
                "entities": {}, "classifier": "lstm" if model else "heuristic",
            }
            risk = self.fuse_risk(signals)
            action, _, offer = self.recommend_action(signals, risk)
            rows.append({
                "message_id": m.message_id, "customer_id": m.customer_id,
                "lang": m.language, "issue": issues[j], "signal": sigs[j],
                "fused_risk": risk["fused_risk"], "band": risk["risk_band"],
                "segment": risk["segment"], "clv_aed": risk["clv_estimate_aed"],
                "recommended": m3_act.ACTION_LABELS[action],
                "action": action, "offer": offer, "text": m.text,
            })
        self._queue = (pd.DataFrame(rows)
                       .sort_values("fused_risk", ascending=False)
                       .reset_index(drop=True))
        return self._annotated_queue()

    def _annotated_queue(self) -> pd.DataFrame:
        q = self._queue.copy()
        q["status"] = q["message_id"].map(self._queue_status).fillna("Pending Review")
        return q

    # ---------------------------------------------------------- analytics
    def customer_scores(self) -> pd.DataFrame:
        if self._cust_scores is None:
            df = self.customers.copy()
            df[["salary_credit_active", "intl_transfer_spike"]] = df[
                ["salary_credit_active", "intl_transfer_spike"]].astype(int)
            model = m2_understand._load()[1]
            X = df[m2_understand.NUMERIC + m2_understand.BOOLEAN + m2_understand.CATEG]
            df["behaviour_risk"] = model.predict_proba(X)[:, 1] if model is not None else 0.5
            df["band"] = df["behaviour_risk"].apply(m2_understand._band)
            self._cust_scores = df
        return self._cust_scores

    def driver_counts(self) -> pd.Series:
        df = self.customer_scores()
        at_risk = df[df["behaviour_risk"] >= 0.55]
        counts: dict[str, int] = {}
        labels = {  # short chart labels for m2's reason rules
            "balance_trend_3m": "Negative balance trend",
            "salary_credit_active": "Salary credit inactive",
            "intl_transfer_spike": "Intl transfer spike",
            "complaints_6m": "Multiple complaints",
            "branch_visits_trend": "Branch visits declining",
            "tenure_months": "New relationship",
            "remittance_count_3m": "High remittance activity",
        }
        for feat, cond, _ in m2_understand._REASON_RULES:
            n = int(at_risk[feat].apply(cond).sum())
            if n:
                counts[labels[feat]] = n
        return pd.Series(counts).sort_values()

    def review_stats(self) -> pd.DataFrame:
        rows = [e for e in audit.read_log() if e.get("human_verdict")]
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        seg = self.customers.set_index("customer_id")["segment"]
        df["segment"] = df["customer_id"].map(seg).fillna("Unknown")
        return df

    # ------------------------------------------------------ eval artifacts
    def eval_artifacts(self) -> dict:
        out = {}
        for key, fname in [("lstm", "lstm_eval.json"), ("churn", "churn_eval.json"),
                           ("bakeoff", "bakeoff_results.json"),
                           ("outreach", "outreach_language_check.json"),
                           ("outreach_v1", "outreach_language_check_v1_before_prompt_fix.json")]:
            p = ROOT / "models" / fname
            out[key] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        return out

    def audit_df(self) -> pd.DataFrame:
        rows = audit.read_log()
        if not rows:
            return pd.DataFrame(columns=["timestamp", "type", "actor/verdict",
                                         "customer", "summary", "status"])
        recs = []
        for e in rows[::-1]:
            recs.append({
                "timestamp": e.get("timestamp", ""),
                "type": e.get("type", "decision"),
                "actor/verdict": e.get("actor") or e.get("human_verdict", ""),
                "customer": e.get("customer_id", ""),
                "summary": e.get("summary") or
                           f"{e.get('issue_type','')} {e.get('churn_signal','')} "
                           f"-> {e.get('risk_band','')} -> {e.get('action','')}",
                "status": e.get("status") or e.get("human_verdict", ""),
            })
        return pd.DataFrame(recs)


SERVICES = WafaServices()
