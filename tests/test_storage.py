import sqlite3

import pytest
from sqlalchemy.exc import IntegrityError

from repo_evolution.storage import save_run


def test_failed_replacement_rolls_back_previous_run(tmp_path):
    database = tmp_path / "sample.sqlite"
    row = {"commit_hash": "abc", "author": "Test", "author_key": "test",
           "authored_at": "2023-01-01", "committed_at": "2023-01-01", "parents": "", "subject": "before"}
    save_run(database, "test-run", "old manifest", [row], [], [], [])
    with pytest.raises(IntegrityError):
        save_run(database, "test-run", "new manifest", [row, row], [], [], [])
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT manifest FROM runs").fetchone()[0] == "old manifest"
        assert connection.execute("SELECT count(*) FROM commits").fetchone()[0] == 1
