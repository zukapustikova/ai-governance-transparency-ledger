#!/usr/bin/env python3
"""
AI Governance Transparency Ledger - Launcher Script

Starts both the FastAPI backend and Streamlit frontend.
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path


def main():
    """Launch the AI Governance Transparency Ledger application."""
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    print("=" * 60)
    print("  AI Governance Transparency Ledger - Tamper-Proof Audit Logging")
    print("=" * 60)
    print()

    processes = []

    try:
        # Start FastAPI backend
        print("[1/2] Starting FastAPI backend on http://localhost:8000")
        backend_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.api:app",
             "--host", "0.0.0.0", "--port", "8000", "--reload"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        processes.append(backend_process)

        # Wait for backend to start
        time.sleep(2)

        # Start Streamlit frontend
        print("[2/2] Starting Streamlit frontend on http://localhost:8501")
        frontend_process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "frontend/app.py",
             "--server.port", "8501", "--server.headless", "true"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        processes.append(frontend_process)

        print()
        print("=" * 60)
        print("  Application is running!")
        print()
        print("  Frontend:  http://localhost:8501")
        print("  API:       http://localhost:8000")
        print("  API Docs:  http://localhost:8000/docs")
        print()
        print("  Press Ctrl+C to stop all services")
        print("=" * 60)

        # Wait for processes
        while True:
            time.sleep(1)
            for p in processes:
                if p.poll() is not None:
                    print(f"Process exited with code {p.returncode}")
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print("\nShutting down...")
        for p in processes:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("All services stopped.")


if __name__ == "__main__":
    main()
