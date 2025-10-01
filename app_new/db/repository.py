"""Thin DB repository proxy used during incremental refactor.

This module delegates to the existing `db_manager` object exposed by the
top-level `database` module (imported by `app.py`). Importing is lazy to avoid
triggering heavy DB initialization during module import.
"""
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def _get_db_manager():
    try:
        import importlib
        root_db = importlib.import_module('database')
        return getattr(root_db, 'db_manager', None)
    except Exception:
        logger.exception('Unable to import database.db_manager')
        return None


def store_transactions(all_transactions: List[Dict], wallet_analysis: Dict) -> bool:
    """Store transactions via the project's db_manager.

    Returns True on success, False otherwise.
    """
    db = _get_db_manager()
    if not db:
        logger.warning('No db_manager available; skipping store_transactions')
        return False
    try:
        return db.store_transactions(all_transactions, wallet_analysis)
    except Exception:
        logger.exception('db_manager.store_transactions failed')
        return False


def get_db_health() -> Dict[str, Any]:
    db = _get_db_manager()
    if not db:
        return {'ok': False, 'reason': 'no-db-manager'}
    try:
        return db.get_db_health()
    except Exception:
        logger.exception('db_manager.get_db_health failed')
        return {'ok': False, 'reason': 'exception'}


def test_db_connection() -> bool:
    db = _get_db_manager()
    if not db:
        return False
    try:
        return db.test_db_connection()
    except Exception:
        logger.exception('db_manager.test_db_connection failed')
        return False
"""Thin repository wrappers to interact with the existing database layer.

This module provides a small indirection so refactors can import a stable
API while the underlying `database` module is migrated or split.
"""
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from database import db_manager  # noqa: F401
    DB_AVAILABLE = True
except Exception as e:
    DB_AVAILABLE = False
    db_manager = None


def store_transactions(transactions: List[Dict[str, Any]], wallet_analysis: Optional[Dict[str, Any]] = None) -> bool:
    if not DB_AVAILABLE:
        logger.warning("DB not available; skipping store_transactions")
        return False
    try:
        return db_manager.store_transactions(transactions, wallet_analysis)
    except Exception as e:
        logger.error("Error in repository.store_transactions: %s", e)
        return False


def get_wallet_summary(wallet_address: str, chain_id: int) -> Optional[Dict[str, Any]]:
    if not DB_AVAILABLE:
        return None
    try:
        return db_manager.get_wallet_summary(wallet_address, chain_id)
    except Exception as e:
        logger.error("Error in repository.get_wallet_summary: %s", e)
        return None
