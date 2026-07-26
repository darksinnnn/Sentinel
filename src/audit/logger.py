import sqlite3
import json
import logging
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("sentinel.audit")

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "audit.db"

class AuditLogger:
    """
    Append-only Hash-Chained Audit Logger using SQLite.
    Every event is stored with a SHA-256 hash of its contents combined with the previous entry's hash,
    creating a cryptographically verifiable tamper-evident chain.
    """

    def __init__(self, session_id: str = "default_session", db_path: Optional[Path] = None):
        self.session_id = session_id
        self.db_path = db_path or DB_PATH
        os.makedirs(self.db_path.parent, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    audit_ref TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    curr_hash TEXT NOT NULL
                )
            """)
            conn.commit()

    def log(self, event_type: str, payload: Dict[str, Any]) -> str:
        """
        Logs an audit event to the hash-chained SQLite table.
        Returns the unique audit reference ID.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(payload, default=str, sort_keys=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT curr_hash FROM audit_log ORDER BY rowid DESC LIMIT 1")
            row = cursor.fetchone()
            prev_hash = row[0] if row else "0" * 64

            raw_string = f"{prev_hash}|{timestamp}|{self.session_id}|{event_type}|{payload_str}"
            curr_hash = hashlib.sha256(raw_string.encode("utf-8")).hexdigest()
            audit_ref = f"AUD-{curr_hash[:8].upper()}"

            cursor.execute("""
                INSERT OR IGNORE INTO audit_log (audit_ref, session_id, timestamp, event_type, payload, prev_hash, curr_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (audit_ref, self.session_id, timestamp, event_type, payload_str, prev_hash, curr_hash))
            conn.commit()

        logger.info(f"[AUDIT LOG | {audit_ref}] {event_type}: {payload_str[:120]}...")
        return audit_ref

def log_event(event_type: str, payload: Dict[str, Any], session_id: str = "default_session") -> str:
    logger_inst = AuditLogger(session_id=session_id)
    return logger_inst.log(event_type, payload)
