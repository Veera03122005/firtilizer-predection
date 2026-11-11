import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Normalize DATABASE_URL for Render PostgreSQL (postgres:// -> postgresql://)
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "smart-fertilizer-advisor-secret-key-prod-3122005")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")
    SQLALCHEMY_DATABASE_URI = db_url or f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
    LLM_TIMEOUT_S = int(os.getenv("LLM_TIMEOUT_S", "15"))
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    # RAG
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
    RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.55"))
    RAG_MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "4000"))

    # Integrations
    WEATHER_TIMEOUT_S = int(os.getenv("WEATHER_TIMEOUT_S", "8"))
    RATELIMIT_CHAT = os.getenv("RATELIMIT_CHAT", "10 per minute")
    PDF_FONT_DIR = os.getenv("PDF_FONT_DIR", "static/fonts")

    WTF_CSRF_ENABLED = True


class DevConfig(BaseConfig):
    FLASK_DEBUG = True


class TestConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key-for-testing-only"

