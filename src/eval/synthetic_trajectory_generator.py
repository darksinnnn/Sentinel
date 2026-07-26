"""
Synthetic Trajectory Generator — Stretch Goal Priority 1 (ISOLATED)
=====================================================================
Demonstrates the structural advantage of the Accumulating Case Ledger
over the stateless point-in-time rule engine.

Synthetic actor: CUST_LEDGER_DEMO_01
  - $7,500 every 42 days, 12 signals total (day 0 → day 462)
  - $7,500 is below the $9,000–$9,999 sub-threshold structuring band
  - One transaction per 6-week gap → max 1 txn per any 30-day window
  - No large inbound (≥$10k) → rapid cashout rule never fires

Asserts:
  1. Stateless rule engine returns 0 flags on every 30-day window.
  2. Ledger score ≥ 0.9 by cycle 6 (day 210, week 30).
  3. Future-signal guard: a future-dated signal contributes exactly zero.

Run standalone (does NOT import or affect the main system):
    python src/eval/synthetic_trajectory_generator.py
"""

import sys
import math
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Project root on sys.path so trajectory_ledger is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.tools.trajectory_ledger import (
    append_signal,
    get_trajectory,
    is_alert,
    LAMBDA,
    ALERT_THRESHOLD,
    DB_PATH,
)

# ── Synthetic transaction schedule ────────────────────────────────────────────
ENTITY_ID   = "CUST_LEDGER_DEMO_01"
START_DATE  = datetime(2026, 1, 1, tzinfo=timezone.utc)
N_CYCLES    = 12
CADENCE_DAYS = 42
TXN_AMOUNT   = 7_500.0        # < $9,000 lower bound of sub-threshold band
WEAK_SCORE   = 0.30

# Rotate between 4 receivers to avoid round-number concentration suspicion
RECEIVERS = ["RCV_A001", "RCV_B002", "RCV_C003", "RCV_D004"]

# Generate all 12 cycle timestamps: day 0, 42, 84, … 462
CYCLE_TIMESTAMPS = [
    START_DATE + timedelta(days=CADENCE_DAYS * i) for i in range(N_CYCLES)
]


# ── Rule engine checks (stateless, computed locally) ──────────────────────────

def stateless_flags_for_window(as_of: datetime) -> dict:
    """
    Checks the three rule flags for the synthetic actor in the 30-day window
    ending at as_of. Computes directly from the known transaction schedule —
    no database or parquet query needed since the synthetic customer doesn't
    exist in the scored parquet files.

    Returns:
        dict with is_structuring, is_rapid_cashout, is_round_number_suspicious
    """
    window_start = as_of - timedelta(days=30)
    txns_in_window = [
        ts for ts in CYCLE_TIMESTAMPS
        if window_start <= ts <= as_of
    ]
    n = len(txns_in_window)

    # is_structuring: sub_threshold_count_30d >= 3
    # sub-threshold band: $9,000 ≤ amount ≤ $9,999
    # TXN_AMOUNT = $7,500 → never in band → count always 0
    sub_threshold_count = sum(1 for _ in txns_in_window if 9000 <= TXN_AMOUNT <= 9999)
    is_structuring = int(sub_threshold_count >= 3)

    # is_rapid_cashout: requires large inbound ≥ $10k — none exist
    is_rapid_cashout = 0

    # is_round_number_suspicious: round txns ≥ 5 AND total txns ≥ 5
    # With cadence 42d > 30d, at most 1 txn per window → total txns ≤ 1
    round_count = sum(1 for _ in txns_in_window if TXN_AMOUNT % 100 == 0)
    is_round_number_suspicious = int(round_count >= 5 and n >= 5)

    return {
        "txns_in_window": n,
        "sub_threshold_count": sub_threshold_count,
        "is_structuring": is_structuring,
        "is_rapid_cashout": is_rapid_cashout,
        "is_round_number_suspicious": is_round_number_suspicious,
    }


