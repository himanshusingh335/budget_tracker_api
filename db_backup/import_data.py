import csv
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_NAME = REPO_ROOT / "backend-service" / "data" / "budget.db"
CSV_DIR = REPO_ROOT / "csv_exports"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS budget_tracker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Date TEXT,
                Description TEXT,
                Category TEXT,
                Expenditure REAL,
                Year INT,
                Month INT,
                Day INT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS budget_set (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                MonthYear TEXT,
                Category TEXT,
                Budget REAL
            )
        ''')

def import_budget_set(csv_file):
    with sqlite3.connect(DB_NAME) as conn:
        with open(csv_file, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                conn.execute('''
                    INSERT INTO budget_set (MonthYear, Category, Budget)
                    VALUES (?, ?, ?)
                ''', (row["MonthYear"], row["Category"], float(row["Budget"])))
    print("✅ budget_set imported.")

def import_budget_tracker(csv_file):
    with sqlite3.connect(DB_NAME) as conn:
        with open(csv_file, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                conn.execute('''
                    INSERT INTO budget_tracker (Date, Description, Category, Expenditure, Year, Month, Day)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row["Date"],
                    row["Description"],
                    row["Category"],
                    float(row["Expenditure"]),
                    int(float(row["Year"])),
                    int(float(row["Month"])),
                    int(float(row["Day"]))
                ))
    print("✅ budget_tracker imported.")

if __name__ == "__main__":
    init_db()
    import_budget_set(CSV_DIR / "budget_set.csv")
    import_budget_tracker(CSV_DIR / "budget_tracker.csv")
