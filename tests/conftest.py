from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

import pytest


def git_command(repo: Path, *args: str, stamp: str | None = None) -> str:
    __tracebackhide__ = True
    environment = os.environ.copy()
    if stamp:
        environment.update(GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
    result = subprocess.run(["git", "-C", str(repo), *args], env=environment,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        pytest.fail(f"Git {args[0]} failed: {result.stderr.decode('utf-8', errors='replace')}", pytrace=False)
    return result.stdout.decode("utf-8", errors="replace").strip()


def commit(repo: Path, subject: str, stamp: str) -> str:
    git_command(repo, "add", "--all")
    git_command(repo, "commit", "-m", subject, stamp=stamp)
    return git_command(repo, "rev-parse", "HEAD")


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / "input-repo"
    repo.mkdir()
    git_command(repo, "init", "-b", "main")
    git_command(repo, "config", "user.name", "Fixture Author")
    git_command(repo, "config", "user.email", "fixture@example.invalid")
    git_command(repo, "config", "core.autocrlf", "false")
    package = repo / "package"
    package.mkdir()
    file = package / "sample.py"
    file.write_text("def one():\n    return 1\n", encoding="utf-8")
    commit(repo, "outside start", "2022-12-31T10:00:00+00:00")
    file.write_text("def one(flag):\n    if flag:\n        return 1\n    return 2\n", encoding="utf-8")
    (repo / "binary.dat").write_bytes(b"\0\x01\xff")
    first = commit(repo, "at inclusive start", "2023-01-01T00:00:00+00:00")
    git_command(repo, "tag", "r1")
    destination = repo / "src" / "package"
    destination.mkdir(parents=True)
    file.rename(destination / "sample.py")
    commit(repo, "move package", "2023-02-01T08:00:00+08:00")
    (destination / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    last = commit(repo, "invalid syntax sample", "2023-02-15T00:00:00+00:00")
    git_command(repo, "tag", "r2")
    (repo / "note.txt").write_text("after the window", encoding="utf-8")
    head = commit(repo, "at exclusive end", "2023-03-01T00:00:00+00:00")
    return {"repo": repo, "first": first, "last": last, "head": head,
            "start": datetime(2023, 1, 1, tzinfo=timezone.utc),
            "end": datetime(2023, 3, 1, tzinfo=timezone.utc)}
