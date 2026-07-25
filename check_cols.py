import duckdb
import pandas as pd

print("Pandas Columns:")
df_pd = pd.read_csv('data/raw/HI-Small_Trans.csv', nrows=1)
print(df_pd.columns)

print("\nDuckDB Columns:")
conn = duckdb.connect()
df_db = conn.execute("SELECT * FROM read_csv_auto('data/raw/HI-Small_Trans.csv') LIMIT 1").df()
print(df_db.columns)
