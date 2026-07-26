import sqlite3
import math
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "ledger.db"
HALF_LIFE_DAYS = 90
LAMBDA = math.log(2) / HALF_LIFE_DAYS
ALERT_THRESHOLD = 0.9


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            entity_id  TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            weak_score  REAL NOT NULL,
            timestamp   TEXT NOT NULL  -- ISO-8601, UTC, e.g. 2026-01-15T00:00:00+00:00
        )
    """)
    conn.commit()


def _parse(ts: str) -> datetime:
    """Single source of truth for parsing stored timestamps.
    Always returns a tz-aware UTC datetime.
    Raises ValueError if the stored string is naive (missing tzinfo).
    """
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        raise ValueError(
            f"Stored timestamp '{ts}' is naive — all timestamps must be tz-aware UTC."
        )
    return dt.astimezone(timezone.utc)


def append_signal(
    entity_id: str,
    signal_type: str,
    weak_score: float,
    timestamp: datetime,
) -> None:
    """Appends a sub-threshold signal to the entity's ledger.

    Args:
        entity_id:   The entity identifier (customer ID or account ID).
        signal_type: A label for the signal type (e.g. 'sub_threshold_txn').
        weak_score:  Individually-unremarkable risk weight (e.g. 0.30).
        timestamp:   A tz-aware UTC datetime for when the signal was observed.
                     Naive datetimes are rejected to prevent silent UTC assumptions.
    """
    if timestamp.tzinfo is None:
        raise ValueError(
            "timestamp must be tz-aware — use datetime(..., tzinfo=timezone.utc)"
        )
    ts_str = timestamp.astimezone(timezone.utc).isoformat()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    conn.execute(
        "INSERT INTO ledger (entity_id, signal_type, weak_score, timestamp) VALUES (?, ?, ?, ?)",
        (entity_id, signal_type, weak_score, ts_str),
    )
    conn.commit()
    conn.close()


def get_trajectory(entity_id: str, as_of_date: datetime | None = None) -> float:
    """Computes the exponential-decay-weighted ledger score for an entity
    as of a specific point in time.

    Contract:
        - Only signals with timestamp <= as_of_date contribute to the score.
          Signals in the future relative to as_of_date are explicitly skipped
          (delta_days < 0 → continue). This is NOT enforced in SQL to avoid
          SQLite's weak/inconsistent datetime string-comparison behaviour;
          it is enforced in Python on parsed datetime objects.
        - Decay formula: score_i * exp(-LAMBDA * delta_days_i)
          with LAMBDA = ln(2) / 90 (90-day half-life).
        - If as_of_date is None, defaults to datetime.now(UTC) (live use case).
          Historical replay requires an explicit as_of_date.

    Args:
        entity_id:   The entity to look up.
        as_of_date:  The historical or current checkpoint to evaluate as of.
                     Must be tz-aware; naive datetimes are rejected.

    Returns:
        The cumulative decayed score (float). Alert threshold: >= 0.9.
    """
    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc)
    elif as_of_date.tzinfo is None:
        raise ValueError(
            "as_of_date must be tz-aware — use datetime(..., tzinfo=timezone.utc)"
        )
    else:
        as_of_date = as_of_date.astimezone(timezone.utc)

    if not DB_PATH.exists():
        return 0.0

    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    # Fetch ALL rows for this entity — timestamp filtering happens in Python below.
    # Do NOT add a SQL timestamp comparison: SQLite has no native datetime type,
    # and string comparison on ISO-8601 strings would work here but is fragile.
    rows = conn.execute(
        "SELECT weak_score, timestamp FROM ledger WHERE entity_id = ?",
        (entity_id,),
    ).fetchall()
    conn.close()

    total = 0.0
    for weak_score, ts_str in rows:
        signal_time = _parse(ts_str)
        delta_days = (as_of_date - signal_time).total_seconds() / 86400.0
        if delta_days < 0:
            # Signal is in the future relative to as_of_date — contributes zero.
            # This is the concrete guard for Assert 3 in the verification plan:
            # a future-dated signal must be invisible to any past as_of_date query.
            continue
        total += weak_score * math.exp(-LAMBDA * delta_days)
    return total


def is_alert(entity_id: str, as_of_date: datetime | None = None) -> bool:
    """Returns True if the entity's decayed ledger score meets the alert threshold."""
    return get_trajectory(entity_id, as_of_date) >= ALERT_THRESHOLD
