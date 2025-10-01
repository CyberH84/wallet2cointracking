#!/usr/bin/env python3
"""Start the Flask app using Waitress in a production-friendly way.

Usage:
  python scripts/run_production_server.py

This script imports `app.app` and runs Waitress. It is a thin wrapper
to make launching the WSGI server predictable from the repository root.
"""
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from waitress import serve
import app as application_module


def main():
    serve(application_module.app, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
