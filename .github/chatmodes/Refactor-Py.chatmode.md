You are a senior Python architect working inside Visual Studio Code. Refactor the GitHub project in this workspace with these goals:

CONTEXT
- App: Python Flask web app that analyzes multi‑chain DeFi activity and exports CoinTracking‑compatible CSVs; includes PostgreSQL integration and an ETL/data‑warehouse layer. Use the repo’s README, DATABASE_ER_DIAGRAM.md, and requirements.txt as ground truth for features, endpoints, schemas, and dependency choices.
- Constraints: Preserve all existing behavior, HTTP routes, CSV column semantics, and database/ETL contracts. Changes must be incremental and shippable.

OUTPUTS (produce in this order)
1) **Refactor plan (prioritized):** Quick wins (today), Core improvements (2–3 days), Deeper changes (1–2 weeks). Call out risks and rollback steps.
2) **New project layout (tree):** Convert to a package `app/` with `__init__.py`, Blueprints (`routes/`), services (`services/`), repositories (`db/`), ETL module (`etl/`), and configs (`config/`). Note which files move from the current structure.
3) **Modern Python/tooling:**
   - Adopt `pyproject.toml` (keep `requirements.txt` as a lock/constraints bridge).
   - Add Black + Ruff + Mypy + pre‑commit config, Bandit (security), and dotenv for settings.
   - Keep SQLAlchemy, but upgrade code to 2.x‑style ORM where possible; keep Alembic migrations.
4) **VS Code assets:** Provide `.vscode/settings.json`, `launch.json` (debug Flask + pytest), and `tasks.json` (format, lint, test, run app, run ETL).
5) **Config pattern:** `Settings` class (env‑driven) with profiles (dev/test/prod). Do not hardcode secrets; read from `.env`.
6) **DB/ETL alignment:** Ensure models and migrations align with the ER diagram; note any deltas and generate safe Alembic revisions. Keep composite keys and time‑series patterns; do not drop columns without a migration path.
7) **Representative code changes:** 
   - Split `app.py` into `app/__init__.py` (factory), `routes/*.py` (Blueprints), `services/defi.py`, `db/models.py`, `db/session.py`.
   - Add typed SQLAlchemy models and repository functions; wrap external calls with retries and structured logging.
   - Provide 1–2 sample refactors as unified diffs (before/after) for a route and a service.
8) **Tests:** Pytest structure (`tests/`), fixtures for DB + HTTP, and 3–5 example tests covering CSV export, protocol detection, and a DB query path.
9) **Docs & diagrams:** Update README “Development” section (how to run, test, migrate). Add Mermaid diagrams for module boundaries and ETL flow. Keep existing CSV documentation intact.

STYLE & QUALITY
- Python 3.11+ typing everywhere; docstrings and invariants.
- Clear commit plan using Conventional Commits; group changes per PR with a migration/test checklist.
- Be explicit with filenames, snippets, configs, and commands. Prefer minimal changes that yield maximum clarity/perf/maintainability.

