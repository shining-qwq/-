import hashlib
import json
import sqlite3

import pandas as pd
import pytest

from repo_evolution.analysis import summarize
from repo_evolution.config import load_config
from repo_evolution.pipeline import run


def experiment_config(tmp_path, history, **overrides):
    data = {"repo": "input-repo", "output": "results", "database": "data/test.sqlite",
            "start": "2023-01-01", "end": "2023-03-01", "ref": history["head"],
            "snapshots": ["r2", "r1"], "source_paths": ["package", "src/package"]}
    data.update(overrides)
    path = tmp_path / "experiment.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_full_pipeline_rerun_is_idempotent_and_deterministic(tmp_path, history):
    config = experiment_config(tmp_path, history)
    result = run(config)
    assert result["commits"] == 3
    assert result["parse_failures"] == 1
    output = tmp_path / "results"
    monthly = pd.read_csv(output / "monthly.csv")
    assert monthly["commits"].tolist() == [1, 2]
    assert monthly["active_authors"].tolist() == [1, 1]
    snapshots = pd.read_csv(output / "snapshots.csv")
    assert snapshots["snapshot"].tolist() == ["r1", "r2"]
    assert snapshots["parse_failures"].tolist() == [0, 1]
    assert (output / "monthly_commits.png").read_bytes().startswith(b"\x89PNG")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir()}
    assert run(config)["run_id"] == result["run_id"]
    assert hashes == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir()}
    with sqlite3.connect(result["database"]) as connection:
        assert connection.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM commits").fetchone()[0] == 3
        assert connection.execute("SELECT count(*) FROM file_metrics").fetchone()[0] == 3


@pytest.mark.parametrize("overrides", [
    {"start": "2023-03-01"}, {"snapshots": []}, {"snapshots": ["r1", "r1"]},
    {"output": "input-repo/results"}, {"source_paths": ["../outside"]}, {"ref": "--all"},
    {"surprise": True},
])
def test_configuration_errors(tmp_path, history, overrides):
    with pytest.raises(ValueError):
        load_config(experiment_config(tmp_path, history, **overrides))


def test_missing_ref_and_out_of_window_snapshot(tmp_path, history):
    with pytest.raises(ValueError, match="failed"):
        run(experiment_config(tmp_path, history, ref="missing-ref"))
    with pytest.raises(ValueError, match="outside"):
        run(experiment_config(tmp_path, history, snapshots=[history["head"]]))


def test_empty_history_keeps_months_and_headers(history):
    tables = summarize([], [], [{"snapshot": "merge", "commit_hash": "abc", "committed_at": "2023-01-01"}], [], history["start"], history["end"])
    assert tables["monthly"]["commits"].tolist() == [0, 0]
    assert tables["contributors"].empty
    assert tables["hotspots"].empty
    assert tables["snapshots"]["files"].tolist() == [0]
    assert "canonical_path" in tables["hotspot_structure"].columns
