import sys
from pathlib import Path
import duckdb
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ML_SCORED_PATH, CUSTOMERS_PATH
from src.schemas import ToolFilters
from src.audit.logger import log_event

def run_eda(filters: ToolFilters, session_id: str = "default_session") -> Dict[str, Any]:
    """
    EDA Tool: Generates dataset profiling summary metrics.
    Only executed for broad_scan intent queries.
    """
    conn = duckdb.connect()
    
    total_txns = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{ML_SCORED_PATH}')").fetchone()[0]
    risk_summary = conn.execute(f"SELECT risk_level, COUNT(*) FROM read_parquet('{ML_SCORED_PATH}') GROUP BY 1").fetchall()
    segment_summary = conn.execute(f"SELECT segment, COUNT(*) FROM read_parquet('{CUSTOMERS_PATH}') GROUP BY 1").fetchall()
    
    metrics = {
        "total_transactions": total_txns,
        "risk_distribution": dict(risk_summary),
        "customer_segments": dict(segment_summary)
    }
    
    conn.close()
    log_event("eda_tool_executed", {"filters": filters.model_dump(), "metrics": metrics}, session_id=session_id)
    return metrics
