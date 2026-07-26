import os
import sys
import uuid
from pathlib import Path
import duckdb
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.schemas import AgentResponse, ExecutionSummary, FlaggedItem

def run_custom_upload_analysis(file_path: str, session_id: str) -> AgentResponse:
    """
    Parses a user-uploaded CSV/Parquet file, applies a lightweight rule-based 
    anomaly scan, and returns the AgentResponse.
    """
    conn = duckdb.connect()
    
    # 1. Determine table name and create a view for easy querying
    table_name = "custom_data"
    if file_path.endswith(".csv"):
        conn.execute(f"CREATE VIEW {table_name} AS SELECT * FROM read_csv_auto('{file_path}')")
    else:
        conn.execute(f"CREATE VIEW {table_name} AS SELECT * FROM read_parquet('{file_path}')")
        
    # Check what columns we have
    cols_df = conn.execute(f"DESCRIBE {table_name}").df()
    columns = cols_df["column_name"].tolist()
    
    # We will build a lightweight flagged items list based on available columns
    flagged_items = []
    
    has_amount = "amount_paid" in columns or "amount" in columns
    amount_col = "amount_paid" if "amount_paid" in columns else ("amount" if "amount" in columns else None)
    sender_col = "sender_id" if "sender_id" in columns else ("sender" if "sender" in columns else ("account_id" if "account_id" in columns else None))
    
    if has_amount and sender_col:
        # Rule 1: High Amount Anomaly
        high_amount_query = f"""
            SELECT {sender_col} as entity_id, {amount_col} as amount, *
            FROM {table_name}
            WHERE {amount_col} > 15000
            LIMIT 10
        """
        try:
            high_amt_results = conn.execute(high_amount_query).df().to_dict(orient="records")
            for r in high_amt_results:
                flagged_items.append(FlaggedItem(
                    entity_type="customer",
                    entity_id=str(r["entity_id"]),
                    risk_level="high",
                    risk_score=0.95,
                    detected_pattern="unspecified",
                    explanation=f"Custom Upload Analysis: Flagged for high transaction amount (${r['amount']:,.2f}).",
                    evidence=r,
                    recommended_action="review",
                    sar_draft=f"Draft SAR for custom uploaded entity {r['entity_id']} due to high transaction amount."
                ))
        except Exception as e:
            pass

    # Basic stats for EDA panel
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    except:
        count = 0

    conn.close()
    
    # Construct Execution Summary
    summary = ExecutionSummary(
        query="Run custom scan on uploaded dataset",
        detected_intent="broad_scan",
        filters_detected={"custom_file": file_path},
        tools_invoked=["custom_upload_parser", "rule_engine"],
        tools_skipped=["lightgbm_inference", "graph_analysis"],
        reasoning=f"Analyzed custom uploaded dataset with {count} records. Evaluated against basic fallback heuristics since custom features were not guaranteed."
    )
    
    return AgentResponse(
        execution_summary=summary,
        flagged_items=flagged_items,
        supporting_metrics={
            "custom_scan": True,
            "total_records": count,
            "columns_detected": columns
        },
        audit_ref=f"custom-audit-{session_id}"
    )
