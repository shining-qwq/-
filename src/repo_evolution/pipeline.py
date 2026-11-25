"""End-to-end experiment: fixed Git objects -> DB -> CSV, figures, summary."""

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import tempfile

from . import __version__
from .analysis import summarize
from .ast_metrics import analyze_source
from .config import load_config
from .git_data import canonical_path, collect_changes, collect_commits, git, resolve_ref, snapshot_files
from .reporting import figures, write_report
from .storage import save_run


def run(config_path: Path) -> dict:
    config = load_config(config_path)
    print("[1/5] Resolving immutable Git revisions", flush=True)
    ref = resolve_ref(config.repo, config.ref)
    snapshots = []
    for label in config.snapshots:
        sha = resolve_ref(config.repo, label)
        stamp = datetime.fromtimestamp(int(git(config.repo, "show", "-s", "--format=%ct", sha).decode().strip()), timezone.utc)
        if not config.start <= stamp < config.end:
            raise ValueError(f"Snapshot {label} is outside the configured time window")
        ancestor = git(config.repo, "merge-base", ref, sha).decode().strip()
        if ancestor != sha:
            raise ValueError(f"Snapshot {label} is not an ancestor of ref")
        snapshots.append({"snapshot": label, "commit_hash": sha, "committed_at": stamp.isoformat()})
    snapshots.sort(key=lambda row: (row["committed_at"], row["snapshot"]))
    manifest = {
        "tool_version": __version__, "metrics_version": 1, "ref_commit": ref,
        "start": config.start.isoformat(), "end": config.end.isoformat(),
        "end_exclusive": True, "timezone": "UTC", "merge_commits": "excluded",
        "author_identity": "trimmed casefolded email, fallback name; no alias or bot filtering",
        "source_paths": list(config.source_paths), "canonical_path_rule": "strip src/ prefix",
        "snapshots": snapshots,
        "environment": {"python": platform.python_version(),
                        **{name: version(name) for name in ("SQLAlchemy", "pandas", "matplotlib")}},
    }
    fingerprint = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
    run_id = hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
    manifest["run_id"] = run_id
    print("[2/5] Collecting non-merge commits and file changes", flush=True)
    commits = collect_commits(config.repo, ref, config.start, config.end)
    changes = collect_changes(config.repo, commits, config.source_paths)
    print(f"      {len(commits)} commits, {len(changes)} file changes", flush=True)
    print("[3/5] Parsing source snapshots", flush=True)
    metrics = []
    for snapshot in snapshots:
        files = snapshot_files(config.repo, snapshot["commit_hash"], config.source_paths)
        if not files:
            raise ValueError(f"No source files matched snapshot {snapshot['snapshot']}; check source_paths")
        for path, content in files:
            metrics.append({"snapshot": snapshot["snapshot"], "canonical_path": canonical_path(path), **analyze_source(path, content)})
    manifest["counts"] = {"commits": len(commits), "file_changes": len(changes),
                          "snapshots": len(snapshots), "file_snapshots": len(metrics),
                          "parse_failures": sum(bool(row["parse_error"]) for row in metrics)}
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    print("[4/5] Saving transaction and computing aggregates", flush=True)
    save_run(config.database, run_id, manifest_text, commits, changes, snapshots, metrics)
    tables = summarize(commits, changes, snapshots, metrics, config.start, config.end)
    print("[5/5] Exporting CSV, figures and experiment summary", flush=True)
    config.output.parent.mkdir(parents=True, exist_ok=True)
    # Produce a complete staging set before replacing previous generated artifacts.
    with tempfile.TemporaryDirectory(prefix="repo-evolution-", dir=config.output.parent) as temporary:
        stage = Path(temporary)
        for name, frame in tables.items():
            exported = frame.copy()
            if "author_key" in exported:
                exported["author_key"] = exported["author_key"].map(lambda key: hashlib.sha256(key.encode()).hexdigest()[:20])
            exported.to_csv(stage / f"{name}.csv", index=False, encoding="utf-8", float_format="%.6f", lineterminator="\n")
        figures(tables, stage)
        write_report(tables, manifest, stage)
        (stage / "manifest.json").write_text(manifest_text, encoding="utf-8")
        config.output.mkdir(parents=True, exist_ok=True)
        for artifact in sorted(stage.iterdir(), key=lambda item: item.name == "manifest.json"):
            os.replace(artifact, config.output / artifact.name)
    return {"run_id": run_id, **manifest["counts"], "output": str(config.output), "database": str(config.database)}
