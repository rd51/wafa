# Project Wafa — Implementation Guide

How to get the retention intelligence dashboard running locally, what data it uses, and why each piece matters in a real bank.

---

## Requirements

- Python 3.10–3.12
- ~2 GB free disk space (models + Qwen cache if LLM mode is on)
- No GPU required — everything runs on a laptop CPU

---

## First-time setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

This installs Gradio, TensorFlow-CPU, Keras, scikit-learn, Plotly, pandas, and joblib. No GPU packages, no paid APIs.

For the full evaluation pipeline (DistilmBERT fine-tuning, bake-off):

```bash
pip install -r requirements-dev.txt
```

### 2. Train the models

Both training scripts read from `data/` and write to `models/`. They take under two minutes combined on a laptop CPU.

```bash
python training/train_lstm_classifier.py   # M1 text classifier (~1 min)
python training/train_churn_model.py       # M2 churn model (seconds)
```

Output files written to `models/`:

| File | What it is |
|---|---|
| `lstm_listen.keras` | Bidirectional LSTM for issue type + churn signal |
| `lstm_listen_meta.json` | Vocabulary and label mappings |
| `lstm_eval.json` | Held-out and unseen-template accuracy numbers |
| `churn_model.joblib` | Logistic regression churn pipeline |
| `churn_eval.json` | AUC, calibration, per-region fairness audit |

### 3. Launch the dashboard

```bash
python app.py
```

Open `http://localhost:7860` in a browser. The full 8-tab cockpit loads: Overview, Triage, Review queue, Analytics, Model evaluation, Fairness & ethics, Audit log, Settings.

**Minimal fallback** (2 tabs, no dashboard imports needed):

```bash
python app_simple.py
```

---

## Environment variables

Set these before running `app.py` to change behaviour without editing code.

| Variable | Default | Effect |
|---|---|---|
| `WAFA_USE_LLM` | `1` | Set to `0` to skip Qwen and use curated templates instead — instant responses, no 1 GB download |
| `WAFA_CLASSIFIER` | `lstm` | Set to `finetuned` to serve the fine-tuned DistilmBERT pair (better on novel phrasing, ~10 s first-load) |
| `WAFA_PORT` | `7860` | Change the port |
| `WAFA_SHARE` | `1` | Set to `0` to disable the public Gradio tunnel link |

**Recommended for local demos:**

```bash
WAFA_USE_LLM=0 WAFA_SHARE=0 python app.py
```

This gives instant template drafts and keeps the app local-only.

---

## Smoke test

Runs three demo scenarios end-to-end (M1 → M2 → M3 → audit log) without the UI:

```bash
python training/smoke_test.py
```

---

## LLM mode (optional)

With `WAFA_USE_LLM=1` (the default), the first analysis triggers a ~1 GB download of `Qwen/Qwen2.5-0.5B-Instruct` from HuggingFace, cached to `~/.cache/huggingface/`. Subsequent runs use the cache. Draft generation takes 30–60 seconds on CPU.

If the LLM draft fails any guardrail check (urgency language, unfilled placeholders, invented amounts, wrong language, too short), it is automatically replaced by the curated multilingual template for that action. The guardrail decision is logged.

---

## Fine-tuned DistilmBERT (optional, best accuracy on novel messages)

Run on free Google Colab (T4 GPU, ~2 min per task) or locally on CPU (~7 min per task):

```bash
python training/finetune_distilmbert_colab.py --task churn_signal --csv data/messages.csv
python training/finetune_distilmbert_colab.py --task issue_type  --csv data/messages.csv
```

Copy the output folders (`wafa_finetuned_churn_signal/`, `wafa_finetuned_issue_type/`) into `models/`, then launch with `WAFA_CLASSIFIER=finetuned`.

---

## Full evaluation pipeline

Reproduces every number on the Model Evaluation tab:

```bash
python training/make_unseen_testset.py          # build honest out-of-template test set
python training/evaluate_models.py --with-llm  # 4-model bake-off -> models/bakeoff_results.json
```

