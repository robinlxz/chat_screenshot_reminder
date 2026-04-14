import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# App Configuration
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false").lower() == "true"

# API Configuration
API_KEY = os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "seed-model")
BASE_URL = os.getenv("BASE_URL", "https://api.seed.com/v1")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")

# Database
DB_PATH = DATA_DIR / "app.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
