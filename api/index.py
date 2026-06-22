"""Vercel serverless entry point for the FastAPI application.

Vercel executes files in ``api/`` from the repository root.  The application
code lives under ``backend/``, so add that directory to Python's module path
before importing the ASGI application.
"""

from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402,F401
