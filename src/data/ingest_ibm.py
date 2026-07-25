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
    if not os.path.exists(RAW_DATA_PATH):
        logger.warning(f"Raw data file not found at {RAW_DATA_PATH}. Please download it from Kaggle and place it in the data/raw/ directory.")
        return

    logger.info("Subsampling data using DuckDB...")
    conn = duckdb.connect()
    
    # Stratified subsampling: Keep all laundering (1) and sample normal (0) at 5%.
    # Note: Column names based on IBM AML dataset.
    query = f"""
    COPY (
        SELECT * FROM read_csv_auto('{RAW_DATA_PATH}') WHERE "Is Laundering" = 1
        UNION ALL
        SELECT * FROM read_csv_auto('{RAW_DATA_PATH}') WHERE "Is Laundering" = 0 USING SAMPLE 5%
    ) TO '{PROCESSED_DATA_PATH}' (FORMAT PARQUET);
    """
    try:
        conn.execute(query)
        logger.info(f"Subsampled transactions saved to {PROCESSED_DATA_PATH}")
    except Exception as e:
        logger.error(f"Failed to process data with DuckDB: {e}")
        return

    logger.info("Generating synthetic customer metadata...")
    df = pd.read_parquet(PROCESSED_DATA_PATH)
    
    # DuckDB renames the duplicate 'Account' column to 'Account_1'
    if 'Account' in df.columns and 'Account_1' in df.columns:
        accounts = pd.concat([df['Account'], df['Account_1']]).unique()
    else:
        logger.warning("Could not find 'Account' and 'Account.1' columns. Using fallback logic.")
        # Fallback if columns differ
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
    logger.info(f"Generated metadata for {len(accounts)} unique accounts saved to {METADATA_PATH}")

if __name__ == "__main__":
    ingest_and_subsample()
