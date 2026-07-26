import os
import sys
import json
import logging

from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.schemas import FlaggedItem, AgentResponse, ExecutionSummary
from src.audit.logger import log_event

logger = logging.getLogger(__name__)

EXPLANATION_SYSTEM_PROMPT = """You are a senior AML compliance analyst explaining suspicious activity flags.
Your task is to take computed risk metrics and generate grounding-accurate, auditable natural language explanations and optional SAR drafts.

RULES:
1. Grounding: Rely ONLY on the computed evidence, features, risk scores, and rule triggers provided. Do NOT invent numbers, transactions, or fake events.
2. Directness: Explain WHY the item was flagged, linking the computed pattern to the query intent.
3. Tone: Professional, objective, analytical compliance officer tone.
4. Output format: Return JSON with key "explanations" which is a list of objects matching:
   [
     {
       "entity_id": "<string>",
       "explanation": "<grounded explanation string>",
       "recommended_action": "monitor" | "review" | "report",
       "sar_draft": "<optional SAR paragraph if risk_level is high or action is report, else null>"
     }
   ]
"""

def deterministic_explanation(item: FlaggedItem, intent_type: str) -> tuple[str, str, Optional[str]]:
    """
    Fallback explanation generator that constructs grounded narrative from exact evidence facts.
    Guarantees reliable explainability even without external API connection.
    """
    score = item.risk_score
    level = item.risk_level
    pattern = item.detected_pattern
    ev = item.evidence or {}
    eid = item.entity_id

    # Action determination
    if level == "high":
        action = "report"
    elif level in ["medium", "insufficient_evidence"]:
        action = "review"
    else:
        action = "monitor"

    # Narrative construction based on computed facts
    if level == "insufficient_evidence":
        narrative = (
            f"Entity {eid} exhibited top 0.1% statistical peer deviation (peer score: {score:.2f}) "
            f"with zero matching rule-typology flags. System assigned 'insufficient_evidence' "
            f"to highlight unconfirmed statistical outlier for manual analyst investigation."
        )
    elif pattern == "structuring":
        sub_cnt = ev.get("sub_threshold_count_30d", ev.get("sub_threshold_count", "multiple"))
        narrative = (
            f"Flagged for structuring pattern with risk score {score:.2f} ({level} risk). "
            f"Entity {eid} registered {sub_cnt} sub-threshold transactions ($9,000–$9,999) "
            f"within a 30-day window, indicating potential threshold avoidance."
        )
    elif pattern == "rapid_cashout":
        narrative = (
            f"Flagged for rapid cash-out behavior with risk score {score:.2f} ({level} risk). "
            f"Entity {eid} executed a large outbound transfer draining >=50% of a prior >=$10,000 inbound "
            f"deposit within a 24-hour horizon."
        )
    elif pattern in ["sanctions_match", "ofac_sdn_match"]:
        ofac_info = ev.get("ofac_matches", "OFAC SDN list match")
        narrative = (
            f"CRITICAL SANCTIONS ALERT: Entity {eid} matched against US Treasury OFAC SDN sanctions list. "
            f"Details: {ofac_info}."
        )
        action = "report"
    elif pattern == "round_number_suspicious":
        narrative = (
            f"Flagged for suspicious round-number transaction concentration with risk score {score:.2f} ({level} risk). "
            f"Entity {eid} exhibited high frequency of clean, round-amount transactions."
        )
    else:
        narrative = (
            f"Entity {eid} flagged under {pattern} typology with risk score {score:.2f} ({level} risk). "
            f"Computed features: {json.dumps(ev, default=str)}."
        )

    # SAR draft if action is report or level is high
    sar_draft = None
    if action == "report" or level == "high":
        sar_draft = (
            f"SUSPICIOUS ACTIVITY REPORT DRAFT | Subject: {eid} | Risk Level: {level.upper()} (Score: {score:.2f})\n"
            f"Summary: Investigation revealed subject participating in suspicious {pattern} activity. "
            f"Evidentiary basis: {narrative} "
            f"Recommended for formal regulatory filing and account escalation."
        )

    return narrative, action, sar_draft

def generate_explanations(
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
    Explanation & Narrative Layer (Phase 3 Core):
    Gradiates raw tool output facts into natural-language narratives and SAR drafts,
    either via LLM or deterministic fallback parser.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    if api_key and not api_key.startswith("your_") and flagged_items:
        try:
            import requests

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            # Format minimal payload to prevent token bloat
            items_payload = [
                {
                    "entity_id": item.entity_id,
                    "entity_type": item.entity_type,
                    "risk_level": item.risk_level,
                    "risk_score": item.risk_score,
                    "detected_pattern": item.detected_pattern,
                    "evidence": item.evidence
                } for item in flagged_items[:10] # Cap top 10 for LLM narrative
            ]

            prompt_input = (
                f"Query: {query}\n"
                f"Intent: {intent_type}\n"
                f"Flagged Items Data:\n{json.dumps(items_payload, indent=2, default=str)}\n"
            )

            payload = {
                "contents": [{
                    "parts": [
                        {"text": EXPLANATION_SYSTEM_PROMPT},
                        {"text": prompt_input}
                    ]
                }],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.2
                }
            }

            response = requests.post(url, json=payload, timeout=12)
            if response.status_code == 200:
                res_data = response.json()
                text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                expl_map = {e["entity_id"]: e for e in parsed.get("explanations", []) if "entity_id" in e}

                for item in flagged_items:
                    if item.entity_id in expl_map:
                        e_obj = expl_map[item.entity_id]
                        item.explanation = e_obj.get("explanation", item.explanation)
                        item.recommended_action = e_obj.get("recommended_action", item.recommended_action)
                        if e_obj.get("sar_draft"):
                            item.sar_draft = e_obj["sar_draft"]
                    else:
                        # Fallback for unmapped items
                        nar, act, sar = deterministic_explanation(item, intent_type)
                        item.explanation = nar
                        item.recommended_action = act
                        if sar:
                            item.sar_draft = sar

                logger.info("Generated LLM-enhanced narrative explanations successfully.")
            else:
                logger.warning(f"LLM API returned {response.status_code}. Using deterministic explanation fallback.")
                for item in flagged_items:
                    nar, act, sar = deterministic_explanation(item, intent_type)
                    item.explanation = nar
                    item.recommended_action = act
                    if sar:
                        item.sar_draft = sar
        except Exception as e:
            logger.warning(f"LLM narrative generation error ({e}). Using deterministic explanation fallback.")
            for item in flagged_items:
                nar, act, sar = deterministic_explanation(item, intent_type)
                item.explanation = nar
                item.recommended_action = act
                if sar:
                    item.sar_draft = sar
    else:
        # Deterministic generation for all items
        for item in flagged_items:
            nar, act, sar = deterministic_explanation(item, intent_type)
            item.explanation = nar
            item.recommended_action = act
            if sar:
                item.sar_draft = sar

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
