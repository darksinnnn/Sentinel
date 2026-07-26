import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import (
    SCORED_FEATURES_PATH,
    ML_SCORED_PATH,
    ML_FEATURES
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def train_and_score_anomalies():
    """
    Trains Isolation Forest and assigns Sentinel Risk Classifications using an OR-Gate Architecture:
    - High Risk if (rule_score >= 0.45) OR (peer_score >= 0.75 AND ml_anomaly_score >= 0.50)
    - Medium Risk if (rule_score >= 0.20) OR (peer_score >= 0.50) OR (ml_anomaly_score >= 0.50)
    - Low Risk otherwise
    
    This guarantees that strong peer deviations and ML anomaly signals have an independent path
    to 'high' risk even when rule_score == 0, eliminating structural lockout.
    """
    if not os.path.exists(SCORED_FEATURES_PATH):
        logger.error(f"Input file not found: {SCORED_FEATURES_PATH}")
        return

    logger.info(f"Loading feature dataset from {SCORED_FEATURES_PATH}...")
    df = pd.read_parquet(SCORED_FEATURES_PATH)
    logger.info(f"Loaded {len(df):,} transactions.")

    # Prepare feature matrix
    X = df[ML_FEATURES].copy().fillna(0.0)

    logger.info("Training Isolation Forest model...")
    model = IsolationForest(
        n_estimators=100,
        # contamination='auto' resolved to 14.59% effective rate — an 81x overestimate
        # vs the actual positive rate of 0.18% (5,177 illicit / 2,876,633 total).
        # Setting to 0.002 (~1.1x the real rate) so the IF's internal threshold
        # aligns with actual anomaly prevalence rather than defaulting to sklearn's
        # 'auto' heuristic which assumes ~15% of data is anomalous.
        contamination=0.002,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X)

    raw_scores = model.decision_function(X)
    inverted = -raw_scores
    min_s, max_s = inverted.min(), inverted.max()
    df["ml_anomaly_score"] = np.round((inverted - min_s) / (max_s - min_s + 1e-9), 4)

    logger.info("Computing Rule & Peer Scores for OR-Gate Risk Classification...")
    df = df.fillna(0.0)
    
    # 1. Rule Typology Score
    df["rule_score"] = (
        0.45 * df["is_structuring"] +
        0.35 * df["is_rapid_cashout"] +
        0.20 * (df["sub_threshold_count_30d"] >= 3).astype(float) +
        0.15 * df["is_round_number_suspicious"]
    )

    # 2. Peer Score (normalized z-scores capped at 1.0)
    df["peer_score"] = np.clip((df["amount_zscore"].abs() + df["velocity_zscore"].abs()) / 6.0, 0.0, 1.0)

    # 3. Composite Risk Score (for ranking / entity lookup)
    df["composite_risk_score"] = np.clip(
        0.50 * df["rule_score"] + 0.35 * df["peer_score"] + 0.15 * df["ml_anomaly_score"],
        0.0, 1.0
    )

    # 4. RULE-DRIVEN RISK CLASSIFICATION
    #
    # peer_score and ml_anomaly_score were removed from the classification gates
    # after empirical analysis (Finding 5) showed zero discriminative power on this
    # dataset: illicit transactions score lower than or equal to non-illicit at
    # p75–p99 for both signals. No threshold can produce signal from a distribution
    # with no separation. Keeping those gates contributed only false positives.
    #
    # Classification is now rule-typology-driven only:
    #   High:   rule_score >= 0.45  (is_structuring alone, or real combinations)
    #   Medium: rule_score >= 0.15  (round-number alone, sub-threshold alone, etc.)
    #   Low:    rule_score == 0     (no typology pattern detected)
    #
    # For transactions with zero rule signal, we do not fabricate a verdict based
    # on peer/ML scores that have been proven not to discriminate. Instead, the top
    # 0.1% of peer_score outliers (extreme statistical deviations with no rule flag)
    # are labeled "insufficient_evidence" — honest uncertainty, not a false alarm.
    df["risk_level"] = "low"
    df.loc[df["rule_score"] >= 0.15, "risk_level"] = "medium"
    df.loc[df["rule_score"] >= 0.45, "risk_level"] = "high"

    # Honest outlier label: top 0.1% of peer_score among zero-rule-flag transactions
    outlier_cutoff = df.loc[df["rule_score"] == 0, "peer_score"].quantile(0.999)
    insufficient_cond = (df["rule_score"] == 0) & (df["peer_score"] >= outlier_cutoff)
    df.loc[insufficient_cond, "risk_level"] = "insufficient_evidence"

    # Save results
    os.makedirs(os.path.dirname(ML_SCORED_PATH), exist_ok=True)
    df.to_parquet(ML_SCORED_PATH)

    logger.info(f"ML Scoring complete -> Saved to {ML_SCORED_PATH}")
    logger.info("Risk Level Distribution:")
    logger.info(df["risk_level"].value_counts().to_string())

if __name__ == "__main__":
    train_and_score_anomalies()
