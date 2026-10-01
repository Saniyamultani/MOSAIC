import sys
from pathlib import Path

# Add backend directory and project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.main import app as fastapi_app

# Top-level FastAPI instance for Vercel Python Serverless Runtime
app = fastapi_app
