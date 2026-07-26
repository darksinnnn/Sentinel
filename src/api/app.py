import sys
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv

# Load .env variables at API startup
load_dotenv()

from src.schemas import AgentResponse
from src.agent.orchestrator import process_query
from src.audit.logger import DB_PATH

app = FastAPI(
    title="Sentinel AML Conversational Compliance API",
    description="API interface for Sentinel AML Agentic Orchestration and Risk Intelligence",
    version="1.0.0"
)

from src.api.routers import upload
app.include_router(upload.router, prefix="/api/v1")

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str = Field(..., example="Find structuring patterns in the last 30 days")
    session_id: str = Field(default="default_session", example="session_123")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Sentinel AML Compliance API",
        "version": "1.0.0"
    }

@app.post("/chat", response_model=AgentResponse)
def chat_endpoint(req: ChatRequest):
    """
    Primary chat endpoint. Invokes Sentinel Orchestrator and returns structured AgentResponse.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")
    
    try:
        response = process_query(req.query, session_id=req.session_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestrator error: {str(e)}")

@app.get("/audit/{audit_ref}")
def get_audit_record(audit_ref: str):
    """
    Retrieves an immutable audit log entry by audit reference ID.
    """
    if not DB_PATH.exists():
        raise HTTPException(status_code=444, detail="Audit database not initialized.")
        
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT audit_ref, session_id, timestamp, event_type, payload, prev_hash, curr_hash FROM audit_log WHERE audit_ref = ?",
            (audit_ref,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Audit record '{audit_ref}' not found.")
            
        return {
            "audit_ref": row[0],
            "session_id": row[1],
            "timestamp": row[2],
            "event_type": row[3],
            "payload": json.loads(row[4]),
            "prev_hash": row[5],
            "curr_hash": row[6]
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
