#!/usr/bin/env python3
"""Print a masked database URL from the project's DatabaseConfig.

This prints the DB URL with the password replaced by '***' so you can confirm
which host/user/database the app will connect to without exposing secrets.
"""
import re
import sys
from pathlib import Path

# Add project root to sys.path so local imports work when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import DatabaseConfig


def mask_db_url(url: str) -> str:
    # Try to replace password between : and @ in the authority section
    # e.g. postgresql://user:password@host:port/db -> postgresql://user:***@host:port/db
    return re.sub(r'://([^:/]+):([^@]+)@', r'://\1:***@', url)


def main():
    cfg = DatabaseConfig()
    url = cfg._get_database_url()
    masked = mask_db_url(url)
    print(masked)


if __name__ == '__main__':
    main()
