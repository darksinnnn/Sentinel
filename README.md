# Sentinel — AI-Powered Suspicious Activity Detection

A conversational AML investigation workbench built for the banking hackathon's Problem Statement 1. An analyst asks a question in plain English; Sentinel dynamically decides which tools to run, scores and classifies the relevant transactions/customers, explains every flag in grounded natural language, and returns a structured, fully auditable response.

---

## Problem Statement

Financial institutions are required to run Anti-Money Laundering (AML) compliance programs, but traditional rule-based systems generate overwhelming false-positive volumes while still missing sophisticated laundering techniques like structuring, smurfing, and layering. Sentinel is an autonomous agent that parses a natural-language query, dynamically builds an execution plan (not a fixed pipeline — different queries invoke different tools), scores suspicious activity, and returns an explainable, structured risk assessment with a recommended escalation action.

---

## Solution Approach

Sentinel is built around a strict separation of concerns: an intent-parsing layer decides *what* to do, a fixed registry of deterministic tools does the actual work, and a narration layer explains the result — the system never lets free-text generation substitute for computation.

**End-to-end flow:**

```
User query
  → Intent extraction (LLM call, with a deterministic fallback parser)
  → Orchestrator routes to a query-specific tool chain:
      broad_scan         → EDA → anomaly scoring → risk classification → graph analysis → explanation
      targeted_pattern    → anomaly scoring → risk classification → (graph analysis if relevant) → explanation
      aggregation_query   → direct threshold/count query → explanation   (no ML/anomaly step needed)
      single_entity_lookup→ entity lookup → sanctions screening → trajectory check → explanation
      follow_up           → session memory lookup → explanation
  → Every flagged item is returned with: risk level, evidence, a grounded explanation, and a
    recommended escalation action (monitor / review / report)
  → Every step is written to a hash-chained, tamper-evident audit log
```

This satisfies the hackathon's core "agentic" requirement directly: the system does not run one fixed sequence for every query — it inspects the query's intent and invokes only the tools that specific question actually needs (e.g. a direct aggregation query skips anomaly scoring entirely; a single-entity lookup skips full dataset scanning).

### Tool registry

| Tool | Role |
|---|---|
| EDA Tool | Dataset-level profiling — transaction volume, risk distribution, geographic/temporal trends |
| Anomaly/Risk Scoring | Reads model-scored transactions, applies date/filter scoping |
| Risk Classifier | Converts raw scores into a structured, evidence-attached risk record |
| Entity Lookup | Direct single-customer/account drill-down |
| Sanctions/PEP Screening | Fuzzy + token-based matching against the real US Treasury OFAC SDN list |
| Aggregation Tool | Direct threshold/count rule queries (e.g. "10+ transactions under $10k") — no ML needed |
| Graph Analysis | NetworkX-based detection of fan-out, fan-in, and cyclic transaction patterns (mule-network-style structures) |
| Trajectory Ledger | Accumulates weak/borderline signals for an entity over time, so activity that looks unremarkable in any single query can still surface if it accumulates |
| Explanation Layer | Generates a grounded natural-language reason for every flag, tied to the query and the detected pattern |
| Custom Upload | Accepts an analyst-provided CSV for ad-hoc scoring outside the primary dataset |

Every response conforms to a single structured JSON schema (`execution_summary`, `flagged_items[]`, `supporting_metrics`, `audit_ref`) regardless of which tool path executed — this is what makes any response easy to inspect and compare, independent of query complexity.

---

## Dataset & Data Sources

**Primary dataset**: IBM "Transactions for Anti-Money Laundering (AML)" — HI-Small variant.
Source: [Kaggle — IBM Transactions for Anti-Money Laundering (AML)](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml), licensed CDLA-Sharing-1.0. A synthetic-but-research-grade simulation of a full banking network, with transactions labeled against known laundering typologies (fan-in, fan-out, cycles, and others).

**Subsampling methodology** (for repo size and iteration speed): every account with at least one confirmed illicit transaction is kept in full; a 5% random sample of accounts with zero illicit transactions is included alongside them, preserving the full transaction history of every included account. This is intentionally documented rather than left implicit, since the resulting evaluation numbers are only meaningful relative to this specific, disclosed sample — not the full unsampled dataset.

**Sanctions data**: the real, public US Treasury OFAC Specially Designated Nationals (SDN) list, used to power the sanctions/PEP screening tool.

**Customer/KYC metadata**: since the raw transaction dataset has no customer-level demographic fields, a lightweight metadata layer (segment, country, KYC risk rating) is generated and joined onto the real account IDs. Segment is inferred from entity-name text where available (e.g. "corporation" → Corporate); country and KYC risk rating are assigned via a deterministic hash of the account ID, not randomly — ensuring reproducibility.

**A small sample dataset is included directly in the repository** for anyone running the project without the full raw IBM files, generated via `scripts/generate_sample_data.py`.

---

## Tech Stack

**Backend**: Python 3.10, FastAPI + Uvicorn. A custom Python orchestrator performs intent-driven tool routing.

**Intent extraction & explanation**: Google Gemini (`gemini-2.0-flash`), called directly via REST, with a deterministic rule-based fallback parser that activates automatically if the LLM is unavailable or rate-limited — every response is schema-valid and fully explained either way.

