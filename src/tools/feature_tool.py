import sys
from pathlib import Path
import duckdb
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ML_SCORED_PATH
from src.schemas import ToolFilters
from src.audit.logger import log_event

_DATE_RANGE_DAYS = {"7d": 7, "30d": 30, "60d": 60, "90d": 90}


def _date_clause(date_range: Optional[str], table_path: str) -> Optional[str]:
    if not date_range:
        return None
    days = _DATE_RANGE_DAYS.get(str(date_range).lower())
    if not days:
        return None
    return (
        f"CAST(txn_time AS DATE) >= "
        f"(SELECT CAST(MAX(txn_time) AS DATE) - INTERVAL '{days}' DAY "
        f"FROM read_parquet('{table_path}'))"
    )


def run_feature_engineering_query(filters: ToolFilters, session_id: str = "default_session") -> List[Dict[str, Any]]:
    """
    Feature Tool: Queries transaction-level features scoped to current filters.
    Applies date_range, country, segment, and pattern_hint scoping.
    """
    conn = duckdb.connect()
    
    where_clauses = ["1=1"]
    params = []
    
    if filters.country:
        where_clauses.append("country = ?")
        params.append(filters.country)
    if filters.segment:
        where_clauses.append("segment = ?")
        params.append(filters.segment)
    if filters.pattern_hint == "structuring":
        where_clauses.append("is_structuring = 1")
    elif filters.pattern_hint == "rapid_cashout":
        where_clauses.append("is_rapid_cashout = 1")
    elif filters.pattern_hint == "smurfing":
        where_clauses.append("sub_threshold_count_30d >= 3")
    elif filters.pattern_hint == "layering":
        where_clauses.append("(unique_counterparties_30d >= 5 OR velocity_zscore > 2.0)")

    date_frag = _date_clause(filters.date_range, ML_SCORED_PATH)
    if date_frag:
        where_clauses.append(date_frag)

    where_str = " AND ".join(where_clauses)
    query = f"""
    SELECT 
        sender_id, txn_time, amount_paid, risk_level, ml_anomaly_score,
        is_structuring, is_rapid_cashout, is_round_number_suspicious,
        amount_zscore, velocity_zscore,
        sub_threshold_count_30d, unique_counterparties_30d,
        velocity_30d, in_out_ratio_30d
    FROM read_parquet('{ML_SCORED_PATH}')
    WHERE {where_str}
    ORDER BY ml_anomaly_score DESC
    LIMIT 20;
    """
    
    df = conn.execute(query, params).df()
    results = df.to_dict(orient="records")
    conn.close()
    
    log_event("feature_tool_executed", {
        "filters": filters.model_dump(), 
        "date_range_applied": filters.date_range or "none",
        "result_count": len(results)
    }, session_id=session_id)
    return results
