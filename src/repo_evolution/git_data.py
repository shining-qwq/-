"""Read Git objects without checking out or modifying the source repository."""

from datetime import datetime, timezone
from pathlib import Path
import subprocess


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise ValueError(f"Git {' '.join(args[:2])} failed: "
                         + result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def resolve_ref(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()


def utc_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def collect_commits(repo: Path, ref: str, start: datetime, end: datetime) -> list[dict]:
    # Filter in Python: Git's --since traversal can prune history with skewed clocks.
    data = git(repo, "log", "--no-merges", "-z",
               "--format=format:%H%x00%an%x00%ae%x00%at%x00%ct%x00%P%x00%s", ref)
    if not data:
        return []
    fields = data.decode("utf-8", errors="replace").split("\0")
    if len(fields) % 7:
        raise ValueError("Unexpected Git metadata record layout")
    commits = []
    for i in range(0, len(fields), 7):
        sha, author, email, authored, committed, parents, subject = fields[i:i + 7]
        stamp = datetime.fromtimestamp(int(committed), timezone.utc)
        if start <= stamp < end:
            commits.append({
                "commit_hash": sha, "author": author,
                "author_key": email.strip().casefold() or author.strip().casefold(),
                "authored_at": datetime.fromtimestamp(int(authored), timezone.utc).isoformat(),
                "committed_at": stamp.isoformat(), "parents": parents, "subject": subject,
            })
    return sorted(commits, key=lambda row: (row["committed_at"], row["commit_hash"]))


def is_source(path: str, prefixes: tuple[str, ...]) -> bool:
    return path.endswith(".py") and any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def canonical_path(path: str) -> str:
    # Requests moved its package from requests/ to src/requests/.
    return path[4:] if path.startswith("src/") else path


def parse_numstat(data: bytes) -> list[dict]:
    tokens = data.decode("utf-8", errors="replace").split("\0")
    rows = []
    index = 0
    while index < len(tokens):
        item = tokens[index]
        index += 1
        if not item:
            continue
        added, deleted, path = item.split("\t", 2)
        previous = ""
        if not path:
            if index + 1 >= len(tokens):
                raise ValueError("Truncated rename record in Git numstat")
            previous, path = tokens[index:index + 2]
            index += 2
        binary = added == "-" or deleted == "-"
        rows.append({"path": path, "previous_path": previous,
                     "added": None if binary else int(added),
                     "deleted": None if binary else int(deleted), "binary": binary})
    return rows


def collect_changes(repo: Path, commits: list[dict], prefixes: tuple[str, ...]) -> list[dict]:
    rows = []
    for commit in commits:
        data = git(repo, "diff-tree", "--root", "--no-commit-id", "-r", "-M", "--numstat", "-z", commit["commit_hash"])
        for change in parse_numstat(data):
            rows.append({"commit_hash": commit["commit_hash"], **change,
                         "canonical_path": canonical_path(change["path"]),
                         "is_source": is_source(change["path"], prefixes) or is_source(change["previous_path"], prefixes)})
    return rows


def snapshot_files(repo: Path, commit: str, prefixes: tuple[str, ...]) -> list[tuple[str, bytes]]:
    items = git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0")
    files = []
    for item in items:
        if not item:
            continue
        metadata, encoded_path = item.split(b"\t", 1)
        mode, kind, blob = metadata.split(b" ")
        path = encoded_path.decode("utf-8", errors="replace")
        if kind == b"blob" and mode != b"120000" and is_source(path, prefixes):
            files.append((path, git(repo, "cat-file", "blob", blob.decode("ascii"))))
    return sorted(files)
