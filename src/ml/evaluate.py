import sys
from pathlib import Path
import duckdb
import pandas as pd
import logging

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ML_SCORED_PATH

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def evaluate_pipeline():
    """
    Evaluation Harness: Compares Sentinel Hybrid Pipeline against Naive Rule System 
    using IBM AML ground-truth labels (is_laundering = 1).
    Computes Precision, Recall, False Positive Rate (FPR), and FP reduction delta.
    """
    logger.info("Connecting to DuckDB and loading ml_scored.parquet...")
    conn = duckdb.connect()
    
    df = conn.execute(f"""
        SELECT 
            is_laundering,
            risk_level,
            ml_anomaly_score,
            amount_paid,
            is_structuring,
            is_rapid_cashout,
            is_round_number_suspicious
        FROM read_parquet('{ML_SCORED_PATH}')
    """).df()
    conn.close()

    total_records = len(df)
    total_illicit = (df['is_laundering'] == 1).sum()
    total_normal = (df['is_laundering'] == 0).sum()

    logger.info(f"Dataset Total: {total_records:,} txns | Illicit: {total_illicit:,} ({total_illicit/total_records:.2%}) | Normal: {total_normal:,}")

    # 1. Naive Baseline (Traditional Rule Engine: Flat threshold e.g., amount > $10,000 OR simple structuring)
    df['naive_flag'] = (df['amount_paid'] >= 10000) | (df['is_structuring'] == 1)
    
    naive_tp = ((df['naive_flag'] == True) & (df['is_laundering'] == 1)).sum()
    naive_fp = ((df['naive_flag'] == True) & (df['is_laundering'] == 0)).sum()
    naive_tn = ((df['naive_flag'] == False) & (df['is_laundering'] == 0)).sum()
    naive_fn = ((df['naive_flag'] == False) & (df['is_laundering'] == 1)).sum()

    naive_precision = naive_tp / (naive_tp + naive_fp + 1e-9)
    naive_recall = naive_tp / (naive_tp + naive_fn + 1e-9)
    naive_fpr = naive_fp / (naive_fp + naive_tn + 1e-9)

    # 2. Sentinel Hybrid System (Flagged as HIGH risk)
    df['sentinel_high_flag'] = (df['risk_level'] == 'high')
    
    high_tp = ((df['sentinel_high_flag'] == True) & (df['is_laundering'] == 1)).sum()
    high_fp = ((df['sentinel_high_flag'] == True) & (df['is_laundering'] == 0)).sum()
    high_tn = ((df['sentinel_high_flag'] == False) & (df['is_laundering'] == 0)).sum()
    high_fn = ((df['sentinel_high_flag'] == False) & (df['is_laundering'] == 1)).sum()

    high_precision = high_tp / (high_tp + high_fp + 1e-9)
    high_recall = high_tp / (high_tp + high_fn + 1e-9)
    high_fpr = high_fp / (high_fp + high_tn + 1e-9)

    # 3. Sentinel Hybrid System (Flagged as HIGH or MEDIUM risk)
    df['sentinel_medium_plus_flag'] = df['risk_level'].isin(['high', 'medium'])
    
    med_tp = ((df['sentinel_medium_plus_flag'] == True) & (df['is_laundering'] == 1)).sum()
    med_fp = ((df['sentinel_medium_plus_flag'] == True) & (df['is_laundering'] == 0)).sum()
    med_tn = ((df['sentinel_medium_plus_flag'] == False) & (df['is_laundering'] == 0)).sum()
    med_fn = ((df['sentinel_medium_plus_flag'] == False) & (df['is_laundering'] == 1)).sum()

    med_precision = med_tp / (med_tp + med_fp + 1e-9)
    med_recall = med_tp / (med_tp + med_fn + 1e-9)
    med_fpr = med_fp / (med_fp + med_tn + 1e-9)

    print("\n========================================================")
    print("      SENTINEL EVALUATION HARNESS BENCHMARK RESULTS      ")
    print("========================================================\n")
    print(f"{'Metric':<25} | {'Naive Baseline':<16} | {'Sentinel (High)':<16} | {'Sentinel (High+Med)':<18}")
    print("-" * 82)
    print(f"{'Precision':<25} | {naive_precision:<16.4%} | {high_precision:<16.4%} | {med_precision:<18.4%}")
    print(f"{'Recall':<25} | {naive_recall:<16.4%} | {high_recall:<16.4%} | {med_recall:<18.4%}")
    print(f"{'False Positive Rate (FPR)':<25} | {naive_fpr:<16.4%} | {high_fpr:<16.4%} | {med_fpr:<18.4%}")
    print(f"{'Flagged Volume':<25} | {naive_tp+naive_fp:<16,} | {high_tp+high_fp:<16,} | {med_tp+med_fp:<18,}")
    print("-" * 82)
    
    fp_reduction = (naive_fp - high_fp) / naive_fp if naive_fp > 0 else 0.0
    print(f"\nQUANTIFIED RESULT: Sentinel (High Risk) achieves {high_recall:.2%} Recall while reducing False Positives by {fp_reduction:.2%} compared to Naive Baseline.")
    print("========================================================\n")

if __name__ == "__main__":
    evaluate_pipeline()
