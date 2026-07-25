from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

IntentType = Literal[
    "broad_scan", 
    "targeted_pattern", 
    "single_entity_lookup", 
    "aggregation_query", 
    "follow_up"
]

PatternHint = Literal[
    "structuring", 
    "smurfing", 
    "layering", 
    "rapid_cashout", 
    "unspecified"
]

EntityType = Literal["transaction", "customer"]
RiskLevel = Literal["low", "medium", "high", "insufficient_evidence"]
RecommendedAction = Literal["monitor", "review", "report"]


class Entities(BaseModel):
    customer_id: Optional[str] = None
    country: Optional[str] = None
    segment: Optional[str] = None
    date_range: Optional[str] = None
    txn_type: Optional[str] = None
    amount_threshold: Optional[float] = None


class IntentObject(BaseModel):
    intent_type: IntentType
    entities: Entities = Field(default_factory=Entities)
    pattern_hint: PatternHint = "unspecified"


class ToolFilters(BaseModel):
    customer_id: Optional[str] = None
    country: Optional[str] = None
    segment: Optional[str] = None
    date_range: Optional[str] = None
    txn_type: Optional[str] = None
    amount_threshold: Optional[float] = None
    pattern_hint: PatternHint = "unspecified"


class ExecutionSummary(BaseModel):
    query: str
    detected_intent: IntentType
    filters_detected: Dict[str, Any] = Field(default_factory=dict)
    tools_invoked: List[str] = Field(default_factory=list)
    tools_skipped: List[str] = Field(default_factory=list)
    reasoning: str


class FlaggedItem(BaseModel):
    entity_type: EntityType
    entity_id: str
    risk_level: RiskLevel
    risk_score: float
    detected_pattern: str
    explanation: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    recommended_action: RecommendedAction
    sar_draft: Optional[str] = None


class AgentResponse(BaseModel):
    execution_summary: ExecutionSummary
    flagged_items: List[FlaggedItem] = Field(default_factory=list)
    supporting_metrics: Dict[str, Any] = Field(default_factory=dict)
    audit_ref: str
