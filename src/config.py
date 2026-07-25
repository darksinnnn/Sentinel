import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"

# Data file paths
SCORED_FEATURES_PATH = os.getenv("SCORED_FEATURES_PATH", str(DATA_DIR / "scored_features.parquet"))
PEER_BASELINES_PATH = os.getenv("PEER_BASELINES_PATH", str(DATA_DIR / "peer_baselines.parquet"))
CUSTOMERS_PATH = os.getenv("CUSTOMERS_PATH", str(DATA_DIR / "customers.parquet"))
TRANSACTIONS_PATH = os.getenv("TRANSACTIONS_PATH", str(DATA_DIR / "transactions.parquet"))
OFAC_SDN_PATH = os.getenv("OFAC_SDN_PATH", str(DATA_DIR / "ofac_sdn.parquet"))

ML_SCORED_PATH = os.getenv("ML_SCORED_PATH", str(DATA_DIR / "ml_scored.parquet"))
CUSTOMER_RISK_PATH = os.getenv("CUSTOMER_RISK_PATH", str(DATA_DIR / "customer_risk.parquet"))
DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "sentinel.db"))

# Feature selection for ML anomaly detection (z-scored & peer-aware features + typology hints)
ML_FEATURES = [
    "amount_zscore",
    "velocity_zscore",
    "txn_count_zscore",
    "counterparty_zscore",
    "is_rapid_cashout",
    "is_structuring",
    "is_round_number_suspicious",
    "sub_threshold_count_30d",
    "in_out_ratio_30d"
]

# Anomaly Detection & Risk Classification Thresholds
# IsolationForest decision_function outputs continuous score; lower/more negative means more anomalous.
# Contamination or score percentiles map to high/medium risk.
ISOLATION_FOREST_CONTAMINATION = 0.05  # top 5% estimated anomalies
HIGH_ANOMALY_THRESHOLD = 0.55  # recalibrated threshold
MEDIUM_ANOMALY_THRESHOLD = 0.35

# Log level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
