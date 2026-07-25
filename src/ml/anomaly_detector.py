import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import logging
import os
from pathlib import Path

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import (
    SCORED_FEATURES_PATH,
    ML_SCORED_PATH,
    ML_FEATURES,
    ISOLATION_FOREST_CONTAMINATION,
    HIGH_ANOMALY_THRESHOLD,
    MEDIUM_ANOMALY_THRESHOLD
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
#training
def train_and_score_anomalies():
    """
    Trains Isolation Forest on peer-relative z-scores and typology features from scored_features.parquet,
    produces a normalized ml_anomaly_score (0.0 to 1.0), and assigns risk_level.
    """
    if not os.path.exists(SCORED_FEATURES_PATH):
        logger.error(f"Input file not found: {SCORED_FEATURES_PATH}")
        return

    logger.info(f"Loading feature dataset from {SCORED_FEATURES_PATH}...")
    df = pd.read_parquet(SCORED_FEATURES_PATH)
    logger.info(f"Loaded {len(df):,} transactions.")

    # Prepare feature matrix X
    X = df[ML_FEATURES].copy()
    X = X.fillna(0.0)

    logger.info(f"Training Isolation Forest on features: {ML_FEATURES}...")
    model = IsolationForest(
        n_estimators=100,
        contamination=ISOLATION_FOREST_CONTAMINATION,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X)

    # decision_function: lower/more negative means more anomalous
    raw_scores = model.decision_function(X)
    
    # Invert and min-max scale so higher value (0 to 1) means higher risk/anomaly
    inverted_scores = -raw_scores
    min_s, max_s = inverted_scores.min(), inverted_scores.max()
    normalized_scores = (inverted_scores - min_s) / (max_s - min_s + 1e-9)

    df["ml_anomaly_score"] = np.round(normalized_scores, 4)

    logger.info("Classifying risk levels based on ML anomaly score and typology triggers...")
    
    # Strong typology signal: structuring OR rapid cashout with elevated velocity/amount z-score
    has_strong_typology = (
        (df["is_structuring"] == 1) | 
        ((df["is_rapid_cashout"] == 1) & (df["velocity_zscore"] > 0.5)) |
        (df["is_round_number_suspicious"] == 1)
    )

    # High: Anomaly score >= 0.65 OR (Anomaly score >= 0.40 AND strong typology)
    # Medium: Anomaly score >= 0.40 OR strong typology
    # Low: Otherwise
    
    high_cond = (df["ml_anomaly_score"] >= HIGH_ANOMALY_THRESHOLD) | (
        (df["ml_anomaly_score"] >= MEDIUM_ANOMALY_THRESHOLD) & has_strong_typology
    )
    medium_cond = (
        (df["ml_anomaly_score"] >= MEDIUM_ANOMALY_THRESHOLD) | has_strong_typology
    ) & (~high_cond)

    df["risk_level"] = "low"
    df.loc[medium_cond, "risk_level"] = "medium"
    df.loc[high_cond, "risk_level"] = "high"

    # Save results
    os.makedirs(os.path.dirname(ML_SCORED_PATH), exist_ok=True)
    df.to_parquet(ML_SCORED_PATH)

    logger.info(f"ML Scoring complete! Saved to {ML_SCORED_PATH}")
    logger.info("Risk Level Distribution:")
    logger.info(df["risk_level"].value_counts().to_string())

if __name__ == "__main__":
    train_and_score_anomalies()
