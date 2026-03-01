# db.py
from pathlib import Path
import os

from dotenv import load_dotenv
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATHS = [
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / ".venv" / ".env",
]

for env_path in ENV_PATHS:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME") or os.getenv("MONGO_DB_NAME", "triage_db")

if not MONGODB_URI:
    raise ValueError("MONGODB_URI is not set in the environment variables")

client = None
db = None
patients_col = None
keynotes_col = None
triage_priority_col = None
_db_init_error = None


def ensure_db():
    global client, db, patients_col, keynotes_col, triage_priority_col, _db_init_error

    if client is not None:
        return db

    if _db_init_error is not None:
        raise RuntimeError(f"MongoDB initialization failed: {_db_init_error}") from _db_init_error

    try:
        client = MongoClient(
            MONGODB_URI,
            tls=True,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
        )
        db = client[DB_NAME]
        patients_col = db["patients"]
        keynotes_col = db["keyNotes"]
        triage_priority_col = db["triagePriority"]
        return db
    except Exception as exc:
        _db_init_error = exc
        raise RuntimeError(f"MongoDB initialization failed: {exc}") from exc
