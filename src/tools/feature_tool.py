import sys
from pathlib import Path
import duckdb
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ML_SCORED_PATH
from src.schemas import ToolFilters
from src.audit.logger import log_event

def run_feature_engineering_query(filters: ToolFilters, session_id: str = "default_session") -> List[Dict[str, Any]]:
    """
    Feature Tool: Queries transaction-level features scoped to current filters.
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

    where_str = " AND ".join(where_clauses)
    query = f"""
    SELECT 
        sender_id, txn_time, amount_paid, risk_level, ml_anomaly_score,
        is_structuring, is_rapid_cashout, is_round_number_suspicious,
        amount_zscore, velocity_zscore
    FROM read_parquet('{ML_SCORED_PATH}')
    WHERE {where_str}
    ORDER BY ml_anomaly_score DESC
    LIMIT 20;
    """
    
    df = conn.execute(query, params).df()
    results = df.to_dict(orient="records")
    conn.close()
    
    log_event("feature_tool_executed", {"filters": filters.model_dump(), "result_count": len(results)}, session_id=session_id)
    return results
