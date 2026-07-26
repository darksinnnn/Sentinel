import pandas as pd
import duckdb
import os
import random
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RAW_TRANS_PATH = "data/raw/HI-Small_Trans.csv"
RAW_ACCOUNTS_PATH = "data/raw/HI-Small_accounts.csv"
RAW_PATTERNS_PATH = "data/raw/HI-Small_Patterns.txt"

PROCESSED_TRANS_PATH = "data/processed/transactions.parquet"
PROCESSED_CUSTOMERS_PATH = "data/processed/customers.parquet"

def parse_patterns():
    logger.info("Parsing HI-Small_Patterns.txt to extract ground truth typologies...")
    records = []
    current_typology = None
    attempt_id = 0
    
    with open(RAW_PATTERNS_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("BEGIN LAUNDERING ATTEMPT"):
                try:
                    # Example: BEGIN LAUNDERING ATTEMPT - FAN-OUT:  Max 16-degree Fan-Out
                    current_typology = line.split('-')[1].split(':')[0].strip()
                except IndexError:
                    current_typology = "UNKNOWN"
                attempt_id += 1
            else:
                parts = line.split(',')
                if len(parts) >= 11:
                    records.append({
                        'Timestamp': parts[0],
                        'Account': parts[2],
                        'Account_1': parts[4],
                        # Use string formatting to avoid float precision mismatch in joins
                        'Amount_Paid_Str': parts[7],
                        'typology': current_typology,
                        'attempt_id': attempt_id
                    })
    
    df = pd.DataFrame(records)
    # Deduplicate just in case
    df = df.drop_duplicates(subset=['Timestamp', 'Account', 'Account_1', 'Amount_Paid_Str'])
    logger.info(f"Parsed {len(df)} illicit transactions with typologies.")
    return df

def parse_accounts():
    logger.info("Parsing HI-Small_accounts.csv for KYC metadata...")
    # The columns are: Bank Name, Bank ID, Account Number, Entity ID, Entity Name
    df = pd.read_csv(RAW_ACCOUNTS_PATH)
    
    # We need to map Account Number to customer_id, and infer Segment from Entity Name
    def infer_segment(name):
        name = str(name).lower()
        if 'corporation' in name:
            return 'Corporate'
        elif 'partnership' in name:
            return 'Business'
        elif 'sole proprietorship' in name:
            return 'SME'
        else:
            return 'Retail'
            
    df['segment'] = df['Entity Name'].apply(infer_segment)
    
    # Generate random countries and risk ratings but tie them persistently to the real account
    countries = ['US', 'UK', 'CA', 'DE', 'FR', 'AE', 'SG', 'KY']
    risk_ratings = ['Low', 'Medium', 'High']
    
    # Use hashing for stable deterministic randoms
    df['country'] = df['Account Number'].apply(lambda x: countries[hash(x) % len(countries)])
    df['kyc_risk_rating'] = df['Account Number'].apply(lambda x: risk_ratings[hash(x) % len(risk_ratings)])
    df['account_age_days'] = df['Account Number'].apply(lambda x: 30 + (hash(x) % 3600))
    
    df = df.rename(columns={
        'Account Number': 'customer_id',
        'Bank Name': 'bank_name',
        'Entity Name': 'entity_name'
    })
    
    return df[['customer_id', 'bank_name', 'entity_name', 'segment', 'country', 'kyc_risk_rating', 'account_age_days']]

def ingest_and_subsample():
    if not all(os.path.exists(p) for p in [RAW_TRANS_PATH, RAW_ACCOUNTS_PATH, RAW_PATTERNS_PATH]):
        logger.error("Missing raw data files in data/raw/!")
        return

    patterns_df = parse_patterns()
    conn = duckdb.connect()
    
    # Register patterns dataframe to join
    conn.register('patterns_df', patterns_df)
    
    logger.info("Subsampling transaction data and joining ground-truth typologies...")
    query = f"""
    COPY (
        WITH raw AS (
            SELECT *, "Account" AS sender_id 
            FROM read_csv_auto('{RAW_TRANS_PATH}')
        ),
        illicit_accounts AS (
            SELECT DISTINCT sender_id 
            FROM raw 
            WHERE "Is Laundering" = 1
        ),
        normal_only_accounts AS (
            SELECT DISTINCT sender_id 
            FROM raw 
            WHERE sender_id NOT IN (SELECT sender_id FROM illicit_accounts)
            USING SAMPLE 5%
        ),
        keep_accounts AS (
            SELECT sender_id FROM illicit_accounts
            UNION
            SELECT sender_id FROM normal_only_accounts
        ),
        filtered_txns AS (
            SELECT raw.* EXCLUDE (sender_id)
            FROM raw
            WHERE raw.sender_id IN (SELECT sender_id FROM keep_accounts)
        )
        SELECT 
            t.*,
            p.typology,
            p.attempt_id
        FROM filtered_txns t
        LEFT JOIN patterns_df p
            ON t."Timestamp" = p.Timestamp 
            AND t."Account" = p.Account 
            AND t."Account_1" = p.Account_1
            AND CAST(t."Amount Paid" AS VARCHAR) = p.Amount_Paid_Str
    ) TO '{PROCESSED_TRANS_PATH}' (FORMAT PARQUET);
    """
    conn.execute(query)
    
    # Verify results
    result = conn.execute(f"""
        SELECT 
            COUNT(*) as total_rows,
            SUM(CASE WHEN "Is Laundering" = 1 THEN 1 ELSE 0 END) as illicit_rows,
            SUM(CASE WHEN typology IS NOT NULL THEN 1 ELSE 0 END) as labeled_illicit_rows
        FROM read_parquet('{PROCESSED_TRANS_PATH}')
    """).fetchone()
    
    logger.info(f"Subsampled transactions saved to {PROCESSED_TRANS_PATH}")
    logger.info(f"  Total rows: {result[0]:,}")
    logger.info(f"  Illicit rows: {result[1]:,}")
    logger.info(f"  Successfully labeled illicit rows: {result[2]:,}")
    
    # Parse and save accounts
    accounts_df = parse_accounts()
    
    # We must ensure that ALL accounts present in the transactions dataset exist in customers.parquet.
    # The transactions dataset has receiver accounts that might not be in HI-Small_accounts.csv.
    logger.info("Ensuring all transaction accounts have metadata...")
    all_tx_accounts = conn.execute(f"""
        SELECT DISTINCT Account AS customer_id FROM read_parquet('{PROCESSED_TRANS_PATH}')
        UNION
        SELECT DISTINCT Account_1 AS customer_id FROM read_parquet('{PROCESSED_TRANS_PATH}')
    """).df()
    
    missing_accounts = set(all_tx_accounts['customer_id']) - set(accounts_df['customer_id'])
    if missing_accounts:
        logger.info(f"Generating synthetic metadata for {len(missing_accounts)} unmapped receiver accounts...")
        countries = ['US', 'UK', 'CA', 'DE', 'FR', 'AE', 'SG', 'KY']
        missing_df = pd.DataFrame({'customer_id': list(missing_accounts)})
        missing_df['bank_name'] = 'External Bank'
        missing_df['entity_name'] = 'External Entity'
        missing_df['segment'] = 'Retail'
        missing_df['country'] = missing_df['customer_id'].apply(lambda x: countries[hash(x) % len(countries)])
        missing_df['kyc_risk_rating'] = 'Medium'
        missing_df['account_age_days'] = missing_df['customer_id'].apply(lambda x: 30 + (hash(x) % 3600))
        accounts_df = pd.concat([accounts_df, missing_df], ignore_index=True)
    
    accounts_df.to_parquet(PROCESSED_CUSTOMERS_PATH)
    logger.info(f"Saved complete customer metadata to {PROCESSED_CUSTOMERS_PATH}")

if __name__ == "__main__":
    ingest_and_subsample()
