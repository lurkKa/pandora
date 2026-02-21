import sys
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pa_wsgi")

# Set project home to current directory
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set working directory (crucial for SQLite and JSON files)
os.chdir(project_home)

# Allow CORS from PythonAnywhere domain (set BEFORE importing main.py)
if not os.environ.get("PANDORA_CORS_ORIGIN_REGEX"):
    os.environ["PANDORA_CORS_ORIGIN_REGEX"] = (
        r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+"
        r"|[\w-]+\.pythonanywhere\.com)(:\d+)?$"
    )

logger.info("Importing main module...")

# Tell main.py to skip async startup event (we init DB synchronously below)
os.environ["PANDORA_SKIP_STARTUP"] = "1"

# PythonAnywhere usually runs a single web worker; keep request latency predictable.
os.environ.setdefault("PANDORA_LOW_RESOURCE_MODE", "1")
os.environ.setdefault("PANDORA_RUNNER_TIMEOUT_S", "4.5")
os.environ.setdefault("PANDORA_DOCKER_RUN_TIMEOUT_S", "1.5")
os.environ.setdefault("PANDORA_RUNNER_CONCURRENCY", "1")
os.environ.setdefault("PANDORA_SQLITE_TIMEOUT_S", "6")
os.environ.setdefault("PANDORA_SQLITE_BUSY_TIMEOUT_MS", "2500")
os.environ.setdefault("PANDORA_AUTH_TRACE", "1")
os.environ.setdefault("PANDORA_STATELESS_AUTH", "1")

# Import FastAPI app and pre-initialize DB
from main import app as application_asgi, init_db

# Pre-init everything synchronously (replaces the async _startup() that hangs via a2wsgi)
logger.info("Pre-initializing...")
try:
    import secrets as _secrets
    from pathlib import Path as _Path

    # JWT secret (same logic as _startup)
    import main as _main_mod
    if not _main_mod.JWT_SECRET:
        secret_file = os.getenv("PANDORA_JWT_SECRET_FILE", ".pandora_jwt_secret")
        secret_path = _Path(secret_file)
        if secret_path.exists():
            _main_mod.JWT_SECRET = secret_path.read_text(encoding="utf-8").strip()
        else:
            _main_mod.JWT_SECRET = _secrets.token_urlsafe(48)
            secret_path.write_text(_main_mod.JWT_SECRET, encoding="utf-8")
        logger.info("JWT secret loaded.")

    init_db()
    logger.info("Database ready.")
except Exception as e:
    logger.error("Pre-init failed: %s", e)
    import traceback; traceback.print_exc()

# Import WSGI Adapter
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(application_asgi)
    logger.info("WSGI application ready.")
except ImportError:
    raise ImportError("Please run 'pip install a2wsgi' to use this adapter.")
