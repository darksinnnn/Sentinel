import sys
from pathlib import Path
import logging
from typing import Dict, Any, List, TypedDict, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.schemas import (
    AgentResponse, 
    IntentObject, 
    ToolFilters, 
    FlaggedItem
)
from src.agent.intent_extractor import extract_intent
from src.tools.eda_tool import run_eda
from src.tools.feature_tool import run_feature_engineering_query
from src.tools.anomaly_tool import run_anomaly_detection
from src.tools.risk_classifier import format_risk_classification
from src.tools.entity_lookup import run_entity_lookup
from src.tools.sanctions_tool import run_sanctions_screening
from src.tools.aggregation_tool import run_aggregation_query
from src.tools.explanation_tool import generate_explanations

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_query(query: str, session_id: str = "default_session") -> AgentResponse:
    """
    Main entry point for the Sentinel Agentic Orchestrator.
    Routes queries dynamically over the tool registry based on extracted intent.
    """
    logger.info(f"Orchestrator received query: '{query}' [session: {session_id}]")
    
    # 1. Intent Extraction
    intent: IntentObject = extract_intent(query, session_id=session_id)
    intent_type = intent.intent_type
    
    filters = ToolFilters(
        customer_id=intent.entities.customer_id,
        country=intent.entities.country,
        segment=intent.entities.segment,
        date_range=intent.entities.date_range,
        txn_type=intent.entities.txn_type,
        amount_threshold=intent.entities.amount_threshold,
        pattern_hint=intent.pattern_hint
    )

    tools_invoked = []
    tools_skipped = []
    flagged_items: List[FlaggedItem] = []
    supporting_metrics: Dict[str, Any] = {}
    reasoning = ""

    # 2. Dynamic Routing based on Intent
    if intent_type == "broad_scan":
        reasoning = "Executing full scan pipeline: EDA profiling -> feature extraction -> ML anomaly detection -> risk classification -> narrative explanation."
        tools_invoked = ["eda", "feature_engineering", "anomaly_detection", "risk_classification", "explanation"]
        tools_skipped = ["single_entity_lookup", "sanctions_screening", "aggregation_query"]
        
        supporting_metrics = run_eda(filters, session_id=session_id)
        raw_anomalies = run_anomaly_detection(filters, session_id=session_id)
        flagged_items = format_risk_classification(raw_anomalies, session_id=session_id)

    elif intent_type == "targeted_pattern":
        reasoning = f"Executing targeted pattern search for '{intent.pattern_hint}': scoped feature extraction -> anomaly detection -> risk classification -> narrative explanation."
        tools_invoked = ["feature_engineering", "anomaly_detection", "risk_classification", "explanation"]
        tools_skipped = ["eda", "single_entity_lookup", "sanctions_screening", "aggregation_query"]
        
        raw_anomalies = run_anomaly_detection(filters, session_id=session_id)
        flagged_items = format_risk_classification(raw_anomalies, session_id=session_id)

    elif intent_type == "aggregation_query":
        reasoning = "Executing direct aggregation rule tool. ML scoring skipped per query intent specification."
        tools_invoked = ["aggregation_query", "explanation"]
        tools_skipped = ["eda", "feature_engineering", "anomaly_detection", "risk_classification", "single_entity_lookup", "sanctions_screening"]
        
        flagged_items = run_aggregation_query(filters, session_id=session_id)

    elif intent_type == "single_entity_lookup":
        reasoning = f"Executing single entity lookup for customer '{filters.customer_id}' + sanctions/PEP screening -> narrative explanation. Full dataset ML scan skipped."
        tools_invoked = ["single_entity_lookup", "sanctions_screening", "explanation"]
        tools_skipped = ["eda", "feature_engineering", "anomaly_detection", "risk_classification", "aggregation_query"]
        
        flagged_items = run_entity_lookup(filters, session_id=session_id)
        
        if filters.customer_id:
            sanc_matches = run_sanctions_screening(filters.customer_id, session_id=session_id)
            if sanc_matches:
                supporting_metrics["ofac_sanctions_matches"] = sanc_matches
                if flagged_items:
                    flagged_items[0].evidence["ofac_matches"] = sanc_matches

    else: # Default fallback
        reasoning = "Executing default scan pipeline."
        tools_invoked = ["feature_engineering", "anomaly_detection", "risk_classification", "explanation"]
        tools_skipped = ["eda", "single_entity_lookup", "sanctions_screening", "aggregation_query"]
        
        raw_anomalies = run_anomaly_detection(filters, session_id=session_id)
        flagged_items = format_risk_classification(raw_anomalies, session_id=session_id)

    filters_dict = intent.entities.model_dump()
    filters_dict["pattern_hint"] = intent.pattern_hint

    # 3. Explanation Node (Phase 3 LLM + Grounded Narrative + SAR Draft)
    response = generate_explanations(
        query=query,
        intent_type=intent_type,
        filters_detected=filters_dict,
        tools_invoked=tools_invoked,
        tools_skipped=tools_skipped,
        reasoning=reasoning,
        flagged_items=flagged_items,
        supporting_metrics=supporting_metrics,
        session_id=session_id
    )

    return response

if __name__ == "__main__":
    # Canonical verification tests
    canonical_queries = [
        "Find structuring patterns in the last 30 days",
        "Which customers made 10+ transactions under $10k?",
        "Is customer 8000EBD30 suspicious?",
        "Is customer NONEXISTENT999 suspicious?"  # Test out-of-scope/inactive customer ID
    ]
    
    print("\n========================================================")
    print("      SENTINEL ORCHESTRATOR PHASE 2 VERIFICATION       ")
    print("========================================================\n")
    
    for q in canonical_queries:
        res = process_query(q)
        print(f"QUERY: '{q}'")
        print(f"DETECTED INTENT: {res.execution_summary.detected_intent}")
        print(f"TOOLS INVOKED:   {res.execution_summary.tools_invoked}")
        print(f"TOOLS SKIPPED:   {res.execution_summary.tools_skipped}")
        print(f"REASONING:       {res.execution_summary.reasoning}")
        print(f"FLAGGED ITEMS:   {len(res.flagged_items)} items returned")
        if res.flagged_items:
            first = res.flagged_items[0]
            print(f"  Top Flag: ID={first.entity_id} | Risk={first.risk_level} | Pattern={first.detected_pattern} | Score={first.risk_score}")
        print(f"AUDIT REF:       {res.audit_ref}")
        print("-" * 60 + "\n")
