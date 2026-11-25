from repo_evolution.git_data import collect_changes, collect_commits, parse_numstat, snapshot_files, utc_timestamp

from conftest import commit, git_command
import subprocess


def test_date_boundaries_rename_binary_and_read_only(history):
    repo = history["repo"]
    before = git_command(repo, "status", "--porcelain")
    rows = collect_commits(repo, history["head"], history["start"], history["end"])
    assert len(rows) == 3
    assert rows[0]["commit_hash"] == history["first"]
    assert rows[-1]["commit_hash"] == history["last"]
    changes = collect_changes(repo, rows, ("package", "src/package"))
    rename = next(row for row in changes if row["previous_path"])
    assert rename["previous_path"] == "package/sample.py"
    assert rename["path"] == "src/package/sample.py"
    assert rename["canonical_path"] == "package/sample.py"
    assert rename["is_source"]
    binary = next(row for row in changes if row["binary"])
    assert binary["added"] is None and binary["deleted"] is None
    assert len(snapshot_files(repo, history["first"], ("package", "src/package"))) == 1
    assert git_command(repo, "status", "--porcelain") == before
    assert git_command(repo, "rev-parse", "HEAD") == history["head"]


def test_numstat_handles_tabs_unicode_newlines_and_rename():
    data = "2\t1\tpackage/中文\tfile\n.py\0-\t-\tbinary\0".encode()
    data += b"0\t0\t\0package/old.py\0src/package/new.py\0"
    rows = parse_numstat(data)
    assert rows[0]["path"] == "package/中文\tfile\n.py"
    assert rows[1]["binary"]
    assert rows[2]["previous_path"] == "package/old.py"
    assert rows[2]["added"] == 0


def test_timezone_conversion():
    assert utc_timestamp("2023-01-01T00:00:00+08:00").isoformat() == "2022-12-31T16:00:00+00:00"


def test_legacy_invalid_timezone_uses_epoch(history):
    repo = history["repo"]
    tree = git_command(repo, "rev-parse", "HEAD^{tree}")
    raw = (f"tree {tree}\nauthor Legacy <legacy@example.invalid> 1315449530 +51800\n"
           f"committer Legacy <legacy@example.invalid> 1315449530 +51800\n\nLegacy clock\n").encode()
    process = subprocess.run(["git", "-C", str(repo), "hash-object", "--literally", "-t", "commit", "-w", "--stdin"],
                             input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    sha = process.stdout.decode().strip()
    from datetime import datetime, timezone
    rows = collect_commits(repo, sha, datetime(2011, 1, 1, tzinfo=timezone.utc), datetime(2012, 1, 1, tzinfo=timezone.utc))
    assert len(rows) == 1
    assert rows[0]["committed_at"] == datetime.fromtimestamp(1315449530, timezone.utc).isoformat()


def test_merge_commit_excluded_but_branch_history_included(history):
    repo = history["repo"]
    git_command(repo, "checkout", "-b", "feature", history["first"])
    (repo / "side.txt").write_text("feature", encoding="utf-8")
    side = commit(repo, "side commit", "2023-01-10T00:00:00+00:00")
    git_command(repo, "checkout", "main")
    git_command(repo, "merge", "--no-ff", "feature", "-m", "merge feature", stamp="2023-02-20T00:00:00+00:00")
    rows = collect_commits(repo, "HEAD", history["start"], history["end"])
    assert len(rows) == 4
    assert side in {row["commit_hash"] for row in rows}
    assert all("merge feature" != row["subject"] for row in rows)
