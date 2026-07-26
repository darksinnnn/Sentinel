"""
Insufficient Evidence Classifier — Stretch Goal Priority 2 (ISOLATED)
======================================================================
Standalone diagnostic script. Does NOT import or modify production
anomaly_detector.py or any main-system component.

Two criteria for "insufficient evidence":
  Criteria 1 (ML/Rule Disagreement, percentile-based):
    amount_zscore > p99.9 threshold AND all three rule flags = 0
    Uses percentile computed on-the-fly from the actual score distribution
    to remain consistent with Phase 2's percentile-based logic.

  Criteria 2 (Minimum Transaction History):
    rolling_txn_count_30d < 3 — too little history to baseline reliably.

Outputs a markdown-style report for comparison with the production classifier
before any merge decision.

Run standalone:
    python src/eval/test_insufficient_evidence.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import duckdb
import numpy as np
from src.config import SCORED_FEATURES_PATH

SCORED_PATH = str(SCORED_FEATURES_PATH)


def run():
    conn = duckdb.connect()

    print("=" * 66)
    print(" SENTINEL — Insufficient Evidence Classifier (Standalone)")
    print("=" * 66)

    # ── Criteria 1: ML/Rule Disagreement (percentile-based) ───────────────
    # Compute p99.9 on amount_zscore from the actual distribution (not a
    # hardcoded absolute threshold like 0.90, which may select a different
    # population depending on distribution shape).
    p999_threshold = conn.execute(f"""
        SELECT QUANTILE_CONT(amount_zscore, 0.999)
        FROM read_parquet('{SCORED_PATH}')
        WHERE amount_zscore IS NOT NULL
    """).fetchone()[0]

    print(f"\nCriteria 1 — ML/Rule Disagreement")
    print(f"  p99.9 amount_zscore threshold (computed from distribution): {p999_threshold:.4f}")

    c1_df = conn.execute(f"""
        SELECT sender_id, amount_zscore, is_structuring, is_rapid_cashout,
               is_round_number_suspicious, rolling_txn_count_30d, risk_level
        FROM read_parquet('{SCORED_PATH}')
        WHERE amount_zscore > {p999_threshold}
          AND is_structuring              = 0
          AND is_rapid_cashout            = 0
          AND is_round_number_suspicious  = 0
          AND amount_zscore IS NOT NULL
        ORDER BY amount_zscore DESC
        LIMIT 20
    """).df()

    c1_total = conn.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{SCORED_PATH}')
        WHERE amount_zscore > {p999_threshold}
          AND is_structuring             = 0
          AND is_rapid_cashout           = 0
          AND is_round_number_suspicious = 0
          AND amount_zscore IS NOT NULL
    """).fetchone()[0]

    total_rows = conn.execute(
        f"SELECT COUNT(*) FROM read_parquet('{SCORED_PATH}')"
    ).fetchone()[0]

    print(f"  Total transactions: {total_rows:,}")
    print(f"  Criteria 1 matches: {c1_total:,}  ({100*c1_total/total_rows:.3f}% of dataset)")
    print(f"\n  Top 5 sample (highest z-score, zero rule flags):")
    for _, row in c1_df.head(5).iterrows():
        print(f"    sender={row['sender_id']}  z={row['amount_zscore']:.2f}  "
              f"risk_level={row['risk_level']}  txns_30d={row['rolling_txn_count_30d']:.0f}")

    # ── Criteria 2: Minimum History ────────────────────────────────────────
    print(f"\nCriteria 2 — Minimum Transaction History (rolling_txn_count_30d < 3)")

    c2_df = conn.execute(f"""
        SELECT sender_id, rolling_txn_count_30d, amount_zscore, risk_level,
               is_structuring, is_rapid_cashout
        FROM read_parquet('{SCORED_PATH}')
        WHERE rolling_txn_count_30d < 3
        ORDER BY rolling_txn_count_30d ASC, amount_zscore DESC NULLS LAST
        LIMIT 20
    """).df()

    c2_total = conn.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{SCORED_PATH}')
        WHERE rolling_txn_count_30d < 3
    """).fetchone()[0]

    print(f"  Criteria 2 matches: {c2_total:,}  ({100*c2_total/total_rows:.3f}% of dataset)")
    print(f"\n  Sample (lowest history):")
    for _, row in c2_df.head(5).iterrows():
        print(f"    sender={row['sender_id']}  txns_30d={row['rolling_txn_count_30d']:.0f}  "
              f"z={row['amount_zscore'] if row['amount_zscore'] else 'N/A'}  "
              f"risk_level={row['risk_level']}")

    # ── Overlap (both criteria simultaneously) ─────────────────────────────
    overlap = conn.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{SCORED_PATH}')
        WHERE amount_zscore > {p999_threshold}
          AND is_structuring             = 0
          AND is_rapid_cashout           = 0
          AND is_round_number_suspicious = 0
          AND amount_zscore IS NOT NULL
          AND rolling_txn_count_30d < 3
    """).fetchone()[0]

    print(f"\n  Overlap (both criteria): {overlap:,}")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'─'*66}")
    print(f"  SUMMARY — Insufficient Evidence Population")
    print(f"{'─'*66}")
    print(f"  Criteria 1 (z-score outlier, no rule flags): {c1_total:,}")
    print(f"  Criteria 2 (< 3 txns in window):             {c2_total:,}")
    print(f"  Overlap (both):                              {overlap:,}")
    combined = c1_total + c2_total - overlap
    print(f"  Combined unique:                             {combined:,}  "
          f"({100*combined/total_rows:.3f}% of dataset)")
    print(f"\n  p99.9 z-score threshold used: {p999_threshold:.4f}")
    print(f"  (Compare this value with Phase 2 anomaly_detector.py before any merge)")
    print()

    conn.close()
    return {
        "p999_threshold": p999_threshold,
        "c1_count": c1_total,
        "c2_count": c2_total,
        "overlap": overlap,
        "total_rows": total_rows,
    }


if __name__ == "__main__":
    run()
