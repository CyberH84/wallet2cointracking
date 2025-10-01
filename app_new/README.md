App_new services
=================

This folder contains the extracted, testable services that are being
migrated out of the legacy `app.py` monolith.

Current contents:

- `services/defi.py` - DeFi helper functions (CSV export, protocol detection, normalization).
- `services/runtime.py` - Runtime shim used by the services to lazily delegate
  to the top-level `app` when available and provide safe fallbacks for tests.

How to run tests for these services

1. Activate the project's virtual environment.
2. Run pytest:

```pwsh
D:/wallet2cointracking/.venv/Scripts/python.exe -m pytest -q
```

Notes
- The `runtime` shim is intentionally conservative; add more behavior there
  if you want services to be runnable without the monolith.
