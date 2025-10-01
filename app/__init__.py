"""Package shim: execute top-level ``app.py`` into this package module.

This approach intentionally loads the existing ``app.py`` source and
executes it into the package module's globals so that functions like
``get_network_summary`` reference the package-level names. That makes
``unittest.mock.patch('app.fetch_transactions_from_explorer')`` behave as
tests expect.

This shim is a minimal, non-invasive bridge while converting the codebase
to a package layout. It avoids creating separate module objects that would
break name resolution inside functions.
"""
from __future__ import annotations

import logging
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

_root = Path(__file__).parent.parent
_candidate = _root / 'app.py'

if _candidate.exists():
    try:
        source = _candidate.read_text(encoding='utf-8')
        # Provide a few globals that the original module expects
        globals()['__file__'] = str(_candidate)
        globals()['__name__'] = 'app'
        # Execute the top-level app.py into this module's globals
        exec(compile(source, str(_candidate), 'exec'), globals())
    except Exception as e:  # pragma: no cover - defensive
        logger.exception('Failed to exec top-level app.py into package: %s', e)
else:
    logger.debug('No top-level app.py found; package shim is inert')


def create_app():
    """Return the Flask application instance from the executed top-level module.

    This returns the `app` object if it exists in the module globals. It is a
    convenience for tests and WSGI servers that prefer a factory function.
    """
    return globals().get('app')


# Re-export `app` at package level for backward compatibility
app = globals().get('app')

__all__ = ['app', 'create_app']

