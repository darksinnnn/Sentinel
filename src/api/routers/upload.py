import os
import shutil
import subprocess
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
import uuid

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.schemas import AgentResponse
from src.agent.orchestrator import process_query

router = APIRouter()

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/analyze-custom", response_model=AgentResponse)
async def analyze_custom_data(file: UploadFile = File(...)):
    if not file.filename.endswith((".csv", ".parquet")):
        raise HTTPException(status_code=400, detail="Only CSV or Parquet files are supported.")
        
    file_id = str(uuid.uuid4())
    ext = ".csv" if file.filename.endswith(".csv") else ".parquet"
    save_path = UPLOAD_DIR / f"{file_id}{ext}"
    
    with save_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # We invoke the orchestrator with a specialized query 
    try:
        response = process_query(
            f"Run custom scan on {save_path.absolute()}",
            session_id=file_id
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze custom data: {str(e)}")
