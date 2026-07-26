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
from src.tools.graph_tool import run_graph_analysis
from src.memory.session_store import get_store
from src.tools.trajectory_ledger import append_signal, get_trajectory, is_alert

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
        reasoning = "Executing full scan pipeline: EDA profiling -> feature extraction -> ML anomaly detection -> graph network analysis -> risk classification -> narrative explanation."
        tools_invoked = ["eda", "feature_engineering", "anomaly_detection", "graph_analysis", "risk_classification", "explanation"]
        tools_skipped = ["single_entity_lookup", "sanctions_screening", "aggregation_query"]
        
        supporting_metrics = run_eda(filters, session_id=session_id)
        raw_anomalies = run_anomaly_detection(filters, session_id=session_id)
        flagged_items = format_risk_classification(raw_anomalies, session_id=session_id)

        # Graph analysis — merge flagged items, graph metrics go into supporting_metrics
        try:
            graph_items, graph_metrics = run_graph_analysis(filters, session_id=session_id)
            supporting_metrics["graph"] = graph_metrics
            # Merge graph flags (avoid duplicates by entity_id)
            existing_ids = {f.entity_id for f in flagged_items}
            for gf in graph_items:
                if gf.entity_id not in existing_ids:
                    flagged_items.append(gf)
                    existing_ids.add(gf.entity_id)
        except Exception as e:
            logger.warning("Graph analysis failed (non-fatal): %s", e)

    elif intent_type == "targeted_pattern":
        pattern = intent.pattern_hint
        reasoning = f"Executing targeted pattern search for '{pattern}': scoped feature extraction -> anomaly detection{' -> graph network analysis' if pattern in ('layering', 'smurfing', 'unspecified') else ''} -> risk classification -> narrative explanation."
        tools_invoked = ["feature_engineering", "anomaly_detection", "risk_classification", "explanation"]
        tools_skipped = ["eda", "single_entity_lookup", "sanctions_screening", "aggregation_query"]
        
        raw_anomalies = run_anomaly_detection(filters, session_id=session_id)
        flagged_items = format_risk_classification(raw_anomalies, session_id=session_id)

        # Add graph analysis for layering/smurfing/unspecified — structural patterns need graph
        if pattern in ("layering", "smurfing", "unspecified"):
            try:
                graph_items, graph_metrics = run_graph_analysis(filters, session_id=session_id)
                supporting_metrics["graph"] = graph_metrics
                tools_invoked.append("graph_analysis")
                existing_ids = {f.entity_id for f in flagged_items}
                for gf in graph_items:
                    if gf.entity_id not in existing_ids:
                        flagged_items.append(gf)
                        existing_ids.add(gf.entity_id)
            except Exception as e:
                logger.warning("Graph analysis failed (non-fatal): %s", e)

    elif intent_type == "aggregation_query":
        reasoning = "Executing direct aggregation rule tool. ML scoring skipped per query intent specification."
        tools_invoked = ["aggregation_query", "explanation"]
        tools_skipped = ["eda", "feature_engineering", "anomaly_detection", "risk_classification", "single_entity_lookup", "sanctions_screening"]
        
        flagged_items = run_aggregation_query(filters, session_id=session_id)

    elif intent_type == "single_entity_lookup":
        # Architecture §5.8 — Validation gate:
        # Only proceed if the extracted ID matches the dataset's known account-ID format
        # (exactly 9 uppercase-alphanumeric characters, e.g. 8000EBD30 or 1004286A8).
        # If a stray English word was extracted (e.g. "is", "the"), abort and return a
        # clarifying response instead of fabricating a confident-looking LOW RISK verdict.
        import re as _re
        _VALID_ID = _re.compile(r'^[0-9A-Z]{9}$')
        customer_id = filters.customer_id or ""

        if not _VALID_ID.match(customer_id.upper()):
            reasoning = (
                f"Could not identify a valid account ID in the query — "
                f"'{customer_id}' does not match the expected 9-character alphanumeric format. "
                f"Did you mean to search for a specific account (e.g. 8000EBD30), "
                f"or find the most suspicious customers overall?"
            )
            tools_invoked = ["intent_extractor"]
            tools_skipped = ["single_entity_lookup", "sanctions_screening", "eda", "feature_engineering", "anomaly_detection", "risk_classification", "explanation"]
            flagged_items = [FlaggedItem(
                entity_type="system",
                entity_id="CLARIFICATION_REQUIRED",
                risk_level="low",
                risk_score=0.0,
                detected_pattern="unspecified",
                explanation=(
                    f"⚠ No valid account ID found in query. The term '{customer_id}' is not a recognisable "
                    f"customer identifier. Please provide a 9-character account ID (e.g. 8000EBD30) "
                    f"or rephrase as a population-level question (e.g. 'show me the most suspicious customers')."
                ),
                recommended_action="monitor",
                sar_draft=None
            )]
        else:
            reasoning = f"Executing single entity lookup for customer '{filters.customer_id}' + sanctions/PEP screening + trajectory ledger -> narrative explanation. Full dataset ML scan skipped."
            tools_invoked = ["single_entity_lookup", "sanctions_screening", "trajectory_ledger", "explanation"]
            tools_skipped = ["eda", "feature_engineering", "anomaly_detection", "risk_classification", "aggregation_query"]

            flagged_items = run_entity_lookup(filters, session_id=session_id)

            if filters.customer_id:
                # Sanctions screening
                sanc_matches = run_sanctions_screening(filters.customer_id, session_id=session_id)
                if sanc_matches:
                    supporting_metrics["ofac_sanctions_matches"] = sanc_matches
                    if flagged_items:
                        flagged_items[0].evidence["ofac_matches"] = sanc_matches
                
                # Trajectory ledger — append a query-triggered signal and retrieve accumulating score
                from datetime import datetime, timezone as _tz
                try:
                    # Score this lookup as a weak signal (repeated lookups suggest interest)
                    append_signal(
                        entity_id=filters.customer_id,
                        signal_type="entity_lookup",
                        weak_score=0.15,
                        timestamp=datetime.now(_tz.utc),
                    )
                    traj_score = get_trajectory(filters.customer_id)
                    traj_alert = is_alert(filters.customer_id)
                    supporting_metrics["trajectory_score"] = round(traj_score, 4)
                    supporting_metrics["trajectory_alert"] = traj_alert
                    # Enrich the flagged item evidence with trajectory data
                    if flagged_items:
                        flagged_items[0].evidence["trajectory_score"] = round(traj_score, 4)
                        flagged_items[0].evidence["trajectory_alert"] = traj_alert
                        if traj_alert and flagged_items[0].risk_level == "medium":
                            flagged_items[0].risk_level = "high"
                            flagged_items[0].recommended_action = "report"
                except Exception as e:
                    logger.warning("Trajectory ledger failed (non-fatal): %s", e)

    else: # follow_up or unknown fallback
        mem = get_store(session_id)
        history = mem.get_history(last_n=3)

        if intent_type == "follow_up" and history:
            # Try to resolve what entity the user is referring to
            last_entity = mem.get_last_flagged_entity()
            reasoning = (
                f"Follow-up query detected. Prior context: {len(history)} turn(s) in session. "
                f"{'Resolving to last flagged entity: ' + last_entity if last_entity else 'No specific entity resolved — returning context summary.'}"
            )
            tools_invoked = ["session_memory"]
            tools_skipped = ["eda", "anomaly_detection", "risk_classification", "aggregation_query"]

            if last_entity:
                # Reuse entity lookup for the last referenced entity
                filters.customer_id = last_entity
                flagged_items = run_entity_lookup(filters, session_id=session_id)
                tools_invoked.append("single_entity_lookup")
                # Check sanctions too
                sanc_matches = run_sanctions_screening(last_entity, session_id=session_id)
                if sanc_matches:
                    supporting_metrics["ofac_sanctions_matches"] = sanc_matches
                    tools_invoked.append("sanctions_screening")
        else:
            reasoning = "Executing default scan pipeline."
            tools_invoked = ["feature_engineering", "anomaly_detection", "risk_classification", "explanation"]
            tools_skipped = ["eda", "single_entity_lookup", "sanctions_screening", "aggregation_query"]
            raw_anomalies = run_anomaly_detection(filters, session_id=session_id)
            flagged_items = format_risk_classification(raw_anomalies, session_id=session_id)

    filters_dict = intent.entities.model_dump()
    filters_dict["pattern_hint"] = intent.pattern_hint

    # Load conversation context for follow-ups / explanation enrichment
    mem = get_store(session_id)
    prior_context = mem.get_context_block() if intent_type == "follow_up" else ""

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
        session_id=session_id,
        prior_context=prior_context,
    )

    # 4. Persist this turn to session memory (always, regardless of intent)
    try:
        mem.save_turn(
            query=query,
            intent_type=intent_type,
            tools_invoked=tools_invoked,
            flagged_items=flagged_items,
        )
    except Exception as e:
        logger.warning("Session memory save failed (non-fatal): %s", e)

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
