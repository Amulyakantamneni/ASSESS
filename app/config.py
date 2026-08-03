# app/config.py
# Central place for environment-driven configuration.

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data/dev.db")
# Railway/Heroku-style URLs come as postgres:// — SQLAlchemy's async driver needs postgresql+asyncpg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")
NOTIFY_FROM_EMAIL = os.environ.get("NOTIFY_FROM_EMAIL", "onboarding@resend.dev")

SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-insecure-secret-change-me")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

PORT = int(os.environ.get("PORT", "3000"))

AI_REPORTS_PER_DAY = int(os.environ.get("AI_REPORTS_PER_DAY", "2"))
