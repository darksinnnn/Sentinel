import sys
from pathlib import Path
import os
import duckdb
import logging

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import (
    ML_SCORED_PATH,
    CUSTOMERS_PATH,
    CUSTOMER_RISK_PATH,
    HIGH_ANOMALY_THRESHOLD,
    MEDIUM_ANOMALY_THRESHOLD
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def aggregate_customer_risk():
    """
    Rolls up transaction-level scores from ml_scored.parquet to customer-level metrics
    and risk classifications in customer_risk.parquet.
    """
    if not os.path.exists(ML_SCORED_PATH):
        logger.error(f"Input file not found: {ML_SCORED_PATH}")
        return

    logger.info("Initializing DuckDB for customer risk rollup...")
    conn = duckdb.connect()

    query = f"""
    CREATE OR REPLACE TEMP TABLE customer_agg AS
    SELECT 
        sender_id AS customer_id,
        COUNT(*) AS total_txns,
        ROUND(SUM(amount_paid), 2) AS total_amount_sent,
        ROUND(MAX(ml_anomaly_score), 4) AS max_ml_score,
        SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk_txns,
        SUM(CASE WHEN risk_level = 'medium' THEN 1 ELSE 0 END) AS medium_risk_txns,
        SUM(CASE WHEN risk_level = 'low' THEN 1 ELSE 0 END) AS low_risk_txns,
        SUM(is_structuring) AS structuring_flags_count,
        SUM(is_rapid_cashout) AS rapid_cashout_flags_count,
        SUM(is_round_number_suspicious) AS round_number_flags_count
    FROM read_parquet('{ML_SCORED_PATH}')
    GROUP BY sender_id;
    """
    conn.execute(query)

    logger.info("Joining customer metadata and assigning customer-level risk classification...")
    classified_query = f"""
    COPY (
        SELECT 
            c.customer_id,
            meta.segment,
            meta.country,
            meta.kyc_risk_rating,
            meta.account_age_days,
            c.total_txns,
            c.total_amount_sent,
            c.max_ml_score,
            c.high_risk_txns,
            c.medium_risk_txns,
            c.low_risk_txns,
            c.structuring_flags_count,
            c.rapid_cashout_flags_count,
            c.round_number_flags_count,
            CASE 
                WHEN c.high_risk_txns >= 1 OR c.max_ml_score >= {HIGH_ANOMALY_THRESHOLD} THEN 'high'
                WHEN c.medium_risk_txns >= 1 OR c.max_ml_score >= {MEDIUM_ANOMALY_THRESHOLD} THEN 'medium'
                ELSE 'low'
            END AS customer_risk_level
        FROM customer_agg c
        LEFT JOIN read_parquet('{CUSTOMERS_PATH}') meta ON c.customer_id = meta.customer_id
    ) TO '{CUSTOMER_RISK_PATH}' (FORMAT PARQUET);
    """
    os.makedirs(os.path.dirname(CUSTOMER_RISK_PATH), exist_ok=True)
    conn.execute(classified_query)

    # Verification stats
    stats = conn.execute(f"SELECT customer_risk_level, COUNT(*) FROM read_parquet('{CUSTOMER_RISK_PATH}') GROUP BY 1").fetchall()
    logger.info(f"Customer Risk Rollup complete! Saved to {CUSTOMER_RISK_PATH}")
    logger.info(f"Customer Risk Distribution: {stats}")
    conn.close()

if __name__ == "__main__":
    aggregate_customer_risk()
