import sys
from pathlib import Path
import duckdb
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ML_SCORED_PATH
from src.schemas import ToolFilters
from src.audit.logger import log_event

def run_anomaly_detection(filters: ToolFilters, session_id: str = "default_session") -> List[Dict[str, Any]]:
    """
    Anomaly Tool: Fetches top ML anomaly-scored items matching filters.
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
    if filters.pattern_hint == "structuring":
        where_clauses.append("is_structuring = 1")
    elif filters.pattern_hint == "rapid_cashout":
        where_clauses.append("is_rapid_cashout = 1")

    where_str = " AND ".join(where_clauses)
    query = f"""
    SELECT 
        sender_id, txn_time, receiver_id, amount_paid, 
        ml_anomaly_score, risk_level,
        is_structuring, is_rapid_cashout, is_round_number_suspicious,
        amount_zscore, velocity_zscore
    FROM read_parquet('{ML_SCORED_PATH}')
    WHERE {where_str}
    ORDER BY ml_anomaly_score DESC
    LIMIT 10;
    """
    
    results = conn.execute(query, params).df().to_dict(orient="records")
    conn.close()
    
    log_event("anomaly_tool_executed", {"filters": filters.model_dump(), "anomalies_found": len(results)}, session_id=session_id)
    return results
