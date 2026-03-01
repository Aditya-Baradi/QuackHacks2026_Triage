import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
OUTPUTS_DIR = BACKEND_DIR / "outputs"
TMP_DIR = BACKEND_DIR / "tmp"
