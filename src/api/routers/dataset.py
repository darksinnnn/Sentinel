from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import shutil
import os

router = APIRouter()

class DatasetSwitchRequest(BaseModel):
    mode: str  # 'main' or 'sample'

@router.post("/switch")
async def switch_dataset(request: DatasetSwitchRequest):
    mode = request.mode.lower()
    if mode not in ["main", "sample"]:
        raise HTTPException(status_code=400, detail="Invalid dataset mode. Must be 'main' or 'sample'.")

    source_dir = f"data/{mode}"
    target_dir = "data/processed"

    if not os.path.exists(source_dir):
        raise HTTPException(status_code=500, detail=f"Source directory {source_dir} does not exist.")

    # Check if the required files exist in the source directory
    ml_scored = os.path.join(source_dir, "ml_scored.parquet")
    customers = os.path.join(source_dir, "customers.parquet")
    customer_risk = os.path.join(source_dir, "customer_risk.parquet")

    if not os.path.exists(ml_scored) or not os.path.exists(customers):
        if mode == "main":
            raise HTTPException(
                status_code=404, 
                detail="Main dataset files are missing. Please place ml_scored.parquet and customers.parquet in the data/main/ directory."
            )
        else:
            raise HTTPException(status_code=404, detail="Sample dataset files are missing.")

    try:
        shutil.copy2(ml_scored, os.path.join(target_dir, "ml_scored.parquet"))
        shutil.copy2(customers, os.path.join(target_dir, "customers.parquet"))
        if os.path.exists(customer_risk):
            shutil.copy2(customer_risk, os.path.join(target_dir, "customer_risk.parquet"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to switch dataset: {str(e)}")

    return {"status": "success", "message": f"Successfully switched to {mode} dataset."}