**Machine learning**: a LightGBM classifier trained on the IBM dataset's ground-truth laundering labels, producing a probability score that is thresholded into risk tiers. A parallel rule-signal layer (structuring, rapid cash-out, sub-threshold frequency, round-number patterns) is computed for every transaction and surfaced as supporting evidence in every explanation, alongside the model's score.

**Data & storage**: DuckDB for in-process analytical queries against Parquet files; Parquet for all data at rest; SQLite for the audit log, session memory, and the trajectory ledger.

**Graph analysis**: NetworkX, for fan-in/fan-out/cycle detection across the transaction graph.

**Frontend**: React 19 + Vite + TypeScript, styled with Tailwind CSS. Framer Motion powers the interface's motion design; Recharts renders supporting metrics and charts; Lucide provides iconography.

**Audit & compliance**: a SHA-256 hash-chained, append-only SQLite audit log records every intent extraction, tool execution, and final response — independently retrievable and verifiable by reference ID, so every judgment the system makes is traceable after the fact.

---

## Setup

**Prerequisites**: Python 3.10, Node.js 18+.

```bash
# 1. Clone and enter the repository
git clone <repo_url>
cd Sentinel

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate        # Windows
# source venv/bin/activate     # macOS/Linux

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Set GEMINI_API_KEY in .env — the system runs correctly without it,
# falling back to a deterministic parser and explanation generator.

# 5. Build the data pipeline (in order)
python src/data/ingest_ibm.py
python src/features/rule_engine.py
python src/ml/anomaly_detector.py
python src/ml/customer_risk_aggregator.py

# — OR, to run on the bundled sample data instead of the full IBM dataset —
python scripts/generate_sample_data.py

# 6. Start the backend
python -m uvicorn src.api.app:app --port 8000

# 7. Start the frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Raw IBM dataset files (`HI-Small_Trans.csv`, `HI-Small_accounts.csv`, `HI-Small_Patterns.txt`) are not included in the repository due to size and must be downloaded separately from Kaggle and placed in `data/raw/` if you want to run the pipeline against the full dataset rather than the bundled sample.

---

## Usage — Example Queries

```
"Find structuring patterns in the last 30 days"
"Which customers made 10+ transactions under $10,000?"
"Is customer 8000EBD30 suspicious?"
"Which customer is most suspicious?"
"Show me the riskiest accounts"
"Show rapid cashout cases"
"Find layering patterns"
```

Each of these routes through a different, query-specific tool path — for example, the aggregation query above never invokes anomaly scoring at all, and a ranking-style question like "which customer is most suspicious" correctly triggers a full population scan rather than being mistaken for a single-entity lookup.

---

## Database Schema

Sentinel relies on a hybrid storage architecture spanning Parquet (for high-performance analytical queries via DuckDB) and SQLite (for stateful logging). 

### 1. Analytical Storage (Parquet / DuckDB)

**`transactions.parquet` & `ml_scored.parquet`** (Core transaction ledger)
- **Base Attributes**: `sender_id`, `receiver_id`, `txn_time`, `amount_paid`, `payment_format`, `is_laundering` (ground truth)
- **Engineered Features**: `rolling_txn_count_30d`, `rolling_amount_30d`, `velocity_30d`, `sub_threshold_count_30d`, `amount_zscore`, `velocity_zscore`, `txn_count_zscore`, `counterparty_zscore`, etc.
- **Rule Flags**: `is_structuring`, `is_rapid_cashout`, `is_round_number_suspicious`
- **ML Outputs** (in `ml_scored.parquet`): `lgbm_proba`, `risk_level`, `rule_score`

**`customers.parquet`** (KYC metadata)
- `account_id` (VARCHAR)
- `segment` (VARCHAR - e.g., 'Retail', 'Corporate', 'SME')
- `country` (VARCHAR - ISO country code)
- `kyc_risk_rating` (VARCHAR - 'Low', 'Medium', 'High')

**`ofac_sdn.parquet`** (Sanctions screening list)
- `uid` (VARCHAR - OFAC list ID)
- `name` (VARCHAR - Entity name)
- `type` (VARCHAR - Individual, Vessel, Entity)
- `aliases` (VARCHAR - Pipe-delimited string of known aliases)

### 2. Operational & Audit Storage (SQLite)

**`audit.db`** (Tamper-evident, hash-chained event logger)
- `audit_ref` (TEXT, Primary Key - e.g. 'AUD-A1B2C3D4')
- `session_id` (TEXT)
- `timestamp` (TEXT - ISO-8601 UTC)
- `event_type` (TEXT - e.g., 'query_dispatched', 'intent_extracted')
- `payload` (TEXT - JSON representation of the event)
- `prev_hash` (TEXT - SHA-256 hash of the preceding record)
- `curr_hash` (TEXT - SHA-256 hash of the current payload + prev_hash)

**`ledger.db`** (Trajectory Ledger / Accumulator)
- Stores accumulated queries against individual entities over time, tracking slow-burn risk signals that may not trigger an alert in a single isolation query.

---

## Data Sources Summary

| Source | Type | Access |
|---|---|---|
| IBM Transactions for Anti-Money Laundering (HI-Small) | Transaction & typology data | [Kaggle](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml), CDLA-Sharing-1.0 |
| US Treasury OFAC SDN List | Sanctions screening data | Public US Treasury data |
| Synthetic customer/KYC metadata | Enrichment layer | Generated in this repository, deterministic (not random), documented in `src/data/ingest_ibm.py` |
