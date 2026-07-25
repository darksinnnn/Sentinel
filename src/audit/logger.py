import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger("sentinel.audit")

class AuditLogger:
    """
    Append-only Audit Logger Interface.
    Phase 2: Logs audit events to console/logger.
    Phase 3: Will write hash-chained records to SQLite audit trail table.
    """

    def __init__(self, session_id: str = "default_session"):
        self.session_id = session_id

    def log(self, event_type: str, payload: Dict[str, Any]) -> str:
        """
        Logs an audit event.
        Returns a mock/stub audit reference ID.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        audit_entry = {
            "session_id": self.session_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "payload": payload
        }
        
        audit_ref = f"AUD-{hash(timestamp + event_type) & 0xFFFFFFFF:08x}"
        logger.info(f"[AUDIT LOG | {audit_ref}] {event_type}: {json.dumps(payload, default=str)}")
        
        return audit_ref

# Global default logger instance helper
_default_logger = AuditLogger()

def log_event(event_type: str, payload: Dict[str, Any], session_id: str = "default_session") -> str:
    logger_inst = AuditLogger(session_id=session_id)
    return logger_inst.log(event_type, payload)
