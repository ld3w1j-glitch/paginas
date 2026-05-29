import os
from pathlib import Path
from dotenv import load_dotenv
from security_config import get_database_url, get_secret_key, normalize_database_url
from storage_service import uploads_dir

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent



class Config:
    SECRET_KEY = get_secret_key()
    SQLALCHEMY_DATABASE_URI = get_database_url(f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(uploads_dir("financeiro")))
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    MARKET_API_URL = os.environ.get("MARKET_API_URL", "")
