"""Pull the most recent S3 backup of budget.db and restore it locally.

Not a disaster-recovery tool for the Pi (it keeps its own Docker volume) —
this is for pulling down the latest prod data snapshot to test against
locally. Restores into backend-service/data/budget.db (and the
run-budget-tracker-api skill's sandbox copy, if present), then regenerates
db_backup/csv_exports/ from it.

Requires the aws CLI to be authenticated locally (run `aws login` first).
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
S3_BUCKET = "budget-tracker-backups-358625410597"
S3_PREFIX = "backups/"
BACKEND_DB = REPO_ROOT / "backend-service" / "data" / "budget.db"
SANDBOX_DB = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "run-budget-tracker-api"
    / ".sandbox"
    / "data"
    / "budget.db"
)
CSV_OUTPUT_DIR = Path(__file__).resolve().parent / "csv_exports"


def run_aws(args: list[str]) -> str:
    result = subprocess.run(
        ["aws", *args], capture_output=True, text=True
    )
    if result.returncode != 0:
        if "expired" in result.stderr.lower() or "reauthenticate" in result.stderr.lower():
            sys.exit(f"aws CLI session expired — run `aws login` first.\n{result.stderr.strip()}")
        sys.exit(f"aws command failed: {' '.join(args)}\n{result.stderr.strip()}")
    return result.stdout


def latest_backup_prefix() -> str:
    output = run_aws(["s3", "ls", f"s3://{S3_BUCKET}/{S3_PREFIX}"])
    prefixes = [
        line.split()[-1]
        for line in output.splitlines()
        if line.strip().startswith("PRE ") and "backup_" in line
    ]
    if not prefixes:
        sys.exit(f"No backups found under s3://{S3_BUCKET}/{S3_PREFIX}")
    return sorted(prefixes)[-1]


def export_csvs(db_path: Path, output_dir: Path) -> list[str]:
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

        return tables
    finally:
        conn.close()


def main():
    prefix = latest_backup_prefix()
    s3_uri = f"s3://{S3_BUCKET}/{S3_PREFIX}{prefix}budget.db"
    print(f"Latest backup: {s3_uri}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        downloaded_db = Path(tmp_dir) / "budget.db"
        run_aws(["s3", "cp", s3_uri, str(downloaded_db)])
        print(f"Downloaded to {downloaded_db}")

        if BACKEND_DB.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKEND_DB.with_name(f"budget.db.bak-{timestamp}")
            shutil.copy2(BACKEND_DB, backup_path)
            print(f"Backed up existing DB to {backup_path}")

        BACKEND_DB.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(downloaded_db, BACKEND_DB)
        print(f"Restored {BACKEND_DB}")

        if SANDBOX_DB.exists():
            shutil.copy2(downloaded_db, SANDBOX_DB)
            print(f"Restored {SANDBOX_DB}")
        else:
            print(f"Skipped sandbox copy (not found at {SANDBOX_DB})")

    tables = export_csvs(BACKEND_DB, CSV_OUTPUT_DIR)
    print(f"Regenerated CSVs in {CSV_OUTPUT_DIR} for tables: {', '.join(tables)}")


if __name__ == "__main__":
    main()
