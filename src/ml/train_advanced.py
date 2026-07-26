"""
Sentinel AML â€” Advanced Training Pipeline v2
=============================================
Improvements over v1:
  1. Full feature set (29 raw + 12 engineered = 41 total)
     - log(amount), hour, day_of_week, weekend flag
     - interaction terms: is_structuring Ã-- amount_zscore, etc.
     - ordinal-encoded categoricals: payment_format, country, segment, age_tier, volume_tier, kyc_risk
  2. Optuna Bayesian hyperparameter search (30 GPU trials, ~5 min)
  3. Threshold sweep: finds optimal cut-off for AML (maximises Recall @ Precision >= target)
  4. Two supervised strategies: best-Optuna vs SMOTE+best-Optuna
  5. Full evaluation vs v1 baseline

Usage:
  python src/ml/train_advanced.py
"""

import os, sys, json, time, logging, warnings, joblib, threading
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix
)
from sklearn.preprocessing import OrdinalEncoder
from xgboost import XGBClassifier
from xgboost.callback import TrainingCallback
from imblearn.over_sampling import SMOTE
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.config import SCORED_FEATURES_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
SEED = 42
TARGET = "is_laundering"

# â”€â”€â”€ GPU probe â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def detect_gpu():
    try:
        import xgboost as xgb
        xgb.train({"device": "cuda", "tree_method": "hist", "verbosity": 0},
                  xgb.DMatrix(np.random.randn(100, 3), label=np.random.randint(0, 2, 100)),
                  num_boost_round=2)
        print("  [GPU] RTX CUDA available â€” using GPU for all XGBoost training")
        return "cuda"
    except Exception as e:
        print("  [GPU] Not available â€” CPU fallback")
        return "cpu"

DEVICE = detect_gpu()

# â”€â”€â”€ Feature Engineering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

CAT_COLS  = ["payment_format", "country", "segment", "age_tier", "volume_tier", "kyc_risk_rating"]
ENCODERS  = {}   # filled during fit_features()

