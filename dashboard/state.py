"""Demo scenarios - each picks a REAL message and a REAL customer from the
data by criteria (not hardcoded ids), so regenerating the datasets never
breaks the demo. Selecting a scenario populates the whole triage flow."""
from __future__ import annotations

import pandas as pd

from .services import SERVICES


def _pick_message(df: pd.DataFrame, **crit) -> pd.Series:
    q = df
    for col, val in crit.items():
        if col == "contains":
            q = q[q["text"].str.contains(val, case=False, regex=False)]
        else:
            q = q[q[col] == val]
    return (q.iloc[0] if len(q) else df.iloc[0])


def _pick_customer(df: pd.DataFrame, query: str) -> pd.Series:
    q = df.query(query)
    return (q.iloc[0] if len(q) else df.iloc[0])


def build_scenarios() -> dict[str, dict]:
    msgs, custs = SERVICES.messages, SERVICES.customers
    specs = [
        ("1 · Premium leaver — closing salary account (EN)",
         "High-risk Premium customer who has resigned and is leaving the UAE.",
         dict(language="en", issue_type="Account_Closure", churn_signal="High",
              contains="salary account"),
         "segment == 'Premium' and churned and not salary_credit_active"),
        ("2 · Arabic — transferring funds abroad",
         "Arabic message about moving money out; profile shows an international transfer spike.",
         dict(language="ar", issue_type="Remittance_Transfer", churn_signal="High"),
         "intl_transfer_spike and churned"),
        ("3 · Mass — remittance/fee complaint (Medium)",
         "Mass-segment customer complaining about fees; medium churn signal.",
         dict(issue_type="Fees_Charges", churn_signal="Medium"),
         "segment == 'Mass' and complaints_6m >= 3 and not churned"),
        ("4 · App failure — rising frustration",
         "Repeated technical failures plus frustration wording.",
         dict(issue_type="App_Technical", churn_signal="Medium"),
         "complaints_6m >= 4 and not churned"),
        ("5 · Private — routine query (low risk)",
         "High-value Private customer, healthy profile, simple question.",
         dict(issue_type="General_Query", churn_signal="Low"),
         "segment == 'Private' and not churned and salary_credit_active"),
        ("6 · Confirmed leaver — dignified goodbye (TL)",
         "Customer states they are relocating; correct action is a dignified goodbye, never retention pressure.",
         dict(language="tl", churn_signal="High"),
         "churned and not salary_credit_active"),
    ]
    scenarios = {}
    for title, blurb, mcrit, cquery in specs:
        m = _pick_message(msgs, **mcrit)
        c = _pick_customer(custs, cquery)
        scenarios[title] = {
            "title": title, "blurb": blurb,
            "message_id": m["message_id"], "text": m["text"],
            "language": m["language"], "customer_id": c["customer_id"],
        }
    return scenarios


SCENARIOS = build_scenarios()
FREE_INPUT = "— free input (paste any message) —"
