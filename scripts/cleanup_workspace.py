#!/usr/bin/env python3
"""Cleanup workspace helper.

Removes .pyc files and __pycache__ directories (excluding the virtualenv).
Run manually or via pre-commit as a local hook.
"""
from pathlib import Path
import shutil
import sys


def clean_workspace(root: Path):
    removed = []
    # Remove .pyc files
    for p in root.rglob('*.pyc'):
        # skip virtualenv if present under the tree
        if '.venv' in p.parts:
            continue
        try:
            p.unlink()
            removed.append(str(p))
        except Exception:
            pass

    # Remove __pycache__ directories
    for p in root.rglob('__pycache__'):
        if '.venv' in p.parts:
            continue
        try:
            shutil.rmtree(p)
            removed.append(str(p))
        except Exception:
            pass

    return removed


def main():
    root = Path(__file__).resolve().parents[1]
    removed = clean_workspace(root)
    if removed:
        print('Removed:')
        for r in removed:
            print('  ', r)
    else:
        print('Nothing to remove')


if __name__ == '__main__':
    sys.exit(0)
