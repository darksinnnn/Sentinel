"""
Sentinel Rule Engine — Feature Engineering & Peer-group Baselining

Computes the FULL feature set from the architecture doc (§5.3):
  1. Rolling txn count (30d)
  2. Rolling amount sum (30d)  
  3. Velocity (amount / count)
  4. Sub-threshold frequency (<$10k, structuring hint)
  5. Round-number frequency
  6. Counterparty diversity
  7. In/out ratio (sent vs received)
  8. Amount deviation from peer baseline (z-score)
  9. Rapid cash-out signal (time delta between large inbound and next outbound)

Also computes:
  - Peer-group baselines (by segment + account age tier)
  - Per-account deviation scores (z-scores against peer baselines)
  - Boolean typology flags (is_structuring, is_rapid_cashout)
"""
import duckdb
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "data/processed/sentinel.db"
TRANSACTIONS_PARQUET = "data/processed/transactions.parquet"
CUSTOMERS_PARQUET = "data/processed/customers.parquet"

# Output paths for the computed tables
FEATURES_PARQUET = "data/processed/sender_features.parquet"
RECEIVER_FEATURES_PARQUET = "data/processed/receiver_features.parquet"
PEER_BASELINES_PARQUET = "data/processed/peer_baselines.parquet"
SCORED_FEATURES_PARQUET = "data/processed/scored_features.parquet"


def initialize_db():
    """Initializes DuckDB and loads parquet files as views for easy querying."""
    logger.info("Initializing DuckDB connection...")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = duckdb.connect(DB_PATH)
    
    try:
        conn.execute(f"CREATE OR REPLACE VIEW transactions AS SELECT * FROM read_parquet('{TRANSACTIONS_PARQUET}')")
        conn.execute(f"CREATE OR REPLACE VIEW customers AS SELECT * FROM read_parquet('{CUSTOMERS_PARQUET}')")
        logger.info("Views for transactions and customers created successfully.")
    except Exception as e:
        logger.warning(f"Could not create views (maybe parquet files don't exist yet): {e}")
        
    return conn


