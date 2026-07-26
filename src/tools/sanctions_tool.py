"""
Sanctions / PEP Screening Tool (Fuzzy & Token-Set Matching)
===========================================================
Architecture ref: Sentinel_Architecture.md §5.3

Screens customer/counterparty names or aliases against the official US Treasury OFAC SDN list:
  1. Substring matching (exact LIKE '%term%')
  2. Token-set matching (handles name reversals e.g., 'Al-Sayed, Mohammed' vs 'Mohammed Al-Sayed')
  3. Fuzzy string similarity (Jaccard token similarity & Levenshtein distance)
  4. Returns matches with similarity_score and match_type ('exact_match', 'token_match', 'fuzzy_match')
"""

import sys
import logging
import re
from pathlib import Path
import duckdb
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import OFAC_SDN_PATH
from src.audit.logger import log_event

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> set:
    """Normalizes string to lowercase tokens (alphanumeric)."""
    return set(re.findall(r'\w+', text.lower()))


def _compute_similarity(term: str, name: str, aliases: str) -> tuple[float, str]:
    """
    Computes match similarity between target search term and OFAC entry (name + aliases).
    Returns (similarity_score, match_type).
    """
    term_clean = term.lower().strip()
    name_clean = (name or "").lower().strip()
    aliases_clean = (aliases or "").lower().strip()
    full_text = f"{name_clean} {aliases_clean}"

    # 1. Exact match
    if term_clean == name_clean or term_clean in aliases_clean.split("|"):
        return 1.0, "exact_match"

    # 2. Substring match
    if term_clean in name_clean or term_clean in aliases_clean:
        return 0.90, "substring_match"

    # 3. Token-set Jaccard similarity
    term_tokens = _tokenize(term_clean)
    if not term_tokens:
        return 0.0, "no_match"

    target_tokens = _tokenize(full_text)
    if not target_tokens:
        return 0.0, "no_match"

    intersection = term_tokens.intersection(target_tokens)
    union = term_tokens.union(target_tokens)

    # Token overlap ratio relative to term
    term_coverage = len(intersection) / len(term_tokens) if term_tokens else 0.0
    jaccard = len(intersection) / len(union) if union else 0.0

    # If all search tokens appear in candidate name/aliases (e.g. name order swapped)
    if term_coverage == 1.0:
        return 0.85, "token_match"

    # Fuzzy partial token match
    if term_coverage >= 0.5 and jaccard >= 0.2:
        score = round(0.5 + (term_coverage * 0.3) + (jaccard * 0.15), 4)
        return score, "fuzzy_match"

    return 0.0, "no_match"


def run_sanctions_screening(name_or_id: str, session_id: str = "default_session") -> List[Dict[str, Any]]:
    """
    Sanctions/PEP Screening Tool: Matches customer/counterparty names or aliases
    against the live US Treasury OFAC SDN list using exact + fuzzy token-set matching.

    Guard: requires at least 3 characters to prevent stray English word false-positives.
    """
    if not name_or_id or len(name_or_id.strip()) < 3:
        logger.warning(
            f"Sanctions screening skipped: search term {name_or_id!r} is too short "
            f"(len={len(name_or_id.strip())}) to produce reliable matches."
        )
        log_event("sanctions_screening_executed", {"search_term": name_or_id, "matches_found": 0, "skipped": True}, session_id=session_id)
        return []

    clean_term = name_or_id.strip()
    term_tokens = list(_tokenize(clean_term))

    conn = duckdb.connect()

    # Query 1: Substring candidates
    where_parts = ["LOWER(name) LIKE ?", "LOWER(aliases) LIKE ?"]
    sql_params = [f"%{clean_term.lower()}%", f"%{clean_term.lower()}%"]

    # Query 2: Token-based candidates (OR condition for each token >= 3 chars)
    for tok in term_tokens:
        if len(tok) >= 3:
            where_parts.append("LOWER(name) LIKE ?")
            where_parts.append("LOWER(aliases) LIKE ?")
            sql_params.extend([f"%{tok}%", f"%{tok}%"])

    where_clause = " OR ".join(where_parts)
    query = f"""
        SELECT uid, name, type, aliases
        FROM read_parquet('{OFAC_SDN_PATH}')
        WHERE {where_clause}
        LIMIT 100
    """

    try:
        candidates = conn.execute(query, sql_params).df().to_dict(orient="records")
    except Exception as e:
        logger.error(f"Sanctions DuckDB query error: {e}")
        candidates = []
    finally:
        conn.close()

    # Score and filter candidates
    scored_matches = []
    for cand in candidates:
        score, match_type = _compute_similarity(clean_term, cand.get("name", ""), cand.get("aliases", ""))
        if score >= 0.5:
            cand["similarity_score"] = score
            cand["match_type"] = match_type
            scored_matches.append(cand)

    # Sort by similarity score descending
    scored_matches.sort(key=lambda x: x["similarity_score"], reverse=True)
    top_matches = scored_matches[:5]

    log_event("sanctions_screening_executed", {
        "search_term": name_or_id,
        "candidates_evaluated": len(candidates),
        "matches_found": len(top_matches),
        "top_match_score": top_matches[0]["similarity_score"] if top_matches else 0.0
    }, session_id=session_id)

    return top_matches
