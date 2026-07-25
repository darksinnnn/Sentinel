import sys
from pathlib import Path
import duckdb
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import CUSTOMER_RISK_PATH, ML_SCORED_PATH
from src.schemas import ToolFilters, FlaggedItem
from src.audit.logger import log_event

def run_entity_lookup(filters: ToolFilters, session_id: str = "default_session") -> List[FlaggedItem]:
    """
    Single-Entity Lookup Tool: Performs direct customer drill-down from customer_risk.parquet & ml_scored.parquet.
    Skips broad ML scoring.
    """
    if not filters.customer_id:
        return []
        
    conn = duckdb.connect()
    
    # Query customer_risk summary
    cust_query = f"SELECT * FROM read_parquet('{CUSTOMER_RISK_PATH}') WHERE customer_id = ?"
    cust_df = conn.execute(cust_query, [filters.customer_id]).df()
    
    if cust_df.empty:
        conn.close()
        return []
        
    c_row = cust_df.iloc[0]
    
    # Query top transactions for this customer
    txn_query = f"""
    SELECT amount_paid, ml_anomaly_score, risk_level, is_structuring, is_rapid_cashout
    FROM read_parquet('{ML_SCORED_PATH}')
    WHERE sender_id = ?
    ORDER BY ml_anomaly_score DESC
    LIMIT 5;
    """
    txns = conn.execute(txn_query, [filters.customer_id]).df().to_dict(orient="records")
    conn.close()
    
    risk_lvl = c_row.get("customer_risk_level", "low")
    action = "report" if risk_lvl == "high" else ("review" if risk_lvl == "medium" else "monitor")
    
    pattern = "unspecified"
    if c_row.get("structuring_flags_count", 0) > 0:
        pattern = "structuring"
    elif c_row.get("rapid_cashout_flags_count", 0) > 0:
        pattern = "rapid_cashout"
        
    item = FlaggedItem(
        entity_type="customer",
        entity_id=str(filters.customer_id),
        risk_level=risk_lvl,
        risk_score=float(c_row.get("max_ml_score", 0.0)),
        detected_pattern=pattern,
        explanation=f"Single entity lookup for customer {filters.customer_id}. High risk transactions: {c_row.get('high_risk_txns')}, Total volume: ${c_row.get('total_amount_sent'):,.2f}.",
        evidence={
            "segment": c_row.get("segment"),
            "country": c_row.get("country"),
            "kyc_risk_rating": c_row.get("kyc_risk_rating"),
            "total_txns": c_row.get("total_txns"),
            "high_risk_txns": c_row.get("high_risk_txns"),
            "recent_txns_sample": txns
        },
        recommended_action=action
    )
    
    log_event("entity_lookup_executed", {"customer_id": filters.customer_id, "risk_level": risk_lvl}, session_id=session_id)
    return [item]
