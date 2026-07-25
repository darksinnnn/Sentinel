import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.schemas import FlaggedItem, RiskLevel, RecommendedAction
from src.audit.logger import log_event

def format_risk_classification(anomalies: List[Dict[str, Any]], session_id: str = "default_session") -> List[FlaggedItem]:
    """
    Risk Classifier Tool: Converts raw anomaly dictionary objects into schema-conforming FlaggedItem models.
    """
    flagged_items = []
    
    for item in anomalies:
        score = float(item.get("ml_anomaly_score", 0.0))
        risk_lvl: RiskLevel = item.get("risk_level", "low")
        
        pattern = "unspecified"
        if item.get("is_structuring") == 1:
            pattern = "structuring"
        elif item.get("is_rapid_cashout") == 1:
            pattern = "rapid_cashout"
        elif item.get("is_round_number_suspicious") == 1:
            pattern = "round_number_anomaly"
            
        action: RecommendedAction = "report" if risk_lvl == "high" else ("review" if risk_lvl == "medium" else "monitor")
        
        flagged = FlaggedItem(
            entity_type="transaction",
            entity_id=str(item.get("sender_id", "UNKNOWN")),
            risk_level=risk_lvl,
            risk_score=score,
            detected_pattern=pattern,
            explanation="Flagged by peer-relative Isolation Forest anomaly detection.",
            evidence={
                "amount_paid": item.get("amount_paid"),
                "amount_zscore": item.get("amount_zscore"),
                "velocity_zscore": item.get("velocity_zscore")
            },
            recommended_action=action,
            sar_draft="Draft SAR: Customer exhibited sub-threshold or rapid cash-out transaction activity." if action == "report" else None
        )
        flagged_items.append(flagged)
        
    log_event("risk_classifier_executed", {"count": len(flagged_items)}, session_id=session_id)
    return flagged_items
