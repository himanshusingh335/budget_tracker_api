"""Pull the most recent S3 backup of budget.db and restore it locally.

Restores into backend-service/data/budget.db (and the run-budget-tracker-api
skill's sandbox copy, if present), then regenerates csv_exports/ from it.

Requires the aws CLI to be authenticated locally (run `aws login` first).
"""
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from export_data_to_csv import export_all_tables

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

    tables = export_all_tables(db_path=BACKEND_DB)
    print(f"Regenerated CSVs for tables: {', '.join(tables)}")


if __name__ == "__main__":
    main()
