# Development

This repository is structured for an incremental migration from a monolithic
`app.py` to a package-based layout under `app_new/` (and eventually `app/`).

Quick commands (Windows PowerShell):

```powershell
# create venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# run tests
.\.venv\Scripts\python -m pytest -q

# format
.\.venv\Scripts\python -m black .

# lint
.\.venv\Scripts\python -m ruff .
```

Migrations: Alembic is used for DB migrations; keep existing migration scripts and
create new revisions via:

```powershell
.\.venv\Scripts\python -m alembic revision --autogenerate -m "describe change"
.\.venv\Scripts\python -m alembic upgrade head
```

ETL: ETL scripts live in `etl/` (planned). The ER diagram is in
`DATABASE_ER_DIAGRAM.md` and should guide model changes.

Configuration & Settings
------------------------

This repo now includes a Pydantic-based `Settings` class at
`app_new/config/settings.py`. Example usage:

```python
from app_new.config.settings import settings

print(settings.ENV)
```

Environment variables are loaded from a `.env` file at the repo root when
present. An example `.env.example` is included.
