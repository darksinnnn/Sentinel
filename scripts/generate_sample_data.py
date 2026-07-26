import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import random

def generate_synthetic_data():
    np.random.seed(42)
    random.seed(42)
    
    os.makedirs('data', exist_ok=True)
    
    # 1. Generate Customers
    customer_ids = [f"CUST{i:04d}" for i in range(1, 101)]
    customers_data = {
        "customer_id": customer_ids,
        "entity_name": [f"Entity {i}" for i in range(1, 101)],
        "bank_name": np.random.choice(["Global Bank", "Trust Financial", "Metro Bank", "Apex Credit"], 100),
        "country": np.random.choice(["US", "UK", "CA", "SG", "UAE"], 100, p=[0.6, 0.15, 0.1, 0.05, 0.1]),
        "segment": np.random.choice(["Retail", "Corporate", "High Net Worth"], 100, p=[0.7, 0.2, 0.1])
    }
    customers_df = pd.DataFrame(customers_data)
    customers_df.to_parquet('data/customers.parquet')
    print("Generated data/customers.parquet")
    
    # 2. Generate Base Transactions (Normal)
    today = datetime.now()
    dates = [today - timedelta(days=x) for x in range(30)]
    
    txns = []
    
    # Generate 500 normal transactions
    for _ in range(500):
        sender = np.random.choice(customer_ids)
        receiver = np.random.choice(customer_ids)
        while receiver == sender:
            receiver = np.random.choice(customer_ids)
            
        amt = round(random.uniform(50, 2000), 2)
        txn_time = np.random.choice(dates)
        
        txns.append({
            "sender_id": sender,
            "receiver_id": receiver,
            "amount_paid": amt,
            "txn_time": txn_time,
            "country": customers_df[customers_df['customer_id'] == sender]['country'].iloc[0],
            "segment": customers_df[customers_df['customer_id'] == sender]['segment'].iloc[0],
            "ml_anomaly_score": round(random.uniform(0.01, 0.2), 4),
            "risk_level": "low",
            "is_structuring": 0,
            "is_rapid_cashout": 0,
            "is_round_number_suspicious": 1 if amt % 100 == 0 else 0,
            "typology": "none",
            "amount_zscore": round(random.uniform(0.1, 0.9), 2),
            "velocity_zscore": round(random.uniform(0.1, 0.9), 2),
            "sub_threshold_count_30d": random.randint(0, 1),
            "unique_counterparties_30d": random.randint(1, 3),
            "velocity_30d": random.randint(1, 5)
        })
        
    # 3. Inject Anomalies
    
    # Anomaly 1: Structuring / Smurfing (Target: CUST0099)
    smurf = "CUST0099"
    for _ in range(12): # 12 transactions just under $10,000 threshold
        receiver = np.random.choice(customer_ids[:50])
        amt = round(random.uniform(9500, 9999), 2)
        txns.append({
            "sender_id": smurf,
            "receiver_id": receiver,
            "amount_paid": amt,
            "txn_time": today - timedelta(days=random.randint(1, 5)),
            "country": "US",
            "segment": "Retail",
            "ml_anomaly_score": round(random.uniform(0.85, 0.95), 4),
            "risk_level": "high",
            "is_structuring": 1,
            "is_rapid_cashout": 0,
            "is_round_number_suspicious": 0,
            "typology": "structuring",
            "amount_zscore": 2.5,
            "velocity_zscore": 3.1,
            "sub_threshold_count_30d": 12,
            "unique_counterparties_30d": 12,
            "velocity_30d": 12
        })
        
    # Anomaly 2: Layering / U-Turn Cycle (CUST0090 -> CUST0091 -> CUST0092 -> CUST0090)
    cycle_nodes = ["CUST0090", "CUST0091", "CUST0092", "CUST0090"]
    for i in range(len(cycle_nodes)-1):
        txns.append({
            "sender_id": cycle_nodes[i],
            "receiver_id": cycle_nodes[i+1],
            "amount_paid": 50000.0,
            "txn_time": today - timedelta(days=3-i),
            "country": "CA",
            "segment": "Corporate",
            "ml_anomaly_score": round(random.uniform(0.9, 0.98), 4),
            "risk_level": "high",
            "is_structuring": 0,
            "is_rapid_cashout": 0,
            "is_round_number_suspicious": 1,
            "typology": "layering",
            "amount_zscore": 4.1,
            "velocity_zscore": 1.5,
            "sub_threshold_count_30d": 0,
            "unique_counterparties_30d": 5,
            "velocity_30d": 2
        })
        
    # Anomaly 3: Rapid Cashout (CUST0080 receives big amount then sends to multiple instantly)
    txns.append({
            "sender_id": "CUST0001",
            "receiver_id": "CUST0080",
            "amount_paid": 100000.0,
            "txn_time": today - timedelta(days=1, hours=2),
            "country": "UK",
            "segment": "Retail",
            "ml_anomaly_score": 0.4,
            "risk_level": "medium",
            "is_structuring": 0,
            "is_rapid_cashout": 0,
            "is_round_number_suspicious": 1,
            "typology": "none",
            "amount_zscore": 3.0,
            "velocity_zscore": 1.0,
            "sub_threshold_count_30d": 0,
            "unique_counterparties_30d": 2,
            "velocity_30d": 1
    })
    for _ in range(5):
        txns.append({
            "sender_id": "CUST0080",
            "receiver_id": np.random.choice(customer_ids[:20]),
            "amount_paid": 19500.0,
            "txn_time": today - timedelta(days=1, hours=1), # Happens 1 hour after receiving
            "country": "UK",
            "segment": "Retail",
            "ml_anomaly_score": 0.92,
            "risk_level": "high",
            "is_structuring": 0,
            "is_rapid_cashout": 1,
            "is_round_number_suspicious": 1,
            "typology": "rapid_cashout",
            "amount_zscore": 2.1,
            "velocity_zscore": 4.5,
            "sub_threshold_count_30d": 0,
            "unique_counterparties_30d": 5,
            "velocity_30d": 6
        })
        
    # Anomaly 4: Target specifically 8000EBD30 from the benchmark queries
    # Make sure this entity exists in customers
    customers_df.loc[0, 'customer_id'] = "8000EBD30"
    customers_df.to_parquet('data/customers.parquet')
    
    for _ in range(3):
        txns.append({
            "sender_id": "8000EBD30",
            "receiver_id": np.random.choice(customer_ids),
            "amount_paid": 7500.0,
            "txn_time": today - timedelta(days=1),
            "country": "US",
            "segment": "Retail",
            "ml_anomaly_score": 0.88,
            "risk_level": "high",
            "is_structuring": 1,
            "is_rapid_cashout": 0,
            "is_round_number_suspicious": 0,
            "typology": "structuring",
            "amount_zscore": 1.5,
            "velocity_zscore": 2.5,
            "sub_threshold_count_30d": 5,
            "unique_counterparties_30d": 3,
            "velocity_30d": 5
        })

    ml_scored_df = pd.DataFrame(txns)
    ml_scored_df['txn_time'] = pd.to_datetime(ml_scored_df['txn_time'])
    ml_scored_df.to_parquet('data/ml_scored.parquet')
    print(f"Generated data/ml_scored.parquet with {len(ml_scored_df)} rows")
    
    # 4. Generate sample_upload.csv for custom upload testing
    upload_txns = []
    
    # Structuring pattern (Sub-threshold)
    for i in range(10):
        upload_txns.append({
            "sender_id": "UPL_CUST_1",
            "receiver_id": f"UPL_RCV_{i}",
            "amount_paid": 9900.0,
            "txn_time": (today - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        })
        
    # Layering (U-Turn Cycle)
    cycle = ["UPL_CUST_2", "UPL_CUST_3", "UPL_CUST_4", "UPL_CUST_2"]
    for i in range(len(cycle)-1):
        upload_txns.append({
            "sender_id": cycle[i],
            "receiver_id": cycle[i+1],
            "amount_paid": 25000.0,
            "txn_time": (today - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        })
        
    # Normal noise
    for i in range(20):
        upload_txns.append({
            "sender_id": f"UPL_CUST_{random.randint(10, 20)}",
            "receiver_id": f"UPL_RCV_{random.randint(10, 20)}",
            "amount_paid": round(random.uniform(100, 2000), 2),
            "txn_time": (today - timedelta(days=random.randint(3, 10))).strftime("%Y-%m-%d %H:%M:%S")
        })
        
    upload_df = pd.DataFrame(upload_txns)
    upload_df.to_csv('data/sample_upload.csv', index=False)
    print("Generated data/sample_upload.csv")

if __name__ == "__main__":
    generate_synthetic_data()
