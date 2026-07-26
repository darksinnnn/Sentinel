import sys
from pathlib import Path
import duckdb
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ML_SCORED_PATH, CUSTOMERS_PATH
from src.schemas import ToolFilters
from src.audit.logger import log_event

# ── date_range -> DuckDB interval map ────────────────────────────────────────
_DATE_RANGE_DAYS = {"7d": 7, "30d": 30, "60d": 60, "90d": 90}


def _date_clause(date_range: Optional[str]) -> Optional[str]:
    """Returns a WHERE fragment that filters txn_time to the last N days,
    anchored to the maximum txn_time in the table (dataset may not be live).
    Returns None if date_range is empty or unrecognised."""
    if not date_range:
        return None
    days = _DATE_RANGE_DAYS.get(str(date_range).lower())
    if not days:
        return None
    return (
        f"CAST(txn_time AS DATE) >= "
        f"(SELECT CAST(MAX(txn_time) AS DATE) - INTERVAL '{days}' DAY "
        f"FROM read_parquet('{ML_SCORED_PATH}'))"
    )


def run_anomaly_detection(filters: ToolFilters, session_id: str = "default_session") -> List[Dict[str, Any]]:
    """
    Anomaly Tool: Fetches top ML anomaly-scored items matching filters.
    Applies: country, segment, pattern_hint, AND date_range (30d/7d/90d) filters.
    """
    conn = duckdb.connect()

    where_clauses = ["risk_level IN ('high', 'medium')"]
    params = []

    if filters.country:
        where_clauses.append("country = ?")
        params.append(filters.country)
    if filters.segment:
        where_clauses.append("segment = ?")
        params.append(filters.segment)

    # Pattern-specific filters — maps AML typologies to feature flags
    if filters.pattern_hint == "structuring":
        where_clauses.append("is_structuring = 1")
    elif filters.pattern_hint == "rapid_cashout":
        where_clauses.append("is_rapid_cashout = 1")
    elif filters.pattern_hint == "smurfing":
        # Smurfing = multiple sub-threshold transactions -> high sub_threshold_count
        where_clauses.append("sub_threshold_count_30d >= 3")
    elif filters.pattern_hint == "layering":
        # Layering = high counterparty diversity + high velocity
        where_clauses.append("(unique_counterparties_30d >= 5 OR velocity_zscore > 2.0)")

    # Date range filter — anchored to dataset max date (handles non-live data correctly)
    date_frag = _date_clause(filters.date_range)
    if date_frag:
        where_clauses.append(date_frag)

    where_str = " AND ".join(where_clauses)

    # DISTINCT ON (sender_id): take the highest-scoring row per customer,
    # then rank those deduplicated customers and return the top 10.
    query = f"""
    SELECT
        deduped.sender_id, deduped.txn_time, deduped.receiver_id, deduped.amount_paid,
        deduped.ml_anomaly_score, deduped.risk_level,
        deduped.is_structuring, deduped.is_rapid_cashout, deduped.is_round_number_suspicious, deduped.typology,
        deduped.amount_zscore, deduped.velocity_zscore,
        deduped.sub_threshold_count_30d, deduped.unique_counterparties_30d, deduped.velocity_30d,
        c.entity_name, c.bank_name
    FROM (
        SELECT DISTINCT ON (sender_id)
            sender_id, txn_time, receiver_id, amount_paid,
            ml_anomaly_score, risk_level,
            is_structuring, is_rapid_cashout, is_round_number_suspicious, typology,
            amount_zscore, velocity_zscore,
            sub_threshold_count_30d, unique_counterparties_30d, velocity_30d
        FROM read_parquet('{ML_SCORED_PATH}')
        WHERE {where_str}
        ORDER BY sender_id, ml_anomaly_score DESC
    ) deduped
    LEFT JOIN read_parquet('{CUSTOMERS_PATH}') c ON deduped.sender_id = c.customer_id
    ORDER BY deduped.ml_anomaly_score DESC
    LIMIT 10;
    """

    results = conn.execute(query, params).df().to_dict(orient="records")

    # Fetch chart_data (30-day time series of txns) for each flagged entity
    if results:
        sender_ids = tuple(r["sender_id"] for r in results)
        placeholders = ", ".join(f"'{sid}'" for sid in sender_ids)
        chart_query = f"""
            SELECT sender_id, CAST(txn_time AS DATE) as txn_date, SUM(amount_paid) as daily_amount, COUNT(*) as daily_count
            FROM read_parquet('{ML_SCORED_PATH}')
            WHERE sender_id IN ({placeholders})
            AND CAST(txn_time AS DATE) >= (SELECT CAST(MAX(txn_time) AS DATE) - INTERVAL '30' DAY FROM read_parquet('{ML_SCORED_PATH}'))
            GROUP BY sender_id, CAST(txn_time AS DATE)
            ORDER BY txn_date ASC
        """
        chart_df = conn.execute(chart_query).df()
        
        for r in results:
            # format date as string
            entity_chart_df = chart_df[chart_df["sender_id"] == r["sender_id"]].copy()
            if not entity_chart_df.empty:
                entity_chart_df["txn_date"] = entity_chart_df["txn_date"].astype(str)
                r["chart_data"] = entity_chart_df[["txn_date", "daily_amount", "daily_count"]].to_dict(orient="records")
            else:
                r["chart_data"] = []

    conn.close()

    log_event("anomaly_tool_executed", {
        "filters": filters.model_dump(),
        "date_range_applied": filters.date_range or "none",
        "pattern_filter": filters.pattern_hint,
        "anomalies_found": len(results)
    }, session_id=session_id)
    return results
