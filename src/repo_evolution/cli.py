"""Command-line entry point."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from sqlalchemy.exc import SQLAlchemyError

from .pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Git history and Python source structure")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("run", help="Run a reproducible analysis experiment")
    command.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.config), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError, SQLAlchemyError, sqlite3.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