def compute_features_and_baselines(conn):
    """
    Computes the full feature set, peer baselines, deviation scores,
    and typology flags. Persists results to Parquet.
    """
    logger.info("Starting feature computation pipeline...")

    # ── Step 1: Parse timestamps and standardize columns ──────────────
    logger.info("Step 1/7: Parsing timestamps...")
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE txn_parsed AS 
        SELECT 
            "Timestamp"::TIMESTAMP AS txn_time,
            "Account" AS sender_id,
            "Account_1" AS receiver_id,
            TRY_CAST("Amount Paid" AS DOUBLE) AS amount_paid,
            TRY_CAST("Amount Received" AS DOUBLE) AS amount_received,
            "Payment Format" AS payment_format,
            "Is Laundering" AS is_laundering
        FROM transactions
    """)
    
    row_count = conn.execute("SELECT COUNT(*) FROM txn_parsed").fetchone()[0]
    logger.info(f"  Parsed {row_count:,} transactions.")

    # ── Step 2: Sender-side 30-day rolling features ───────────────────
    logger.info("Step 2/7: Computing 30-day rolling sender features...")
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE sender_features AS 
        SELECT 
            sender_id,
            txn_time,
            receiver_id,
            amount_paid,
            payment_format,
            is_laundering,
            
            -- Rolling counts and sums
            COUNT(*) OVER w30 AS rolling_txn_count_30d,
            SUM(amount_paid) OVER w30 AS rolling_amount_30d,
            
            -- Velocity (avg amount per txn in window)
            (SUM(amount_paid) OVER w30) / NULLIF(COUNT(*) OVER w30, 0) AS velocity_30d,
            
            -- Sub-threshold frequency (structuring hint: $9k-$9,999)
            SUM(CASE WHEN amount_paid BETWEEN 9000 AND 9999 THEN 1 ELSE 0 END) OVER w30 
                AS sub_threshold_count_30d,
            
            -- Round-number frequency
            SUM(CASE WHEN amount_paid > 0 AND amount_paid % 100 = 0 THEN 1 ELSE 0 END) OVER w30 
                AS round_number_count_30d,
            
            -- Counterparty diversity
            COUNT(DISTINCT receiver_id) OVER w30 AS unique_counterparties_30d
            
        FROM txn_parsed
        WINDOW w30 AS (
            PARTITION BY sender_id 
            ORDER BY txn_time 
            RANGE BETWEEN INTERVAL 30 DAYS PRECEDING AND CURRENT ROW
        )
    """)
    logger.info("  Sender features computed.")

    # ── Step 3: Receiver-side features (for in/out ratio) ─────────────
    logger.info("Step 3/7: Computing receiver-side aggregates for in/out ratio...")
    # Pre-aggregate to one row per (receiver, day) to prevent join fan-out.
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE receiver_daily AS
        WITH receiver_rolling AS (
            SELECT 
                receiver_id,
                txn_time,
                SUM(amount_received) OVER w30 AS rolling_amount_received_30d
            FROM txn_parsed
            WINDOW w30 AS (
                PARTITION BY receiver_id 
                ORDER BY txn_time 
                RANGE BETWEEN INTERVAL 30 DAYS PRECEDING AND CURRENT ROW
            )
        ),
        -- Deduplicate: one row per (receiver, day) — take the latest snapshot
        ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY receiver_id, txn_time::DATE 
                    ORDER BY txn_time DESC
                ) AS rn
            FROM receiver_rolling
        )
        SELECT receiver_id, txn_time::DATE AS txn_date, rolling_amount_received_30d
        FROM ranked
        WHERE rn = 1
    """)
    
    # Join in/out ratio onto sender features (guaranteed 1:1 via daily dedup)
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE sender_features_v2 AS
        SELECT 
            s.*,
            s.rolling_amount_30d / NULLIF(
                COALESCE(r.rolling_amount_received_30d, 0), 0
            ) AS in_out_ratio_30d
        FROM sender_features s
        LEFT JOIN receiver_daily r 
            ON s.sender_id = r.receiver_id 
            AND s.txn_time::DATE = r.txn_date
    """)
    logger.info("  In/out ratio computed.")

    # ── Step 4: Rapid cash-out signal ─────────────────────────────────
    logger.info("Step 4/7: Computing rapid cash-out signal...")
    # Use a window-based approach: for each account, track the most recent
    # inbound timestamp and compute the delta. This avoids self-joins that
    # cause row duplication.
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE cashout_enriched AS
        WITH all_events AS (
            -- Unify inbound and outbound into a single timeline per account
            SELECT sender_id AS account_id, txn_time, amount_paid, 0 AS amount_in, 'OUT' AS direction
            FROM txn_parsed WHERE amount_paid > 0
            UNION ALL
            SELECT receiver_id AS account_id, txn_time, 0 AS amount_paid, amount_received AS amount_in, 'IN' AS direction
            FROM txn_parsed WHERE amount_received > 0
        ),
        with_last_inbound AS (
            SELECT 
                account_id,
                txn_time,
                direction,
                amount_paid,
                amount_in,
                -- For each row, find the most recent inbound event timestamp (including current)
                MAX(CASE WHEN direction = 'IN' THEN txn_time ELSE NULL END) 
                    OVER (PARTITION BY account_id ORDER BY txn_time 
                          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) 
                    AS last_inbound_time
            FROM all_events
        ),
        -- Deduplicate: one row per (account, outbound_time) - pick shortest delta
        deduped AS (
            SELECT 
                account_id,
                txn_time AS outbound_time,
                EXTRACT(EPOCH FROM (txn_time - last_inbound_time)) / 3600.0 AS cashout_hours_delta,
                ROW_NUMBER() OVER (
                    PARTITION BY account_id, txn_time 
                    ORDER BY (txn_time - last_inbound_time) ASC
                ) AS rn
            FROM with_last_inbound
            WHERE direction = 'OUT'
              AND last_inbound_time IS NOT NULL
              AND txn_time - last_inbound_time <= INTERVAL 7 DAYS
        )
        SELECT account_id, outbound_time, cashout_hours_delta
        FROM deduped WHERE rn = 1
    """)
    
    # Join rapid cash-out signal onto sender features (1:1 guaranteed)
    conn.execute("""
        CREATE OR REPLACE TEMP TABLE sender_features_v3 AS
        SELECT 
            s.*,
            c.cashout_hours_delta,
            -- Flag: rapid cash-out if outbound within 24 hours of large inbound
            CASE WHEN c.cashout_hours_delta IS NOT NULL AND c.cashout_hours_delta < 24 
                 THEN 1 ELSE 0 END AS is_rapid_cashout
        FROM sender_features_v2 s
        LEFT JOIN cashout_enriched c 
            ON s.sender_id = c.account_id 
            AND s.txn_time = c.outbound_time
    """)
    logger.info("  Rapid cash-out signal computed.")

    # ── Step 5: Peer-group baselines ──────────────────────────────────
    logger.info("Step 5/7: Computing peer-group baselines...")
    conn.execute(f"""
        CREATE OR REPLACE TABLE peer_group_baselines AS
        SELECT 
            c.segment,
            CASE 
                WHEN c.account_age_days < 180 THEN 'new'
                WHEN c.account_age_days < 365 THEN 'established'
                ELSE 'veteran'
            END AS age_tier,
            
            -- Amount baselines
            AVG(f.rolling_amount_30d) AS avg_peer_rolling_amount,
            STDDEV(f.rolling_amount_30d) AS std_peer_rolling_amount,
            
            -- Velocity baselines
            AVG(f.velocity_30d) AS avg_peer_velocity,
            STDDEV(f.velocity_30d) AS std_peer_velocity,
            
            -- Transaction count baselines
            AVG(f.rolling_txn_count_30d) AS avg_peer_txn_count,
            STDDEV(f.rolling_txn_count_30d) AS std_peer_txn_count,
            
            -- Counterparty baselines
            AVG(f.unique_counterparties_30d) AS avg_peer_counterparties,
            STDDEV(f.unique_counterparties_30d) AS std_peer_counterparties,
            
            -- Peer count for confidence
            COUNT(DISTINCT f.sender_id) AS peer_account_count
            
        FROM sender_features_v3 f
        JOIN customers c ON f.sender_id = c.customer_id
        GROUP BY 1, 2
    """)
    
    # Persist baselines
    conn.execute(f"COPY peer_group_baselines TO '{PEER_BASELINES_PARQUET}' (FORMAT PARQUET)")
    logger.info("  Peer-group baselines computed and saved.")

    # ── Step 6: Deviation scores (z-scores against peer baselines) ────
    logger.info("Step 6/7: Computing deviation scores and typology flags...")
    conn.execute(f"""
        CREATE OR REPLACE TABLE scored_features AS
        SELECT 
            f.sender_id,
            f.txn_time,
            f.receiver_id,
            f.amount_paid,
            f.payment_format,
            f.is_laundering,
            
            -- Raw features
            f.rolling_txn_count_30d,
            f.rolling_amount_30d,
            f.velocity_30d,
            f.sub_threshold_count_30d,
            f.round_number_count_30d,
            f.unique_counterparties_30d,
            f.in_out_ratio_30d,
            f.cashout_hours_delta,
            f.is_rapid_cashout,
            
            -- Peer context
            c.segment,
            CASE 
                WHEN c.account_age_days < 180 THEN 'new'
                WHEN c.account_age_days < 365 THEN 'established'
                ELSE 'veteran'
            END AS age_tier,
            c.country,
            c.kyc_risk_rating,
            
            -- Z-scores: how far this account's behavior deviates from its peer group
            (f.rolling_amount_30d - p.avg_peer_rolling_amount) 
                / NULLIF(p.std_peer_rolling_amount, 0) AS amount_zscore,
            (f.velocity_30d - p.avg_peer_velocity) 
                / NULLIF(p.std_peer_velocity, 0) AS velocity_zscore,
            (f.rolling_txn_count_30d - p.avg_peer_txn_count) 
                / NULLIF(p.std_peer_txn_count, 0) AS txn_count_zscore,
            (f.unique_counterparties_30d - p.avg_peer_counterparties) 
                / NULLIF(p.std_peer_counterparties, 0) AS counterparty_zscore,
            
            -- Typology flags (boolean risk signals)
            CASE WHEN f.sub_threshold_count_30d >= 3 THEN 1 ELSE 0 END AS is_structuring,
            CASE WHEN f.round_number_count_30d >= 5 
                  AND f.rolling_txn_count_30d >= 5 
                 THEN 1 ELSE 0 END AS is_round_number_suspicious,
            
            -- Peer baseline values (for explainability)
            p.avg_peer_rolling_amount,
            p.avg_peer_velocity,
            p.peer_account_count
            
        FROM sender_features_v3 f
        JOIN customers c ON f.sender_id = c.customer_id
        LEFT JOIN peer_group_baselines p 
            ON c.segment = p.segment
            AND (CASE 
                    WHEN c.account_age_days < 180 THEN 'new'
                    WHEN c.account_age_days < 365 THEN 'established'
                    ELSE 'veteran'
                END) = p.age_tier
    """)
    
    # Persist scored features
    conn.execute(f"COPY scored_features TO '{SCORED_FEATURES_PARQUET}' (FORMAT PARQUET)")
    
    # Also persist raw sender features for ML consumption
    conn.execute(f"COPY (SELECT * FROM sender_features_v3) TO '{FEATURES_PARQUET}' (FORMAT PARQUET)")
    
    # Summary stats
    total = conn.execute("SELECT COUNT(*) FROM scored_features").fetchone()[0]
    structuring = conn.execute("SELECT COUNT(*) FROM scored_features WHERE is_structuring = 1").fetchone()[0]
    cashout = conn.execute("SELECT COUNT(*) FROM scored_features WHERE is_rapid_cashout = 1").fetchone()[0]
    
    logger.info(f"  Scored features saved to {SCORED_FEATURES_PARQUET}")
    logger.info(f"  Total rows: {total:,}")
    logger.info(f"  Structuring flags: {structuring:,}")
    logger.info(f"  Rapid cash-out flags: {cashout:,}")

    # ── Step 7: Verify data quality ───────────────────────────────────
    logger.info("Step 7/7: Verification checks...")
    
    # Check that z-scores are populated
    null_zscores = conn.execute(
        "SELECT COUNT(*) FROM scored_features WHERE amount_zscore IS NULL"
    ).fetchone()[0]
    logger.info(f"  Rows with NULL amount_zscore: {null_zscores:,} (expected for accounts not in metadata)")
    
    # Check feature distributions
    dist = conn.execute("""
        SELECT 
            AVG(rolling_txn_count_30d) AS avg_txn_count,
            AVG(velocity_30d) AS avg_velocity,
            AVG(sub_threshold_count_30d) AS avg_sub_threshold,
            AVG(unique_counterparties_30d) AS avg_counterparties
        FROM scored_features
    """).fetchone()
    logger.info(f"  Avg txn count: {dist[0]:.1f}, avg velocity: {dist[1]:.1f}, "
                f"avg sub_threshold: {dist[2]:.2f}, avg counterparties: {dist[3]:.1f}")
    
    logger.info("Feature computation pipeline complete.")


if __name__ == "__main__":
    conn = initialize_db()
    compute_features_and_baselines(conn)
    conn.close()
