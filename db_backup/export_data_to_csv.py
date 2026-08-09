import sqlite3
import pandas as pd
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "backend-service" / "data" / "budget.db"
OUTPUT_DIR = REPO_ROOT / "csv_exports"


def export_all_tables(db_path: Path = DB_PATH, output_dir: Path = OUTPUT_DIR) -> list[str]:
    """Export every table in the SQLite DB at db_path to a CSV in output_dir.

    Returns the list of table names exported.
    """
    os.makedirs(output_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        for table_name in tables:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            csv_file_path = os.path.join(output_dir, f"{table_name}.csv")
            df.to_csv(csv_file_path, index=False)
            print(f"Exported table '{table_name}' to '{csv_file_path}'")

        return tables
    finally:
        conn.close()


if __name__ == "__main__":
    export_all_tables()
