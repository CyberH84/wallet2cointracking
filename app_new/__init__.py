"""
Lightweight, non-intrusive application package scaffold.

This package intentionally uses the name `app_new` to avoid
shadowing the existing top-level `app.py`. It provides a
factory and small blueprint registration so we can migrate
incrementally later.
"""
from flask import Flask


def create_app(settings=None):
    """Create and return a minimal Flask app for iterative refactor.

    This factory is intentionally small and safe: it only registers
    the lightweight blueprints in `app_new.routes`. It does not
    attempt to replace or modify the existing `app.py` runtime.
    """
    app = Flask(__name__)

    # Register minimal blueprints
    try:
        from app_new.routes.jobs import bp as jobs_bp

        app.register_blueprint(jobs_bp)
    except Exception:
        # Best-effort: don't fail creation if imports aren't available
        pass

    return app