Results are read live by the dashboard — no manual copy-paste.

---

## Project structure

```
project_wafa/
├── app.py                    # full 8-tab Gradio cockpit
├── app_simple.py             # 2-tab fallback
├── wafa/
│   ├── contracts.py          # TypedDict interfaces between M1/M2/M3
│   ├── m1_listen.py          # language detection, LSTM classifiers, entity extraction
│   ├── m2_understand.py      # churn model fusion, risk banding, explainability
│   ├── m3_act.py             # decision rules, offer economics, Qwen drafting, guardrails
│   └── audit.py              # append-only JSONL audit log
├── dashboard/
│   ├── services.py           # single data-loading layer used by all tabs
│   ├── theme.py              # CSS + colour tokens
│   └── components/           # one module per tab
├── data/
│   ├── customers.csv         # 240 synthetic customer profiles
│   ├── messages.csv          # 252 labelled messages (4 languages, 7 issue types)
│   ├── messages_unseen.csv   # honest evaluation set (novel phrasings)
│   └── generate_wafa_data.py # synthetic data generator
├── models/                   # trained artefacts (written by training scripts)
├── training/                 # all training and evaluation scripts
├── logs/
│   └── audit_log.jsonl       # append-only decision log (grows with each triage)
└── docs/                     # architecture doc, business report, ethics statement
```

---

## The data — what it is, why it exists, and how it maps to real banking

### `data/customers.csv` — 240 customer profiles

Each row is one bank customer with 14 fields:

| Column | What it captures | Real-world source |
|---|---|---|
| `customer_id` | Unique ID (FB1000–FB1239) | CRM primary key |
| `nationality_region` | Region grouping (MENA, South_Asia, East_Asia, Western, African) | Passport/KYC record — **excluded from all model features** (fairness) |
| `tenure_months` | How long they have been a customer | Account open date |
| `segment` | Mass / Premium / Private | Relationship tier from CLV + balance |
| `products_held` | Count of active products | Product holding database |
| `avg_balance_aed` | 12-month average balance | Core banking system |
| `balance_trend_3m` | 3-month % change in balance | Derived from transaction history |
| `salary_credit_active` | Whether salary is still credited | Payroll transaction flag |
| `remittance_count_3m` | Outbound remittances in last 3 months | Transfer records |
| `intl_transfer_spike` | Unusual international transfer activity | Anomaly flag from transaction monitoring |
| `complaints_6m` | Complaint count in last 6 months | CRM ticket system |
| `branch_visits_trend` | Direction of branch visit frequency | Branch attendance log |
| `clv_estimate_aed` | Customer lifetime value estimate | Revenue model (fees + interest margin) |
| `churned` | Ground-truth churn label | Account closure event |

**Why synthetic?** A real bank cannot share customer data for an academic project. The generator (`data/generate_wafa_data.py`) replicates the statistical relationships a bank would actually observe: declining balances co-occur with salary credit stops; high remittance customers are more likely to be relocating; Premium customers tend to higher CLV. The synthetic distribution makes the churn model learnable, while keeping all personally identifying information fictional.

**Real-world use:** In production, this table would be a daily extract from the core banking system joined with the CRM. The churn model pipeline (`churn_model.joblib`) is a sklearn `Pipeline` object — swap in the real CSV and retrain with `train_churn_model.py`. The feature names and types are designed to match what any retail bank already tracks.

**What the model learns from it:** The Logistic Regression churn model finds that `balance_trend_3m` (coefficient –3.60) is the strongest single predictor of churn — a customer draining their balance is the clearest signal. `salary_credit_active=False` (coefficient –2.8) is the second: a salary stopping is nearly always a resignation. These coefficients power the per-customer "why" shown on the Triage tab.

**Fairness note:** `nationality_region` is deliberately excluded from every model. It is used only post-hoc to audit whether the model's predicted risk skews by region. The audit (`models/churn_eval.json`) shows calibrated predictions across all five regions — the model is not using a demographic proxy to rank risk.

---

### `data/messages.csv` — 252 customer messages

Each row is one inbound message with 6 fields:

