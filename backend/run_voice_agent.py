"""Entry point: starts the FastAPI server."""
import os
import sys

import uvicorn
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from app.main import app  # noqa: E402

if __name__ == "__main__":
    print("Starting Insurance Co-Pilot server...")
    print("Customer UI:  http://localhost:5173")
    print("Agent Dashboard: http://localhost:5173/dashboard")
    print("API: http://localhost:8000")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info", reload=True)
