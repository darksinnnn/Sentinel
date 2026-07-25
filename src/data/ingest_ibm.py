import pandas as pd
import duckdb
import os
import random
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RAW_DATA_PATH = "data/raw/HI-Small_Trans.csv"
PROCESSED_DATA_PATH = "data/processed/transactions.parquet"
METADATA_PATH = "data/processed/customers.parquet"

def ingest_and_subsample():
    """
    Ingest IBM AML dataset with per-ACCOUNT subsampling (not per-transaction).
    
    Strategy:
      - Keep 100% of accounts that have at least one illicit transaction.
      - Randomly sample 5% of the remaining (normal-only) accounts.
      - For every included account, keep ALL of its transactions.
    
    This preserves complete transaction histories for rolling-window features
    (velocity, rolling sums, sub-threshold counts, etc.) while still reducing
    the dataset to a manageable size for the hackathon.
    """
    if not os.path.exists(RAW_DATA_PATH):
        logger.warning(f"Raw data file not found at {RAW_DATA_PATH}. "
                       "Please download it from Kaggle and place it in the data/raw/ directory.")
        return

    logger.info("Subsampling data using DuckDB (per-account, preserving complete histories)...")
    conn = duckdb.connect()
    
    # Step 1: Identify which sender accounts have any illicit transactions
    # Step 2: Sample 5% of the remaining normal-only accounts
    # Step 3: Keep ALL transactions where the sender is in the included set
    query = f"""
    COPY (
        WITH raw AS (
            SELECT *, "Account" AS sender_id 
            FROM read_csv_auto('{RAW_DATA_PATH}')
        ),
        -- Accounts with at least one illicit transaction (must keep all)
        illicit_accounts AS (
            SELECT DISTINCT sender_id 
            FROM raw 
            WHERE "Is Laundering" = 1
        ),
        -- All other accounts — sample 5% of these
        normal_only_accounts AS (
            SELECT DISTINCT sender_id 
            FROM raw 
            WHERE sender_id NOT IN (SELECT sender_id FROM illicit_accounts)
            USING SAMPLE 5%
        ),
        -- Combined set of accounts to keep
        keep_accounts AS (
            SELECT sender_id FROM illicit_accounts
            UNION
            SELECT sender_id FROM normal_only_accounts
        )
        -- Keep ALL transactions for these accounts (complete histories)
        SELECT raw.* EXCLUDE (sender_id)
        FROM raw
        WHERE raw.sender_id IN (SELECT sender_id FROM keep_accounts)
    ) TO '{PROCESSED_DATA_PATH}' (FORMAT PARQUET);
    """
    try:
        conn.execute(query)
        
        # Verify results
        result = conn.execute(f"""
            SELECT 
                COUNT(*) as total_rows,
                SUM(CASE WHEN "Is Laundering" = 1 THEN 1 ELSE 0 END) as illicit_rows,
                COUNT(DISTINCT "Account") as unique_senders
            FROM read_parquet('{PROCESSED_DATA_PATH}')
        """).fetchone()
        
        logger.info(f"Subsampled transactions saved to {PROCESSED_DATA_PATH}")
        logger.info(f"  Total rows: {result[0]:,}")
        logger.info(f"  Illicit rows: {result[1]:,}")
        logger.info(f"  Normal rows: {result[0] - result[1]:,}")
        logger.info(f"  Unique sender accounts: {result[2]:,}")
        
    except Exception as e:
        logger.error(f"Failed to process data with DuckDB: {e}")
        return

    logger.info("Generating synthetic customer metadata...")
    df = pd.read_parquet(PROCESSED_DATA_PATH)
    
    # Collect ALL unique accounts (both senders and receivers)
    if 'Account' in df.columns and 'Account_1' in df.columns:
        accounts = pd.concat([df['Account'], df['Account_1']]).unique()
    else:
        logger.warning("Could not find 'Account' and 'Account_1' columns. Using fallback logic.")
        accounts = pd.concat([df.iloc[:, 2], df.iloc[:, 4]]).unique()
    
    segments = ['Retail', 'Business', 'Corporate', 'High Net Worth']
    countries = ['US', 'UK', 'CA', 'DE', 'FR', 'AE', 'SG', 'KY']
    risk_ratings = ['Low', 'Medium', 'High']
    
    metadata = []
    for acc in accounts:
        metadata.append({
            'customer_id': acc,
            'segment': random.choices(segments, weights=[0.7, 0.2, 0.08, 0.02])[0],
            'country': random.choices(countries, weights=[0.6, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05])[0],
            'kyc_risk_rating': random.choices(risk_ratings, weights=[0.8, 0.15, 0.05])[0],
            'account_age_days': random.randint(30, 3650)
        })
        
    meta_df = pd.DataFrame(metadata)
    meta_df.to_parquet(METADATA_PATH)
    logger.info(f"Generated metadata for {len(accounts)} unique accounts "
                f"(senders + receivers) saved to {METADATA_PATH}")

if __name__ == "__main__":
    ingest_and_subsample()
