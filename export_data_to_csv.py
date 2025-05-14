import sqlite3
import pandas as pd
import os

# Path to your SQLite database
db_path = 'budget.db'

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Fetch all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

# Output directory (optional - stores CSVs in a subfolder)
output_dir = 'csv_exports'
os.makedirs(output_dir, exist_ok=True)

# Export each table to CSV
for table_name_tuple in tables:
    table_name = table_name_tuple[0]
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    csv_file_path = os.path.join(output_dir, f"{table_name}.csv")
    df.to_csv(csv_file_path, index=False)
    print(f"Exported table '{table_name}' to '{csv_file_path}'")

# Close the connection
conn.close()