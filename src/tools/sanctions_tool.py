import sys
from pathlib import Path
import duckdb
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import OFAC_SDN_PATH
from src.schemas import ToolFilters, FlaggedItem
from src.audit.logger import log_event

def run_sanctions_screening(name_or_id: str, session_id: str = "default_session") -> List[Dict[str, Any]]:
    """
    Sanctions/PEP Screening Tool: Matches customer/counterparty names or aliases against the live US Treasury OFAC SDN list.
    """
    conn = duckdb.connect()
    
    query = f"""
    SELECT uid, name, type, aliases
    FROM read_parquet('{OFAC_SDN_PATH}')
    WHERE LOWER(name) LIKE ? OR LOWER(aliases) LIKE ?
    LIMIT 5;
    """
    search_term = f"%{name_or_id.lower()}%"
    matches = conn.execute(query, [search_term, search_term]).df().to_dict(orient="records")
    conn.close()
    
    log_event("sanctions_screening_executed", {"search_term": name_or_id, "matches_found": len(matches)}, session_id=session_id)
    return matches
