import sys
from pathlib import Path
import duckdb
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ML_SCORED_PATH, CUSTOMERS_PATH
from src.schemas import ToolFilters, FlaggedItem
from src.audit.logger import log_event

def run_aggregation_query(filters: ToolFilters, session_id: str = "default_session") -> List[FlaggedItem]:
    """
    Aggregation/Rule Tool: Directly aggregates transaction data to satisfy hard-filter queries
    (e.g., "Which customers made 10+ transactions under $20k?").
    SKIPS ML anomaly scoring entirely per Architecture §5.2.
    """
    conn = duckdb.connect()
    
    limit_amount = filters.amount_threshold if filters.amount_threshold is not None else 10000.0
    min_count = filters.count_threshold if filters.count_threshold is not None else 10
    
    query = f"""
    SELECT 
        m.sender_id AS customer_id,
        COUNT(*) AS sub_threshold_txns,
        SUM(m.amount_paid) AS total_amount,
        MAX(m.typology) AS typology,
        ANY_VALUE(c.entity_name) AS entity_name,
        ANY_VALUE(c.bank_name) AS bank_name
    FROM read_parquet('{ML_SCORED_PATH}') m
    LEFT JOIN read_parquet('{CUSTOMERS_PATH}') c ON m.sender_id = c.customer_id
    WHERE m.amount_paid < ?
    GROUP BY m.sender_id
    HAVING COUNT(*) >= ?
    ORDER BY sub_threshold_txns DESC
    LIMIT 10;
    """
    
    df = conn.execute(query, [limit_amount, min_count]).df()
    conn.close()
    
    flagged_items = []
    for _, row in df.iterrows():
        item = FlaggedItem(
            entity_type="customer",
            entity_id=str(row["customer_id"]),
            risk_level="medium",
            risk_score=0.75,
            detected_pattern=str(row.get("typology")) if row.get("typology") else "sub_threshold_structuring_count",
            explanation=f"Customer executed {int(row['sub_threshold_txns']):,} transactions under ${limit_amount:,.2f} with total volume of ${float(row['total_amount']):,.2f} (Direct Rule Aggregation - ML Skipped).",
            evidence={
                "sub_threshold_txns": int(row["sub_threshold_txns"]),
                "total_amount": float(row["total_amount"]),
                "threshold_filter": limit_amount,
                "min_count_filter": min_count,
                "entity_name": row.get("entity_name"),
                "bank_name": row.get("bank_name")
            },
            recommended_action="review"
        )
        flagged_items.append(item)
        
    log_event("aggregation_tool_executed", {"filters": filters.model_dump(), "count": len(flagged_items)}, session_id=session_id)
    return flagged_items

