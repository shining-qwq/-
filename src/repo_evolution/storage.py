"""Transactional SQLite persistence using SQLAlchemy Core."""

from pathlib import Path

from sqlalchemy import (Boolean, Column, ForeignKey, Integer, MetaData, String, Table,
                        Text, URL, create_engine, delete, event)


metadata = MetaData()
runs = Table("runs", metadata,
             Column("run_id", String, primary_key=True), Column("manifest", Text, nullable=False))


def run_column():
    return Column("run_id", String, ForeignKey("runs.run_id", ondelete="CASCADE"), primary_key=True)


commits = Table("commits", metadata, run_column(), Column("commit_hash", String, primary_key=True),
                *[Column(name, Text) for name in ("author", "author_key", "authored_at", "committed_at", "parents", "subject")])
changes = Table("file_changes", metadata, run_column(), Column("commit_hash", String, primary_key=True),
                Column("path", Text, primary_key=True), Column("previous_path", Text, nullable=False),
                Column("canonical_path", Text), Column("added", Integer), Column("deleted", Integer),
                Column("binary", Boolean), Column("is_source", Boolean))
snapshots = Table("snapshots", metadata, run_column(), Column("snapshot", String, primary_key=True),
                  Column("commit_hash", String), Column("committed_at", String))
metrics = Table("file_metrics", metadata, run_column(), Column("snapshot", String, primary_key=True),
                Column("path", Text, primary_key=True), Column("canonical_path", Text),
                *[Column(name, Integer) for name in ("physical_lines", "functions", "classes", "branch_nodes", "function_lines", "max_function_lines")],
                Column("parse_error", Text))


def save_run(path: Path, run_id: str, manifest: str, commit_rows: list[dict],
             change_rows: list[dict], snapshot_rows: list[dict], metric_rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=str(path)))

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(delete(runs).where(runs.c.run_id == run_id))
            connection.execute(runs.insert(), {"run_id": run_id, "manifest": manifest})
            for table, rows in ((commits, commit_rows), (changes, change_rows), (snapshots, snapshot_rows), (metrics, metric_rows)):
                if rows:
                    connection.execute(table.insert(), [{"run_id": run_id, **row} for row in rows])
    finally:
        engine.dispose()
