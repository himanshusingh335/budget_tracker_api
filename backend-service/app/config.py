import os

DB_PATH = "data/budget.db"
APP_TITLE = "Budget Tracker API"
APP_VERSION = "2.0.0"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = os.getenv("LOG_FILE", "app.log")
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
