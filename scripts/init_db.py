import sys
import os

# Add the project root to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import init_db
from src.config import DATA_DIR, UPLOAD_DIR

if __name__ == "__main__":
    print(f"Ensuring directories exist:\n  - {DATA_DIR}\n  - {UPLOAD_DIR}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Initializing SQLite database...")
    init_db()
    print("Database initialized successfully.")
