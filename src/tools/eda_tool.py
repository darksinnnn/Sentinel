"""
EDA (Exploratory Data Analysis) Tool
====================================
Architecture ref: Sentinel_Architecture.md §5.3

Provides comprehensive dataset profiling & baseline statistical summaries:
  - Total volume & unique customer counts
  - Temporal bounds (min/max transaction date)
  - Risk classification breakdown
  - Customer segment distribution
  - Amount statistics (mean, median, stddev, percentiles p25/p75/p95/p99)
  - Daily transaction volume & monetary trends (for Plotly visualization)
  - Typology pattern prevalence rates (structuring, rapid cashout, round numbers)
  - Data quality & missing value audit
"""

import sys
import logging
from pathlib import Path
import duckdb
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ML_SCORED_PATH, CUSTOMERS_PATH
from src.schemas import ToolFilters
from src.audit.logger import log_event

logger = logging.getLogger(__name__)


def run_eda(filters: ToolFilters, session_id: str = "default_session") -> Dict[str, Any]:
    """
    EDA Tool: Generates comprehensive dataset profiling summary metrics.
    Supports scoping by country and segment if provided in filters.
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

    where_str = " AND ".join(where_clauses)

    # 1. Total volume, unique customers, and date bounds
    overview_query = f"""
        SELECT 
            COUNT(*) AS total_transactions,
            COUNT(DISTINCT sender_id) AS unique_senders,
            COUNT(DISTINCT receiver_id) AS unique_receivers,
            MIN(txn_time) AS min_txn_time,
            MAX(txn_time) AS max_txn_time
        FROM read_parquet('{ML_SCORED_PATH}')
        WHERE {where_str}
    """
    ov = conn.execute(overview_query, params).df().to_dict(orient="records")[0]

    # 2. Risk distribution
    risk_query = f"""
        SELECT risk_level, COUNT(*) AS count
        FROM read_parquet('{ML_SCORED_PATH}')
        WHERE {where_str}
        GROUP BY risk_level
        ORDER BY count DESC
    """
    risk_dist = dict(conn.execute(risk_query, params).fetchall())

    # 3. Customer segment summary
    segment_query = f"""
        SELECT segment, COUNT(*) AS count
        FROM read_parquet('{CUSTOMERS_PATH}')
        GROUP BY segment
        ORDER BY count DESC
    """
    segment_dist = dict(conn.execute(segment_query).fetchall())

    # 4. Amount summary & percentiles
    amt_query = f"""
        SELECT
            MIN(amount_paid) AS min_amount,
            MAX(amount_paid) AS max_amount,
            AVG(amount_paid) AS mean_amount,
            MEDIAN(amount_paid) AS median_amount,
            STDDEV_SAMP(amount_paid) AS std_amount,
            QUANTILE_CONT(amount_paid, 0.25) AS p25_amount,
            QUANTILE_CONT(amount_paid, 0.75) AS p75_amount,
            QUANTILE_CONT(amount_paid, 0.95) AS p95_amount,
            QUANTILE_CONT(amount_paid, 0.99) AS p99_amount
        FROM read_parquet('{ML_SCORED_PATH}')
        WHERE {where_str}
    """
    amt_stats_raw = conn.execute(amt_query, params).df().to_dict(orient="records")[0]
    amt_stats = {k: round(float(v), 2) if v is not None else 0.0 for k, v in amt_stats_raw.items()}

    # 5. Typology pattern prevalence
    pattern_query = f"""
        SELECT
            SUM(is_structuring) AS structuring_count,
            SUM(is_rapid_cashout) AS rapid_cashout_count,
            SUM(is_round_number_suspicious) AS round_number_count,
            AVG(is_structuring) AS structuring_rate,
            AVG(is_rapid_cashout) AS rapid_cashout_rate,
            AVG(is_round_number_suspicious) AS round_number_rate
        FROM read_parquet('{ML_SCORED_PATH}')
        WHERE {where_str}
    """
    pat_raw = conn.execute(pattern_query, params).df().to_dict(orient="records")[0]
    pattern_prevalence = {
        "structuring_count": int(pat_raw["structuring_count"] or 0),
        "rapid_cashout_count": int(pat_raw["rapid_cashout_count"] or 0),
        "round_number_count": int(pat_raw["round_number_count"] or 0),
        "structuring_rate_pct": round(float(pat_raw["structuring_rate"] or 0) * 100, 4),
        "rapid_cashout_rate_pct": round(float(pat_raw["rapid_cashout_rate"] or 0) * 100, 4),
        "round_number_rate_pct": round(float(pat_raw["round_number_rate"] or 0) * 100, 4),
    }

    # 6. Daily volume & monetary trend (for UI Plotly charts)
    daily_query = f"""
        SELECT 
            CAST(txn_time AS DATE) AS date_val,
            COUNT(*) AS txn_count,
            ROUND(SUM(amount_paid), 2) AS total_amount,
            SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk_count
        FROM read_parquet('{ML_SCORED_PATH}')
        WHERE {where_str}
        GROUP BY 1
        ORDER BY 1 ASC
    """
    daily_df = conn.execute(daily_query, params).df()
    daily_trend = [
        {
            "date": str(row["date_val"]),
            "txn_count": int(row["txn_count"]),
            "total_amount": float(row["total_amount"]),
            "high_risk_count": int(row["high_risk_count"]),
        }
        for _, row in daily_df.iterrows()
    ]

    # 7. Missing value / data quality audit
    null_query = f"""
        SELECT
            SUM(CASE WHEN amount_paid IS NULL THEN 1 ELSE 0 END) AS null_amount,
            SUM(CASE WHEN sender_id IS NULL THEN 1 ELSE 0 END) AS null_sender,
            SUM(CASE WHEN receiver_id IS NULL THEN 1 ELSE 0 END) AS null_receiver,
            SUM(CASE WHEN txn_time IS NULL THEN 1 ELSE 0 END) AS null_txn_time
        FROM read_parquet('{ML_SCORED_PATH}')
        WHERE {where_str}
    """
    null_audit = dict(conn.execute(null_query, params).df().to_dict(orient="records")[0])

    conn.close()

    metrics = {
        "overview": {
            "total_transactions": int(ov["total_transactions"]),
            "unique_senders": int(ov["unique_senders"]),
            "unique_receivers": int(ov["unique_receivers"]),
            "min_txn_time": str(ov["min_txn_time"]),
            "max_txn_time": str(ov["max_txn_time"]),
        },
        "risk_distribution": risk_dist,
        "customer_segments": segment_dist,
        "amount_statistics": amt_stats,
        "pattern_prevalence": pattern_prevalence,
        "daily_trend": daily_trend,
        "data_quality_null_counts": null_audit,
    }

    log_event("eda_tool_executed", {"filters": filters.model_dump(), "metrics_summary": metrics["overview"]}, session_id=session_id)
    return metrics
