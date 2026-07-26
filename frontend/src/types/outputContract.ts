export type RiskLevel = 'high' | 'medium' | 'low' | 'insufficient_evidence';
export type RecommendedAction = 'report' | 'review' | 'monitor';

export interface ToolFilters {
  customer_id?: string | null;
  country?: string | null;
  segment?: string | null;
  date_range?: string | null;
  txn_type?: string | null;
  amount_threshold?: number | null;
  pattern_hint?: string | null;
}

export interface ExecutionSummary {
  query: string;
  detected_intent: string;
  filters_detected: Record<string, any>;
  tools_invoked: string[];
  tools_skipped: string[];
  reasoning: string;
}

export interface FlaggedItem {
  entity_type: string;
  entity_id: string;
  risk_level: RiskLevel;
  risk_score: number;
  detected_pattern: string;
  explanation: string;
  evidence?: Record<string, any>;
  chart_data?: Record<string, any>[];
  recommended_action?: RecommendedAction;
  sar_draft?: string | null;
}

export interface AgentResponse {
  execution_summary: ExecutionSummary;
  flagged_items: FlaggedItem[];
  supporting_metrics: Record<string, any>;
  audit_ref: string;
}

export interface AuditRecord {
  audit_ref: string;
  session_id: string;
  timestamp: string;
  event_type: string;
  payload: Record<string, any>;
  prev_hash: string;
  curr_hash: string;
}
