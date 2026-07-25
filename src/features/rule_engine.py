import duckdb
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "data/processed/sentinel.db"
TRANSACTIONS_PARQUET = "data/processed/transactions.parquet"
CUSTOMERS_PARQUET = "data/processed/customers.parquet"

def initialize_db():
    """Initializes DuckDB and loads parquet files as views for easy querying."""
    logger.info("Initializing DuckDB connection...")
    
    # Ensure processed directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = duckdb.connect(DB_PATH)
    
    # Create views over the parquet files
    try:
        conn.execute(f"CREATE OR REPLACE VIEW transactions AS SELECT * FROM read_parquet('{TRANSACTIONS_PARQUET}')")
        conn.execute(f"CREATE OR REPLACE VIEW customers AS SELECT * FROM read_parquet('{CUSTOMERS_PARQUET}')")
        logger.info("Views for transactions and customers created successfully.")
    except Exception as e:
        logger.warning(f"Could not create views (maybe parquet files don't exist yet): {e}")
        
    return conn

def compute_features_and_baselines(conn):
    """
    Computes rule-based features and peer-group baselines.
    Features:
    - Transaction frequency (rolling count)
    - Rolling sums
    - Velocity
    - Sub-threshold frequency (<$10k)
    - Rapid cash-out signal
    - Round-number frequency
    """
    logger.info("Computing features and baselines...")
    
    try:
        # Step 1: Pre-process timestamps and extract base columns
        # Assuming IBM AML columns: "Timestamp", "Account", "Account.1" (Receiver), "Amount Paid"
        # We need a standardized timestamp for window functions
        conn.execute("""
            CREATE OR REPLACE TEMP TABLE txn_parsed AS 
            SELECT 
                "Timestamp"::TIMESTAMP AS txn_time,
                "Account" AS sender_id,
                "Account.1" AS receiver_id,
                TRY_CAST("Amount Paid" AS DOUBLE) AS amount_paid,
                "Payment Format" AS payment_format,
                "Is Laundering" AS is_laundering
            FROM transactions
        """)
        
        # Step 2: Compute sender-side 30-day rolling features
        logger.info("Computing 30-day rolling sender features...")
        conn.execute("""
            CREATE OR REPLACE TEMP TABLE sender_features AS 
            SELECT 
                sender_id,
                txn_time,
                amount_paid,
                -- 30-day rolling counts and sums
                COUNT(*) OVER w30 AS rolling_txn_count_30d,
                SUM(amount_paid) OVER w30 AS rolling_amount_30d,
                
                -- Velocity (amount per day in window)
                (SUM(amount_paid) OVER w30) / NULLIF(COUNT(*) OVER w30, 0) AS velocity_30d,
                
                -- Sub-threshold frequency (Structring hint: transactions between 9k and 10k)
                SUM(CASE WHEN amount_paid BETWEEN 9000 AND 9999 THEN 1 ELSE 0 END) OVER w30 AS sub_threshold_count_30d,
                
                -- Round-number frequency
                SUM(CASE WHEN amount_paid % 100 = 0 THEN 1 ELSE 0 END) OVER w30 AS round_number_count_30d,
                
                -- Counterparty diversity
                COUNT(DISTINCT receiver_id) OVER w30 AS unique_counterparties_30d
                
            FROM txn_parsed
            WINDOW w30 AS (
                PARTITION BY sender_id 
                ORDER BY txn_time 
                RANGE BETWEEN INTERVAL 30 DAYS PRECEDING AND CURRENT ROW
            )
        """)
        
        # Step 3: Peer-group baselining
        # We group by customer segment and account age to compute baseline means and stddevs.
        logger.info("Computing peer-group baselining...")
        conn.execute("""
            CREATE OR REPLACE TEMP TABLE peer_group_baselines AS
            SELECT 
                c.segment,
                CASE 
                    WHEN c.account_age_days < 180 THEN 'new'
                    WHEN c.account_age_days < 365 THEN 'established'
                    ELSE 'veteran'
                END AS age_tier,
                AVG(f.rolling_amount_30d) AS avg_peer_rolling_amount,
                STDDEV(f.rolling_amount_30d) AS std_peer_rolling_amount,
                AVG(f.velocity_30d) AS avg_peer_velocity,
                STDDEV(f.velocity_30d) AS std_peer_velocity
            FROM sender_features f
            JOIN customers c ON f.sender_id = c.customer_id
            GROUP BY 1, 2
        """)
        
        logger.info("Features and baselines computed successfully (stored as TEMP TABLES in memory).")
    
    except Exception as e:
        logger.error(f"Error computing features: {e}. (This is expected if the Parquet files are not yet created).")

if __name__ == "__main__":
    conn = initialize_db()
    compute_features_and_baselines(conn)
    conn.close()
