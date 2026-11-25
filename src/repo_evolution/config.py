"""Validated, config-file-relative experiment settings."""

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import json
from pathlib import Path


@dataclass(frozen=True)
class Config:
    repo: Path
    output: Path
    database: Path
    start: datetime
    end: datetime
    ref: str
    snapshots: tuple[str, ...]
    source_paths: tuple[str, ...]


def load_config(path: Path) -> Config:
    path = path.resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Configuration must be a JSON object")
    allowed = {"repo", "output", "database", "start", "end", "ref", "snapshots", "source_paths"}
    unknown = raw.keys() - allowed
    if unknown:
        raise ValueError(f"Unknown configuration keys: {sorted(unknown)}")
    for key in allowed:
        if key not in raw:
            raise ValueError(f"Missing configuration key: {key}")
    for key in ("repo", "output", "database", "start", "end", "ref"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    for key in ("snapshots", "source_paths"):
        if not isinstance(raw[key], list) or not raw[key]:
            raise ValueError(f"{key} must be a nonempty list")
        if any(not isinstance(item, str) or not item.strip() for item in raw[key]):
            raise ValueError(f"{key} must contain nonempty strings")
        if len(set(raw[key])) != len(raw[key]):
            raise ValueError(f"{key} must not contain duplicates")
    for ref in [raw["ref"], *raw["snapshots"]]:
        if ref.startswith("-"):
            raise ValueError("Git refs must not start with '-'")
    for prefix in raw["source_paths"]:
        if prefix.startswith(("/", "\\")) or "\\" in prefix or ":" in prefix or ".." in prefix.split("/"):
            raise ValueError("source_paths must be repository-relative POSIX paths")
    start = datetime.combine(date.fromisoformat(raw["start"]), time.min, timezone.utc)
    end = datetime.combine(date.fromisoformat(raw["end"]), time.min, timezone.utc)
    if start >= end:
        raise ValueError("start must precede the exclusive end date")
    resolve = lambda value: (path.parent / value).resolve()
    repo, output, database = (resolve(raw[key]) for key in ("repo", "output", "database"))
    if not repo.is_dir():
        raise ValueError(f"Repository directory does not exist: {repo}")
    if output == repo or output in repo.parents or output.is_relative_to(repo):
        raise ValueError("output must be separate from the input repository")
    if database == repo or database.is_relative_to(repo):
        raise ValueError("database must be separate from the input repository")
    return Config(repo, output, database, start, end, raw["ref"],
                  tuple(raw["snapshots"]), tuple(p.rstrip("/") for p in raw["source_paths"]))