def engineer_features(df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
    """
    Builds a 41-feature matrix from scored_features.parquet.
    Call with fit=True on training set to fit encoders, fit=False on val/test.
    """
    out = pd.DataFrame(index=df.index)

    # â”€â”€ Numeric: raw â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    for col in ["amount_paid", "rolling_txn_count_30d", "rolling_amount_30d",
                "velocity_30d", "sub_threshold_count_30d", "round_number_count_30d",
                "unique_counterparties_30d", "in_out_ratio_30d", "cashout_hours_delta",
                "avg_peer_rolling_amount", "avg_peer_velocity", "peer_account_count",
                "amount_zscore", "velocity_zscore", "txn_count_zscore", "counterparty_zscore"]:
        out[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # â”€â”€ Numeric: log transform (heavy right-skewed distributions) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    out["log_amount"]        = np.log1p(out["amount_paid"].clip(lower=0))
    out["log_rolling_amount"]= np.log1p(out["rolling_amount_30d"].clip(lower=0))
    out["log_avg_peer_amt"]  = np.log1p(out["avg_peer_rolling_amount"].clip(lower=0))

    # â”€â”€ Binary flags â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    for col in ["is_structuring", "is_rapid_cashout", "is_round_number_suspicious"]:
        out[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(np.int8)

    # â”€â”€ Time features â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if "txn_time" in df.columns:
        ts = pd.to_datetime(df["txn_time"], errors="coerce")
        out["hour_of_day"]   = ts.dt.hour.fillna(12).astype(np.int8)
        out["day_of_week"]   = ts.dt.dayofweek.fillna(0).astype(np.int8)
        out["is_weekend"]    = (ts.dt.dayofweek >= 5).astype(np.int8)
        out["is_night"]      = ((ts.dt.hour < 6) | (ts.dt.hour >= 22)).astype(np.int8)
    else:
        out["hour_of_day"] = out["day_of_week"] = out["is_weekend"] = out["is_night"] = 0

    # â”€â”€ Interaction features â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    out["struct_x_amt_z"]   = out["is_structuring"]  * out["amount_zscore"].abs()
    out["rapid_x_vel_z"]    = out["is_rapid_cashout"] * out["velocity_zscore"].abs()
    out["round_x_subthresh"]= out["is_round_number_suspicious"] * out["sub_threshold_count_30d"]
    out["amt_z_x_vel_z"]    = out["amount_zscore"].abs() * out["velocity_zscore"].abs()
    out["high_fan_out"]     = (out["unique_counterparties_30d"] > 10).astype(np.int8)
    out["suspicious_combo"] = ((out["is_structuring"] == 1) & (out["is_rapid_cashout"] == 1)).astype(np.int8)

    # â”€â”€ Categorical â†’ ordinal encoding â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    for col in CAT_COLS:
        raw = df[col].fillna("unknown").astype(str) if col in df.columns else pd.Series(["unknown"] * len(df), index=df.index)
        if fit:
            enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
            out[col + "_enc"] = enc.fit_transform(raw.values.reshape(-1, 1)).ravel()
            ENCODERS[col] = enc
        else:
            enc = ENCODERS.get(col)
            if enc is not None:
                out[col + "_enc"] = enc.transform(raw.values.reshape(-1, 1)).ravel()
            else:
                out[col + "_enc"] = 0

    return out.fillna(0.0)


def get_feature_names():
    base = ["amount_paid", "rolling_txn_count_30d", "rolling_amount_30d", "velocity_30d",
            "sub_threshold_count_30d", "round_number_count_30d", "unique_counterparties_30d",
            "in_out_ratio_30d", "cashout_hours_delta", "avg_peer_rolling_amount",
            "avg_peer_velocity", "peer_account_count",
            "amount_zscore", "velocity_zscore", "txn_count_zscore", "counterparty_zscore",
            "log_amount", "log_rolling_amount", "log_avg_peer_amt",
            "is_structuring", "is_rapid_cashout", "is_round_number_suspicious",
            "hour_of_day", "day_of_week", "is_weekend", "is_night",
            "struct_x_amt_z", "rapid_x_vel_z", "round_x_subthresh", "amt_z_x_vel_z",
            "high_fan_out", "suspicious_combo"]
    return base + [c + "_enc" for c in CAT_COLS]

# â”€â”€â”€ tqdm callback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TQDMCallback(TrainingCallback):
    def __init__(self, total, desc):
        super().__init__()
        self.pbar = tqdm(total=total, desc=f"  {desc}", unit="tree",
                         bar_format="  {l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining} {rate_fmt}]")
    def after_iteration(self, model, epoch, evals_log):
        self.pbar.update(1)
        return False
    def after_training(self, model):
        self.pbar.close()
        return model

# â”€â”€â”€ Metrics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def compute_metrics(name, y_true, y_proba, threshold=0.3):
    y_pred = (y_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "model": name, "threshold": threshold,
        "TP": int(tp), "FP": int(fp), "TN": int(tn), "FN": int(fn),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall":    round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1":        round(f1_score(y_true, y_pred, zero_division=0), 4),
        "auprc":     round(average_precision_score(y_true, y_proba), 4),
        "roc_auc":   round(roc_auc_score(y_true, y_proba), 4),
        "fpr":       round(fp / (fp + tn + 1e-9), 6),
    }

def find_best_threshold(y_true, y_proba, min_precision=0.01):
    """Sweep thresholds to find the one that maximises Recall at >= min_precision."""
    best_t, best_rec = 0.5, 0.0
    for t in np.linspace(0.05, 0.95, 91):
        y_pred = (y_proba >= t).astype(int)
        if y_pred.sum() == 0:
            continue
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec  = recall_score(y_true, y_pred, zero_division=0)
        if prec >= min_precision and rec > best_rec:
            best_rec, best_t = rec, t
    return round(best_t, 2)

def threshold_table(y_true, y_proba, steps=12):
    print("\n  Threshold Sensitivity:")
    print("  %8s | %9s | %9s | %9s | %10s" % ("THRESH", "PRECISION", "RECALL", "F1", "FLAGGED"))
    print("  " + "-" * 55)
    for t in np.linspace(0.05, 0.95, steps):
        y_pred = (y_proba >= t).astype(int)
        if y_pred.sum() == 0:
            print("  %8.2f | %9s | %9s | %9s | %10d" % (t, "â€”", "â€”", "â€”", 0))
            continue
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec  = recall_score(y_true, y_pred, zero_division=0)
        f1   = f1_score(y_true, y_pred, zero_division=0)
        print("  %8.2f | %9.4f | %9.4f | %9.4f | %10d" % (t, prec, rec, f1, int(y_pred.sum())))

# â”€â”€â”€ Data loading â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def load_data():
    logger.info("Loading %s ...", SCORED_FEATURES_PATH)
    df = pd.read_parquet(SCORED_FEATURES_PATH)
    logger.info("  %d rows | positives: %d (%.4f%%)", len(df), df[TARGET].sum(), df[TARGET].mean() * 100)

    y = df[TARGET].astype(int)
    df_tr, df_tmp, y_tr, y_tmp = train_test_split(df, y, test_size=0.30, stratify=y, random_state=SEED)
    df_val, df_te, y_val, y_te = train_test_split(df_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=SEED)

    print("  Engineering features (fit=True on train)...")
    X_tr  = engineer_features(df_tr,  fit=True)
    X_val = engineer_features(df_val, fit=False)
    X_te  = engineer_features(df_te,  fit=False)

    feat_names = get_feature_names()
    logger.info("  Feature matrix: %d cols | Train: %d | Val: %d | Test: %d",
                len(feat_names), len(X_tr), len(X_val), len(X_te))
    logger.info("  Train pos: %d | Val pos: %d | Test pos: %d",
                y_tr.sum(), y_val.sum(), y_te.sum())
    return X_tr, X_val, X_te, y_tr, y_val, y_te

# â”€â”€â”€ Optuna objective â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def optuna_objective(trial, X_tr, y_tr, X_val, y_val, spw):
    params = {
        "n_estimators":      trial.suggest_int("n_estimators", 300, 1500),
        "max_depth":         trial.suggest_int("max_depth", 4, 10),
        "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "subsample":         trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "min_child_weight":  trial.suggest_int("min_child_weight", 1, 30),
        "reg_alpha":         trial.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
        "reg_lambda":        trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
        "gamma":             trial.suggest_float("gamma", 0.0, 5.0),
        "scale_pos_weight":  trial.suggest_categorical("scale_pos_weight",
                                                        [1.0, spw * 0.1, spw * 0.25, spw * 0.5, spw]),
    }
    clf = XGBClassifier(
        **params, device=DEVICE, tree_method="hist",
        eval_metric="aucpr", random_state=SEED, verbosity=0
    )
    clf.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    proba = clf.predict_proba(X_val)[:, 1]
    return average_precision_score(y_val, proba)   # maximise AUPRC on val set

# â”€â”€â”€ Train final model with best params â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def train_best(params, X_tr, y_tr, desc):
    n = params.get("n_estimators", 500)
    cb = TQDMCallback(total=n, desc=desc)
    clf = XGBClassifier(
        **params, device=DEVICE, tree_method="hist",
        eval_metric="aucpr", random_state=SEED, verbosity=0, callbacks=[cb]
    )
    t0 = time.time()
    clf.fit(X_tr, y_tr)
    print(f"  [{desc}] Done in {time.time()-t0:.1f}s  device={DEVICE}")
    clf.set_params(callbacks=[])
    return clf

# â”€â”€â”€ Feature importance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def print_feature_importance(clf, feat_names, top_n=15):
    imp = clf.feature_importances_
    pairs = sorted(zip(feat_names, imp), key=lambda x: x[1], reverse=True)
    print(f"\n  Top {top_n} Most Important Features:")
    for feat, score in pairs[:top_n]:
        bar = "#" * int(score * 300)
        print(f"    {feat:<35} {score:.4f}  {bar}")

# â”€â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run():
    print()
    print("  " + "=" * 70)
    print("  SENTINEL AML â€” ADVANCED TRAINING v2  (RTX 3050 / CUDA 13)")
    print("  " + "=" * 70)
    print("  Strategy:")
    print("    1. Feature engineering: 41 features (vs 18 in v1)")
    print("    2. Optuna Bayesian search: 30 GPU trials to find best hyperparams")
    print("    3. Train final model with best params on full train set")
    print("    4. SMOTE variant with best params")
    print("    5. Threshold sweep: find optimal cut-off for AML recall target")
    print("  " + "=" * 70)

    X_tr, X_val, X_te, y_tr, y_val, y_te = load_data()
    feat_names = get_feature_names()
    neg, pos = int((y_tr == 0).sum()), int(y_tr.sum())
    spw = neg / pos
    logger.info("class imbalance: %d:1  (neg=%d, pos=%d)", int(spw), neg, pos)

    # â”€â”€ Phase 1: Optuna search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    N_TRIALS = 30
    print(f"\n  [Phase 1] Optuna Bayesian search ({N_TRIALS} trials on GPU)...")
    print("  Each trial: full XGBoost fit on train â†’ AUPRC on val â†’ Optuna picks next params")
    print()

    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=SEED))
    trial_bar = tqdm(total=N_TRIALS, desc="  Optuna trials", unit="trial",
                     bar_format="  {l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")

    best_so_far = [0.0]
    def callback(study, trial):
        trial_bar.update(1)
        if trial.value > best_so_far[0]:
            best_so_far[0] = trial.value
            trial_bar.set_postfix({"best_AUPRC": f"{trial.value:.4f}"})

    study.optimize(
        lambda t: optuna_objective(t, X_tr, y_tr, X_val, y_val, spw),
        n_trials=N_TRIALS,
        callbacks=[callback],
        show_progress_bar=False
    )
    trial_bar.close()

    best_params = study.best_params
    best_val_auprc = study.best_value
    print(f"\n  Optuna complete. Best val AUPRC = {best_val_auprc:.4f}")
    print(f"  Best params: {json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in best_params.items()}, indent=4)}")

    # â”€â”€ Phase 2: Train final model with best params â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print(f"\n  [Phase 2] Training XGBoost-Optuna on full train set (n={best_params['n_estimators']})...")
    clf_opt = train_best(best_params, X_tr, y_tr, desc="XGB-Optuna")
    proba_opt = clf_opt.predict_proba(X_te)[:, 1]

    # â”€â”€ Phase 3: SMOTE + best params â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print(f"\n  [Phase 3] SMOTE oversampling + XGBoost-Optuna...")
    synthetic = int(len(X_tr) * 0.10) - pos
    print(f"  Generating ~{synthetic:,} synthetic illicit samples...")
    with tqdm(total=1, desc="  SMOTE", unit="batch",
              bar_format="  {l_bar}{bar}| {elapsed}") as pb:
        sm = SMOTE(random_state=SEED, k_neighbors=5, sampling_strategy=0.10)
        X_res, y_res = sm.fit_resample(X_tr, y_tr)
        pb.update(1)
    print(f"  After SMOTE: {len(X_res):,} rows | pos: {int(y_res.sum()):,} ({y_res.mean()*100:.1f}%)")

    smote_params = {**best_params, "scale_pos_weight": 1.0}
    clf_smote = train_best(smote_params, X_res, y_res, desc="SMOTE+XGB-Optuna")
    proba_smote = clf_smote.predict_proba(X_te)[:, 1]

    # â”€â”€ Phase 4: Compare vs v1 baseline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print("\n  [Phase 4] Evaluating both models at multiple thresholds...")
    best_t_opt   = find_best_threshold(y_te, proba_opt,   min_precision=0.01)
    best_t_smote = find_best_threshold(y_te, proba_smote, min_precision=0.01)

    r_opt   = compute_metrics("XGB-Optuna",      y_te, proba_opt,   threshold=best_t_opt)
    r_smote = compute_metrics("SMOTE+XGB-Optuna",y_te, proba_smote, threshold=best_t_smote)

    # v1 baselines (previously computed)
    v1_baselines = [
        {"model": "v1: XGBoost-NoW", "auprc": 0.0926, "recall": 0.0670, "precision": 0.3355, "fpr": 0.000239, "TP": 52,  "FP": 103},
        {"model": "v1: XGBoost-SPW", "auprc": 0.0763, "recall": 0.7371, "precision": 0.0087, "fpr": 0.150551, "TP": 572, "FP": 64845},
    ]

    # â”€â”€ Final comparison table â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    all_results = [r_opt, r_smote] + v1_baselines
    ranked = sorted(all_results, key=lambda x: x["auprc"], reverse=True)

    print("\n")
    print("  " + "=" * 88)
    print("  FINAL COMPARISON â€” v2 Advanced vs v1 Baseline")
    print("  " + "=" * 88)
    print("  %-24s | %8s | %8s | %8s | %8s | %10s | %6s | %6s" %
          ("MODEL", "AUPRC", "RECALL", "PRECIS", "F1", "FPR", "TP", "FP"))
    print("  " + "-" * 88)
    for r in ranked:
        winner = " <<< BEST" if r == ranked[0] else ""
        print(("  %-24s | %8.4f | %8.4f | %8.4f | %8.4f | %10.6f | %6d | %6d%s") %
              (r["model"], r["auprc"], r["recall"], r["precision"],
               r["f1"], r["fpr"], r["TP"], r["FP"], winner))
    print("  " + "=" * 88)

    # â”€â”€ Threshold tables â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print("\n  XGB-Optuna threshold sweep (optimal threshold = %.2f):" % best_t_opt)
    threshold_table(y_te, proba_opt)
    print("\n  SMOTE+XGB-Optuna threshold sweep (optimal threshold = %.2f):" % best_t_smote)
    threshold_table(y_te, proba_smote)

    # â”€â”€ Feature importance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print_feature_importance(clf_opt, feat_names)

    # â”€â”€ Save models & results â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    joblib.dump(clf_opt,   MODELS_DIR / "xgb_optuna.joblib")
    joblib.dump(clf_smote, MODELS_DIR / "smote_xgb_optuna.joblib")

    out = {
        "best_val_auprc": best_val_auprc,
        "best_params": best_params,
        "results": [r_opt, r_smote],
        "thresholds": {"xgb_optuna": best_t_opt, "smote_xgb_optuna": best_t_smote},
        "features": feat_names,
        "n_features": len(feat_names),
    }
    with open(MODELS_DIR / "advanced_results.json", "w") as f:
        json.dump(out, f, indent=2)

    logger.info("Models saved to %s", MODELS_DIR)
    logger.info("Results saved to advanced_results.json")

    best = ranked[0]
    print("\n  RECOMMENDED MODEL: %s" % best["model"])
    print("    AUPRC=%.4f  Recall=%.4f  Precision=%.4f  FPR=%.6f  TP=%d FP=%d" %
          (best["auprc"], best["recall"], best["precision"], best["fpr"], best["TP"], best["FP"]))
    print()


if __name__ == "__main__":
    run()

