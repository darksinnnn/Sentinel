"""
Session Memory Store
====================
Architecture ref: Sentinel_Architecture.md §5.7

Design:
  - SQLite-backed, one row per conversation turn
  - Stores: session_id, turn_index, timestamp, query, intent_type,
            tools_invoked (JSON), flagged_summaries (JSON, NOT full raw data)
  - On follow_up intent: retrieves last N turns and formats a context block
    that gets injected into the explanation prompt
  - Keeps context windows small — stores summaries, not full flag objects

Schema:
  conversation_memory (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    turn_index   INTEGER NOT NULL,
    timestamp    TEXT NOT NULL,
    query        TEXT NOT NULL,
    intent_type  TEXT NOT NULL,
    tools_invoked TEXT NOT NULL,   -- JSON array
    flagged_summaries TEXT NOT NULL -- JSON: [{entity_id, risk_level, pattern, action}]
  )
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "session_memory.db"
MAX_HISTORY_TURNS = 5  # how many past turns to surface for follow-ups


class SessionMemoryStore:
    """
    Thread-safe, SQLite-backed conversation memory.
    Each instance is tied to one session_id.
    """

    def __init__(self, session_id: str, db_path: Optional[Path] = None):
        self.session_id = session_id
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id        TEXT NOT NULL,
                    turn_index        INTEGER NOT NULL,
                    timestamp         TEXT NOT NULL,
                    query             TEXT NOT NULL,
                    intent_type       TEXT NOT NULL,
                    tools_invoked     TEXT NOT NULL,
                    flagged_summaries TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON conversation_memory(session_id, turn_index)")
            conn.commit()

    def _next_turn_index(self, conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT MAX(turn_index) FROM conversation_memory WHERE session_id = ?",
            (self.session_id,)
        ).fetchone()
        return (row[0] or 0) + 1

    def save_turn(
        self,
        query: str,
        intent_type: str,
        tools_invoked: List[str],
        flagged_items: List[Any],   # List[FlaggedItem] — we only store summaries
    ) -> int:
        """
        Persists this turn. Returns the turn index.
        Stores minimal summaries (not full evidence dicts) to keep context small.
        """
        # Build compact summary — entity_id, risk_level, pattern, action only
        summaries = [
            {
                "entity_id": getattr(item, "entity_id", str(item)),
                "risk_level": getattr(item, "risk_level", "unknown"),
                "detected_pattern": getattr(item, "detected_pattern", "unspecified"),
                "recommended_action": getattr(item, "recommended_action", "monitor"),
                "explanation_snippet": (getattr(item, "explanation", "") or "")[:200],
            }
            for item in (flagged_items or [])
        ]

        timestamp = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            turn_index = self._next_turn_index(conn)
            conn.execute(
                """INSERT INTO conversation_memory
                   (session_id, turn_index, timestamp, query, intent_type, tools_invoked, flagged_summaries)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.session_id,
                    turn_index,
                    timestamp,
                    query,
                    intent_type,
                    json.dumps(tools_invoked),
                    json.dumps(summaries, default=str),
                )
            )
            conn.commit()

        logger.debug("SessionMemory: saved turn %d for session %s", turn_index, self.session_id)
        return turn_index

    def get_history(self, last_n: int = MAX_HISTORY_TURNS) -> List[Dict[str, Any]]:
        """Returns the last N turns for this session, oldest first."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT turn_index, timestamp, query, intent_type, tools_invoked, flagged_summaries
                   FROM conversation_memory
                   WHERE session_id = ?
                   ORDER BY turn_index DESC
                   LIMIT ?""",
                (self.session_id, last_n)
            ).fetchall()

        turns = []
        for row in reversed(rows):  # return oldest-first
            turns.append({
                "turn_index": row[0],
                "timestamp": row[1],
                "query": row[2],
                "intent_type": row[3],
                "tools_invoked": json.loads(row[4] or "[]"),
                "flagged_summaries": json.loads(row[5] or "[]"),
            })
        return turns

    def get_context_block(self, last_n: int = MAX_HISTORY_TURNS) -> str:
        """
        Formats last N turns as a compact natural-language context block
        suitable for injection into an LLM prompt.
        Returns empty string if no history.
        """
        history = self.get_history(last_n=last_n)
        if not history:
            return ""

        lines = ["--- PRIOR CONVERSATION CONTEXT ---"]
        for turn in history:
            flagged_text = ", ".join(
                f"{s['entity_id']} ({s['risk_level']}/{s['detected_pattern']})"
                for s in (turn["flagged_summaries"] or [])[:5]
            ) or "none"
            lines.append(
                f"Turn {turn['turn_index']}: Query='{turn['query']}' | "
                f"Intent={turn['intent_type']} | "
                f"Flagged={flagged_text}"
            )
        lines.append("--- END CONTEXT ---")
        return "\n".join(lines)

    def get_last_flagged_entity(self) -> Optional[str]:
        """
        Returns the entity_id most recently flagged with high/medium risk,
        useful for follow-up resolution ("why was that flagged?").
        """
        history = self.get_history(last_n=3)
        for turn in reversed(history):
            for summary in (turn.get("flagged_summaries") or []):
                if summary.get("risk_level") in ("high", "medium"):
                    return summary.get("entity_id")
        return None

    def get_last_entity_for_lookup(self) -> Optional[str]:
        """
        For "show me more about that customer" follow-ups:
        returns the entity_id from the last single_entity_lookup turn.
        """
        history = self.get_history(last_n=5)
        for turn in reversed(history):
            if turn["intent_type"] == "single_entity_lookup":
                sums = turn.get("flagged_summaries") or []
                if sums:
                    return sums[0].get("entity_id")
        return None


# ── Module-level convenience function ────────────────────────────────────────

def get_store(session_id: str) -> SessionMemoryStore:
    """Returns a SessionMemoryStore bound to the given session_id."""
    return SessionMemoryStore(session_id=session_id)
