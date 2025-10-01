Development notes and the refactor plan are in `docs/DEVELOPMENT.md`.

Planned refactor (high level):
- Create `app/` package with factory in `app/__init__.py` and Blueprints under
  `app/routes/`.
- Move services into `app/services/` and repositories into `app/db/`.
- Keep `app.py` as a compatibility shim during the migration pointing to the
  package implementation until cutover.

See `docs/diagrams.md` for diagrams.
