# Phase 1 Walkthrough: Sentinel Foundation & Data Layer

Phase 1 has been fully implemented, providing a robust data and feature foundation for Phase 2's AI orchestrator.

## 1. Environment & Scaffolding
- Built the `venv` and installed all required packages via `requirements.txt`.
- Created the project directory structure (`data/raw`, `src/data`, `src/features`, etc.).
- Set up a `.env` template for the OpenRouter API Key.

## 2. Project Tracker 
- Initialized **[Sentinel_Project_Tracker.md](file:///d:/Project/Sentinel/Sentinel_Project_Tracker.md)**.
- Seeded it with the **Output Contract** (Schema §5.11) to ensure the AI Orchestrator built in Phase 2 can rely on standardized JSON responses from the tools built in Phase 1.

## 3. Data Ingestion
All raw data has been successfully ingested and optimized into `.parquet` files.
- **[ingest_ofac.py](file:///d:/Project/Sentinel/src/data/ingest_ofac.py)**: Downloaded and parsed the live US Treasury XML feed, extracting **19,254 actual sanctions list entities** for our Sanctions tool to screen against.
- **[ingest_ibm.py](file:///d:/Project/Sentinel/src/data/ingest_ibm.py)**: 
  - Stratified subsampled the 5M+ row `HI-Small_Trans.csv` (100% of illicit transactions, 5% of normal transactions) directly into Parquet using DuckDB for speed.
  - Generated realistic synthetic KYC metadata (`kyc_risk_rating`, `country`, `segment`) for **160,110 unique accounts**.

## 4. Rule Engine & Baselining
The core logic for AML feature engineering has been built in DuckDB SQL.
- **[rule_engine.py](file:///d:/Project/Sentinel/src/features/rule_engine.py)**:
  - Connects to DuckDB and loads Parquet files natively as views.
  - Calculates a 30-day rolling window for all senders, computing: `velocity_30d`, `rolling_amount_30d`, `rolling_txn_count_30d`.
  - Calculates specific typology hint features such as `sub_threshold_count_30d` (structuring hint: txns between $9,000 and $9,999) and `round_number_count_30d` (txns ending in '00').
  - **Peer-group Baselining**: Rather than evaluating all accounts globally, we grouped them by `segment` and `age_tier` to compute the average and standard deviation of their velocity. (This allows Phase 2's ML anomaly detector to score an account against its peers rather than a global average).

> [!TIP]
> **Handoff for Phase 2**
> The codebase is fully prepared for the second developer (or AI) to begin Phase 2. They should refer to the [Sentinel_Project_Tracker.md](file:///d:/Project/Sentinel/Sentinel_Project_Tracker.md) to review the Output Contract before building the LLM intent extraction and LangGraph orchestrator!