| Column | What it captures | Real-world source |
|---|---|---|
| `message_id` | Unique ID (M0000–M0251) | Message queue ID |
| `customer_id` | Links to the customer profile | CRM join key |
| `text` | The raw message text | Chat / email / SMS |
| `language` | `en` / `ar` / `hi` / `tl` | Detected or declared language |
| `issue_type` | One of 7 categories (Account_Closure, Fees_Charges, App_Technical, Card_Services, Remittance_Transfer, Loan_Mortgage, General_Query) | Label used to train M1 |
| `churn_signal` | Low / Medium / High | Label used to train M1 churn signal head |

**Languages covered:**

| Language | Why it matters in UAE banking |
|---|---|
| English (`en`) | Business language; used by ~55% of the inbox |
| Arabic (`ar`) | Official language; used by MENA nationals and long-tenure customers |
| Hindi romanized (`hi`) | South Asian expatriate workforce; written in Latin script, not Devanagari — standard NLP tools misdetect it |
| Tagalog (`tl`) | Filipino workforce; largest single-nationality expat group in UAE |

**Why these four?** UAE's expat workforce spans over 200 nationalities, but these four languages account for the majority of retail banking messages in the Gulf. A retention platform that only handles English would fail most of its customers silently.

**How M1 uses it:** The Bidirectional LSTM trains on `text` → (`issue_type`, `churn_signal`) as a dual-head classification task. Both heads share a sentence representation learned from the message text. The model is small (< 2 MB) and trains from scratch in one minute — it learns the vocabulary of these specific banking issues and churn phrases, in all four languages at once, without any translation step.

**Real-world use:** In production, messages would come from a bank's digital channel (WhatsApp Business API, email inbox, chatbot logs). The pipeline reads raw text in — no language pre-selection, no routing to a language-specific model. The rule-based language detector runs first (Arabic Unicode range check, Hindi keyword ratio, Tagalog keyword ratio, English as default), and the LSTM then classifies. A CX team would feed their live message queue into `wafa.listen()` and get back structured signals within 100 ms.

---

### `data/messages_unseen.csv` — honest evaluation set

A separate test set generated with **different phrasing templates** from the training set. This is what surfaces template memorization: the LSTM scores 100% on the held-out random split (shares templates with training), but drops to 32% issue accuracy on `messages_unseen.csv`. The fine-tuned DistilmBERT holds 54%, proving that pretrained multilingual representations generalize to novel wording while the LSTM memorized surface patterns.

**Why this matters in production:** Real customers do not write from templates. A system that only works on seen phrasing will fail the moment a customer says something slightly different. The unseen test set is the honest proxy for that.

---

### `logs/audit_log.jsonl` — the audit trail

Every AI decision and every human verdict is appended here. It is never overwritten — only appended. Each line is a JSON object with 15 fields including the language, issue type, churn signal, fused risk, action taken, offer amount, draft source (LLM or template), guardrail flags, human verdict (approved / edited / rejected / escalated), reviewer note, and the exact final message that was (or would have been) sent.

**Why this matters:** In a regulated bank, every customer communication decision must be auditable. The audit log provides a complete chain of custody: what the AI recommended, what the human decided, and what the customer received. The Analytics tab's "Human review outcomes" chart reads directly from this file — so the feedback loop is visible from day one.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'wafa'`**  
Run from inside `project_wafa/` — Python needs to find `wafa/` as a local package.

**`FileNotFoundError: models/lstm_listen.keras`**  
Run `python training/train_lstm_classifier.py` first.

**Qwen takes 30–60 s per draft**  
Set `WAFA_USE_LLM=0`. Templates are instant and cover all 9 action types in all 4 languages.

**Port 7860 already in use**  
Kill the existing process or set `WAFA_PORT=7861 python app.py`.

**Tab bar shows only "Overview" and "Triage"**  
The remaining tabs are in the overflow menu (the `···` button on the right of the tab bar). Click it to expand, or widen the browser window — all 8 tabs are present, Gradio collapses them into overflow at narrow widths.
