"""Independent Git / SQLite / CSV consistency check for a completed experiment."""

import argparse
import csv
import json
from pathlib import Path
import sqlite3
import subprocess

from repo_evolution.config import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    manifest = json.loads((config.output / "manifest.json").read_text(encoding="utf-8"))
    result = subprocess.run(["git", "-C", str(config.repo), "log", "--no-merges", "--format=%H %ct", manifest["ref_commit"]],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    git_commits = set()
    for line in result.stdout.decode("ascii").splitlines():
        sha, timestamp = line.split()
        if config.start.timestamp() <= int(timestamp) < config.end.timestamp():
            git_commits.add(sha)
    with (config.output / "commits.csv").open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    csv_commits = {row["commit_hash"] for row in csv_rows}
    with sqlite3.connect(config.database) as connection:
        db_commits = {row[0] for row in connection.execute("SELECT commit_hash FROM commits WHERE run_id=?", (manifest["run_id"],))}
        metrics = connection.execute("SELECT count(*) FROM file_metrics WHERE run_id=?", (manifest["run_id"],)).fetchone()[0]
    with (config.output / "monthly.csv").open(encoding="utf-8", newline="") as stream:
        monthly_total = sum(int(row["commits"]) for row in csv.DictReader(stream))
    if not (git_commits == csv_commits == db_commits and len(csv_rows) == monthly_total == len(git_commits)):
        raise SystemExit("FAILED: Git, SQLite, CSV or monthly counts differ")
    if metrics != manifest["counts"]["file_snapshots"]:
        raise SystemExit("FAILED: metric counts differ")
    print(json.dumps({"verified": True, "run_id": manifest["run_id"],
                      "commits": len(git_commits), "file_snapshots": metrics}, indent=2))


if __name__ == "__main__":
    main()