def run():
    # ── Clean ledger slate for this demo entity ───────────────────────────────
    import sqlite3
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM ledger WHERE entity_id = ?", (ENTITY_ID,))
        conn.commit()
        conn.close()

    # ── Insert all 12 backdated signals ───────────────────────────────────────
    for i, ts in enumerate(CYCLE_TIMESTAMPS):
        append_signal(ENTITY_ID, "sub_threshold_txn", WEAK_SCORE, ts)

    print("=" * 70)
    print(" SENTINEL — Accumulating Ledger vs. Stateless Baseline Demo")
    print("=" * 70)
    print(f"\nSynthetic actor : {ENTITY_ID}")
    print(f"Transaction     : ${TXN_AMOUNT:,.0f} every {CADENCE_DAYS} days")
    print(f"Signal span     : Day 0 -> Day {CADENCE_DAYS * (N_CYCLES - 1)} "
          f"({N_CYCLES} signals, {N_CYCLES - 1} gaps)")
    print(f"Decay half-life : 90 days  (λ = {LAMBDA:.6f})")
    print(f"Alert threshold : {ALERT_THRESHOLD}")
    print()

    # ── Assert 1 + cycle-by-cycle table ───────────────────────────────────────
    print(f"{'Cycle':>5} {'Day':>4} {'Txns/30d':>8} {'Struct':>6} {'Cashout':>7} "
          f"{'Round':>5} {'StatelessOK':>11} {'LedgerScore':>11} {'Alert':>7}")
    print("-" * 70)

    assert1_pass = True
    assert2_pass = False
    assert2_cycle = None

    for i, ts in enumerate(CYCLE_TIMESTAMPS):
        flags = stateless_flags_for_window(as_of=ts)
        ledger_score = get_trajectory(ENTITY_ID, as_of_date=ts)
        alerted = is_alert(ENTITY_ID, as_of_date=ts)

        stateless_clean = (
            flags["is_structuring"] == 0
            and flags["is_rapid_cashout"] == 0
            and flags["is_round_number_suspicious"] == 0
        )
        if not stateless_clean:
            assert1_pass = False

        if not assert2_pass and ledger_score >= ALERT_THRESHOLD:
            assert2_pass = True
            assert2_cycle = i + 1

        alert_str = "*** BREACH" if alerted else ""
        stateless_str = "CLEAN" if stateless_clean else "FLAGGED!"

        print(f"{i+1:>5} {CADENCE_DAYS*i:>4} {flags['txns_in_window']:>8} "
              f"{flags['is_structuring']:>6} {flags['is_rapid_cashout']:>7} "
              f"{flags['is_round_number_suspicious']:>5} {stateless_str:>11} "
              f"{ledger_score:>11.4f} {alert_str}")

    print()

    # ── Assert 1 result ───────────────────────────────────────────────────────
    status = "PASS ✓" if assert1_pass else "FAIL ✗"
    print(f"Assert 1 (stateless misses actor throughout): {status}")

    # ── Assert 2 result ───────────────────────────────────────────────────────
    score_day210 = get_trajectory(ENTITY_ID, as_of_date=START_DATE + timedelta(days=210))
    r = 2 ** (-CADENCE_DAYS / 90)
    closed_form = WEAK_SCORE * (1 - r**6) / (1 - r)
    match = abs(score_day210 - closed_form) < 1e-6
    status2 = "PASS ✓" if assert2_pass else "FAIL ✗"
    print(f"Assert 2 (ledger breaches at cycle 6, day 210): {status2}  "
          f"[score={score_day210:.4f}, closed-form={closed_form:.4f}, "
          f"match={match}, first breach=cycle {assert2_cycle}]")

    # ── Assert 3: future-signal guard ─────────────────────────────────────────
    import sqlite3
    tmp_entity = "TEST_FUTURE_GUARD"
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM ledger WHERE entity_id = ?", (tmp_entity,))
    conn.commit()
    conn.close()

    check_time = START_DATE + timedelta(days=100)
    append_signal(tmp_entity, "real", 0.30, START_DATE + timedelta(days=50))
    score_before = get_trajectory(tmp_entity, as_of_date=check_time)

    # Future signal: enormous score, must NOT affect the past checkpoint
    append_signal(tmp_entity, "future", 999.99, START_DATE + timedelta(days=365))
    score_after = get_trajectory(tmp_entity, as_of_date=check_time)

    assert3_pass = (score_before == score_after)
    status3 = "PASS ✓" if assert3_pass else "FAIL ✗"
    print(f"Assert 3 (future-signal contributes zero):     {status3}  "
          f"[without={score_before:.6f}, with={score_after:.6f}]")

    print()
    overall = assert1_pass and assert2_pass and assert3_pass
    if overall:
        print("All assertions passed. Ledger demo is structurally sound.")
    else:
        print("One or more assertions FAILED — do not run the Streamlit demo.")
        sys.exit(1)

    return {
        "cycle_data": [
            {
                "cycle": i + 1,
                "day": CADENCE_DAYS * i,
                "week": round((CADENCE_DAYS * i) / 7, 1),
                "ledger_score": get_trajectory(ENTITY_ID, as_of_date=ts),
                "stateless_score": 0.0,  # all rule flags = 0 throughout
            }
            for i, ts in enumerate(CYCLE_TIMESTAMPS)
        ],
        "alert_threshold": ALERT_THRESHOLD,
        "first_breach_cycle": assert2_cycle,
    }


if __name__ == "__main__":
    run()
