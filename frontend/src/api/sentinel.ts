import type { AgentResponse, AuditRecord } from '../types/outputContract';

const BASE_URL = 'http://127.0.0.1:8000';

export async function sendQuery(query: string, sessionId: string = 'default_session'): Promise<AgentResponse> {
  const response = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query, session_id: sessionId }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error (${response.status}): ${errorText}`);
  }

  return response.json();
}

export async function fetchAuditRecord(auditRef: string): Promise<AuditRecord> {
  const response = await fetch(`${BASE_URL}/audit/${auditRef}`);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Audit Record Fetch Failed (${response.status}): ${errorText}`);
  }

  return response.json();
}
