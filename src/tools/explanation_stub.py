import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.schemas import FlaggedItem, AgentResponse, ExecutionSummary
from src.audit.logger import log_event

def stub_explanation_node(
    query: str,
    intent_type: str,
    filters_detected: Dict[str, Any],
    tools_invoked: List[str],
    tools_skipped: List[str],
    reasoning: str,
    flagged_items: List[FlaggedItem],
    supporting_metrics: Dict[str, Any] = None,
    session_id: str = "default_session"
) -> AgentResponse:
    """
    Step 2.4.5 — Explanation Stub (Resolution #2):
    Produces a schema-conforming AgentResponse with a stub explanation.
    In Phase 3, this single function body is replaced with the LLM narrative call.
    """
    audit_ref = log_event(
        "agent_response_generated",
        {
            "query": query,
            "intent": intent_type,
            "tools_invoked": tools_invoked,
            "flagged_count": len(flagged_items)
        },
        session_id=session_id
    )
    
    # Attach stub explanation text to items if missing
    for item in flagged_items:
        if item.explanation.startswith("Flagged by"):
            item.explanation = f"[Explanation pending — Phase 3] Identified {item.detected_pattern} pattern for {item.entity_type} {item.entity_id} with risk score {item.risk_score:.2f}."

    summary = ExecutionSummary(
        query=query,
        detected_intent=intent_type,
        filters_detected=filters_detected,
        tools_invoked=tools_invoked,
        tools_skipped=tools_skipped,
        reasoning=reasoning
    )

    return AgentResponse(
        execution_summary=summary,
        flagged_items=flagged_items,
        supporting_metrics=supporting_metrics or {},
        audit_ref=audit_ref
    )
