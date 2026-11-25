"""Aggregate data with empty months and AST parse failures kept visible."""

import pandas as pd


def summarize(commits, changes, snapshots, metrics, start, end) -> dict[str, pd.DataFrame]:
    commit_frame = pd.DataFrame(commits, columns=["commit_hash", "author", "author_key", "authored_at", "committed_at", "parents", "subject"])
    change_frame = pd.DataFrame(changes, columns=["commit_hash", "path", "previous_path", "canonical_path", "added", "deleted", "binary", "is_source"])
    metric_frame = pd.DataFrame(metrics, columns=["snapshot", "path", "canonical_path", "physical_lines", "functions", "classes", "branch_nodes", "function_lines", "max_function_lines", "parse_error"])
    months = pd.period_range(start.strftime("%Y-%m"), (end - pd.Timedelta(microseconds=1)).strftime("%Y-%m"), freq="M").astype(str)
    commit_frame["month"] = pd.to_datetime(commit_frame["committed_at"], utc=True).dt.strftime("%Y-%m")
    monthly = commit_frame.groupby("month").agg(commits=("commit_hash", "count"), active_authors=("author_key", "nunique")).reindex(months, fill_value=0)
    monthly.index.name = "month"
    monthly = monthly.reset_index()
    if commit_frame.empty:
        contributors = pd.DataFrame(columns=["author_key", "author", "commits"])
    else:
        contributors = commit_frame.groupby("author_key").agg(author=("author", "first"), commits=("commit_hash", "count")).reset_index().sort_values(["commits", "author_key"], ascending=[False, True])
    source_changes = change_frame.loc[change_frame["is_source"].eq(True)]
    if source_changes.empty:
        hotspots = pd.DataFrame(columns=["canonical_path", "commits", "added", "deleted", "binary_changes", "churn"])
    else:
        hotspots = source_changes.groupby("canonical_path").agg(commits=("commit_hash", "nunique"), added=("added", "sum"), deleted=("deleted", "sum"), binary_changes=("binary", "sum")).reset_index()
        hotspots["churn"] = hotspots["added"] + hotspots["deleted"]
        hotspots = hotspots.sort_values(["commits", "canonical_path"], ascending=[False, True])
    snapshot_rows = []
    for snapshot in snapshots:
        subset = metric_frame.loc[metric_frame["snapshot"].eq(snapshot["snapshot"])]
        valid = subset.loc[subset["parse_error"].eq("")]
        functions = int(valid["functions"].sum())
        snapshot_rows.append({**snapshot, "files": len(subset), "parsed_files": len(valid),
                              "parse_failures": len(subset) - len(valid),
                              **{name: int(valid[name].sum()) for name in ("physical_lines", "functions", "classes", "branch_nodes", "function_lines")},
                              "mean_function_lines": float(valid["function_lines"].sum() / functions) if functions else 0.0})
    snapshot_summary = pd.DataFrame(snapshot_rows)
    latest = snapshots[-1]["snapshot"]
    valid_latest = metric_frame.loc[metric_frame["snapshot"].eq(latest) & metric_frame["parse_error"].eq("")]
    relationship = hotspots.merge(valid_latest[["canonical_path", "physical_lines", "functions", "branch_nodes"]], on="canonical_path", how="inner", validate="one_to_one")
    return {"commits": commit_frame, "file_changes": change_frame, "monthly": monthly,
            "contributors": contributors, "hotspots": hotspots, "file_metrics": metric_frame,
            "snapshots": snapshot_summary, "hotspot_structure": relationship}
