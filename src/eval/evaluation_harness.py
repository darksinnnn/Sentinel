import sys
import os
import json
import logging
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import (
    ML_SCORED_PATH,
    CUSTOMER_RISK_PATH,
    CUSTOMERS_PATH,
    ML_FEATURES
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REPORT_JSON_PATH = "data/processed/evaluation_report.json"

def calculate_metrics(y_true: pd.Series, y_pred: pd.Series) -> Dict[str, Any]:
    """Calculates confusion matrix, precision, recall, F1, FPR, alert volume, alert rate."""
    total = len(y_true)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())

    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    alert_volume = int(tp + fp)
    alert_rate_pct = float((alert_volume / total) * 100) if total > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "fpr": round(fpr, 6),
        "alert_volume": alert_volume,
        "alert_rate_pct": round(alert_rate_pct, 4)
    }

def run_evaluation():
    logger.info("=== STEP A: LEAKAGE CHECK ===")
    ground_truth_cols = ["is_laundering", "Is Laundering", "label", "target"]
    leaked = [col for col in ML_FEATURES if col.lower() in [g.lower() for g in ground_truth_cols]]
    
    passed_leakage = len(leaked) == 0
    leakage_notes = "PASS: Ground truth label column is not present in ML_FEATURES training matrix." if passed_leakage else f"FAIL: Leaked columns detected in ML_FEATURES: {leaked}"
    
    logger.info(f"Leakage Check: {'PASS' if passed_leakage else 'FAIL'}")
    if not passed_leakage:
        raise ValueError(f"Data leakage error: {leakage_notes}")

    logger.info("\n=== STEP G: DATASET SANITY CHECK & LOADING DATA ===")
    conn = duckdb.connect()
    
    # Load transactions ML scored
    df_tx = conn.execute(f"""
        SELECT 
            sender_id,
            receiver_id,
            txn_time,
            amount_paid,
            is_laundering,
            risk_level,
            ml_anomaly_score,
            rolling_txn_count_30d,
            sub_threshold_count_30d,
            is_structuring,
            is_rapid_cashout,
            is_round_number_suspicious,
            amount_zscore,
            velocity_zscore,
            txn_count_zscore,
            counterparty_zscore
        FROM read_parquet('{ML_SCORED_PATH}')
    """).df()

    total_tx = len(df_tx)
    total_pos_gt = int((df_tx['is_laundering'] == 1).sum())
    pos_rate_pct = float((total_pos_gt / total_tx) * 100)

    total_customers = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{CUSTOMERS_PATH}')").fetchone()[0]
    customers_with_risk = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{CUSTOMER_RISK_PATH}')").fetchone()[0]

    logger.info(f"Total Transactions: {total_tx:,}")
    logger.info(f"Positive Ground Truth: {total_pos_gt:,} ({pos_rate_pct:.4f}%)")
    logger.info(f"Total Customers in Customers.parquet: {total_customers:,}")
    logger.info(f"Customers with Risk Profile in Customer_Risk.parquet: {customers_with_risk:,}")

    logger.info("\n=== STEP B & C: TRANSACTION-LEVEL EVALUATION ===")
    # Define Naive Baseline
    # amount > $10,000 OR ($9,000-$9,999 AND rolling_txn_count_30d >= 3)
    df_tx['naive_pred'] = (
        (df_tx['amount_paid'] > 10000) | 
        ((df_tx['amount_paid'] >= 9000) & (df_tx['amount_paid'] <= 9999) & (df_tx['rolling_txn_count_30d'] >= 3))
    ).astype(int)

    df_tx['sentinel_high_pred'] = (df_tx['risk_level'] == 'high').astype(int)
    df_tx['sentinel_med_plus_pred'] = (df_tx['risk_level'].isin(['high', 'medium'])).astype(int)

    tx_naive_metrics = calculate_metrics(df_tx['is_laundering'], df_tx['naive_pred'])
    tx_high_metrics = calculate_metrics(df_tx['is_laundering'], df_tx['sentinel_high_pred'])
    tx_med_metrics = calculate_metrics(df_tx['is_laundering'], df_tx['sentinel_med_plus_pred'])

    logger.info("\n=== STEP E: CUSTOMER-LEVEL EVALUATION ===")
    df_cust_risk = conn.execute(f"SELECT * FROM read_parquet('{CUSTOMER_RISK_PATH}')").df()
    
    # Ground truth per customer: 1 if customer has ANY is_laundering == 1 txn
    cust_gt = conn.execute(f"""
        SELECT 
            sender_id AS customer_id,
            MAX(is_laundering) AS cust_is_laundering,
            MAX(CASE WHEN (amount_paid > 10000 OR (amount_paid >= 9000 AND amount_paid <= 9999 AND rolling_txn_count_30d >= 3)) THEN 1 ELSE 0 END) AS cust_naive_pred
        FROM read_parquet('{ML_SCORED_PATH}')
        GROUP BY sender_id
    """).df()

    df_cust_eval = pd.merge(df_cust_risk, cust_gt, on='customer_id', how='left').fillna(0)

    df_cust_eval['sentinel_cust_high_pred'] = (df_cust_eval['customer_risk_level'] == 'high').astype(int)
    df_cust_eval['sentinel_cust_med_plus_pred'] = (df_cust_eval['customer_risk_level'].isin(['high', 'medium'])).astype(int)

    cust_naive_metrics = calculate_metrics(df_cust_eval['cust_is_laundering'], df_cust_eval['cust_naive_pred'])
    cust_high_metrics = calculate_metrics(df_cust_eval['cust_is_laundering'], df_cust_eval['sentinel_cust_high_pred'])
    cust_med_metrics = calculate_metrics(df_cust_eval['cust_is_laundering'], df_cust_eval['sentinel_cust_med_plus_pred'])

    conn.close()

    # Step Alert Reduction
    high_vs_naive_pct = float((tx_naive_metrics['alert_volume'] - tx_high_metrics['alert_volume']) / tx_naive_metrics['alert_volume'] * 100) if tx_naive_metrics['alert_volume'] > 0 else 0.0
    med_vs_naive_pct = float((tx_naive_metrics['alert_volume'] - tx_med_metrics['alert_volume']) / tx_naive_metrics['alert_volume'] * 100) if tx_naive_metrics['alert_volume'] > 0 else 0.0

    logger.info("\n=== STEP F: ERROR ANALYSIS SAMPLES ===")
    # Top 15 False Negatives (laundering txns missed by high tier)
    fn_df = df_tx[(df_tx['is_laundering'] == 1) & (df_tx['sentinel_high_pred'] == 0)].sort_values(by='ml_anomaly_score', ascending=False).head(15)
    
    fn_samples = []
    for idx, r in fn_df.iterrows():
        pattern = "Fan-In/Out" if r["is_rapid_cashout"] else ("Structuring" if r["is_structuring"] else "Unknown AML Typology")
        fn_samples.append({
            "transaction_id": f"{r['sender_id']}_{r['txn_time']}",
            "amount": float(r["amount_paid"]),
            "ml_anomaly_score": float(r["ml_anomaly_score"]),
            "ground_truth_pattern": pattern,
            "features": {
                "amount_zscore": float(r["amount_zscore"]),
                "velocity_zscore": float(r["velocity_zscore"]),
                "is_structuring": int(r["is_structuring"]),
                "is_rapid_cashout": int(r["is_rapid_cashout"])
            }
        })

    # Top 15 False Positives at HIGH tier
    fp_df = df_tx[(df_tx['is_laundering'] == 0) & (df_tx['sentinel_high_pred'] == 1)].sort_values(by='ml_anomaly_score', ascending=False).head(15)
    
    fp_samples = []
    for idx, r in fp_df.iterrows():
        fp_samples.append({
            "transaction_id": f"{r['sender_id']}_{r['txn_time']}",
            "amount": float(r["amount_paid"]),
            "ml_anomaly_score": float(r["ml_anomaly_score"]),
            "features": {
                "amount_zscore": float(r["amount_zscore"]),
                "velocity_zscore": float(r["velocity_zscore"]),
                "is_structuring": int(r["is_structuring"]),
                "is_rapid_cashout": int(r["is_rapid_cashout"])
            }
        })

    report_json = {
        "leakage_check": {
            "passed": passed_leakage,
            "notes": leakage_notes
        },
        "dataset_summary": {
            "total_transactions_evaluated": total_tx,
            "total_positive_ground_truth": total_pos_gt,
            "positive_rate_pct": round(pos_rate_pct, 4),
            "total_customers": total_customers,
            "customers_with_risk_profile": customers_with_risk
        },
        "transaction_level": {
            "naive_baseline": tx_naive_metrics,
            "sentinel_high_only": tx_high_metrics,
            "sentinel_high_plus_medium": tx_med_metrics
        },
        "customer_level": {
            "naive_baseline": cust_naive_metrics,
            "sentinel_high_only": cust_high_metrics,
            "sentinel_high_plus_medium": cust_med_metrics
        },
        "alert_reduction": {
            "high_only_vs_naive_pct": round(high_vs_naive_pct, 2),
            "high_plus_medium_vs_naive_pct": round(med_vs_naive_pct, 2)
        },
        "error_samples": {
            "false_negatives_top15": fn_samples,
            "false_positives_high_top15": fp_samples
        }
    }

    # Save to JSON
    os.makedirs(os.path.dirname(REPORT_JSON_PATH), exist_ok=True)
    with open(REPORT_JSON_PATH, "w") as f:
        json.dump(report_json, f, indent=2)
    logger.info(f"Saved evaluation report to {REPORT_JSON_PATH}")

    # Output Console Summary Table
    print("\n" + "=" * 90)
    print("                SENTINEL EVALUATION HARNESS — BENCHMARK REPORT                ")
    print("=" * 90)
    print(f"LEAKAGE CHECK: {'PASS' if passed_leakage else 'FAIL'} ({leakage_notes})")
    print(f"DATASET SANITY: {total_tx:,} Txns | {total_pos_gt:,} Illicit ({pos_rate_pct:.4f}%) | {customers_with_risk:,}/{total_customers:,} Accounts Scored")
    print("-" * 90)
    print("TRANSACTION-LEVEL METRICS:")
    print(f"{'Tier':<26} | {'Precision':<10} | {'Recall':<10} | {'F1 Score':<10} | {'FPR':<10} | {'Alert Vol':<12}")
    print("-" * 90)
    print(f"{'Naive Baseline':<26} | {tx_naive_metrics['precision']:<10.4%} | {tx_naive_metrics['recall']:<10.4%} | {tx_naive_metrics['f1']:<10.4} | {tx_naive_metrics['fpr']:<10.4%} | {tx_naive_metrics['alert_volume']:<12,}")
    print(f"{'Sentinel (High Only)':<26} | {tx_high_metrics['precision']:<10.4%} | {tx_high_metrics['recall']:<10.4%} | {tx_high_metrics['f1']:<10.4} | {tx_high_metrics['fpr']:<10.4%} | {tx_high_metrics['alert_volume']:<12,}")
    print(f"{'Sentinel (High + Medium)':<26} | {tx_med_metrics['precision']:<10.4%} | {tx_med_metrics['recall']:<10.4%} | {tx_med_metrics['f1']:<10.4} | {tx_med_metrics['fpr']:<10.4%} | {tx_med_metrics['alert_volume']:<12,}")
    print("-" * 90)
    print("CUSTOMER-LEVEL METRICS:")
    print(f"{'Tier':<26} | {'Precision':<10} | {'Recall':<10} | {'F1 Score':<10} | {'FPR':<10} | {'Alert Vol':<12}")
    print("-" * 90)
    print(f"{'Naive Baseline':<26} | {cust_naive_metrics['precision']:<10.4%} | {cust_naive_metrics['recall']:<10.4%} | {cust_naive_metrics['f1']:<10.4} | {cust_naive_metrics['fpr']:<10.4%} | {cust_naive_metrics['alert_volume']:<12,}")
    print(f"{'Sentinel (High Only)':<26} | {cust_high_metrics['precision']:<10.4%} | {cust_high_metrics['recall']:<10.4%} | {cust_high_metrics['f1']:<10.4} | {cust_high_metrics['fpr']:<10.4%} | {cust_high_metrics['alert_volume']:<12,}")
    print(f"{'Sentinel (High + Medium)':<26} | {cust_med_metrics['precision']:<10.4%} | {cust_med_metrics['recall']:<10.4%} | {cust_med_metrics['f1']:<10.4} | {cust_med_metrics['fpr']:<10.4%} | {cust_med_metrics['alert_volume']:<12,}")
    print("-" * 90)
    print(f"ALERT REDUCTION: High-Only vs Naive = {high_vs_naive_pct:.2f}% reduction | High+Medium vs Naive = {med_vs_naive_pct:.2f}% reduction")
    print("=" * 90 + "\n")

    return report_json

if __name__ == "__main__":
    run_evaluation()
