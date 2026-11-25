"""Portable figure generation and a data-backed Markdown experiment summary."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def figures(tables: dict, output: Path) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(output / name, dpi=160)
        plt.close(fig)

    monthly = tables["monthly"]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(monthly["month"], monthly["commits"], marker="o", markersize=3)
    ax.set(title="Monthly non-merge commits (UTC)", ylabel="Commits")
    ax.set_xticks(range(0, len(monthly), max(1, len(monthly) // 8)))
    ax.tick_params(axis="x", rotation=35)
    save(fig, "monthly_commits.png")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(monthly["month"], monthly["active_authors"], color="#b35c29", marker="o", markersize=3)
    ax.set(title="Monthly active authors (normalized email identity)", ylabel="Authors")
    ax.set_xticks(range(0, len(monthly), max(1, len(monthly) // 8)))
    ax.tick_params(axis="x", rotation=35)
    save(fig, "monthly_authors.png")

    fig, ax = plt.subplots(figsize=(10, 5))
    top = tables["hotspots"].head(10).iloc[::-1]
    if not top.empty:
        ax.barh(top["canonical_path"], top["commits"], color="#346c8b")
    else:
        ax.text(.5, .5, "No source changes in this window", ha="center", transform=ax.transAxes)
    ax.set(title="Most frequently changed source files", xlabel="Distinct commits")
    save(fig, "source_hotspots.png")

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    versions = tables["snapshots"]
    axes[0].plot(versions["snapshot"], versions["functions"], marker="o", label="Functions")
    axes[0].plot(versions["snapshot"], versions["classes"], marker="o", label="Classes")
    axes[0].set(title="Source structure across pinned snapshots", ylabel="Definitions")
    axes[0].legend()
    axes[1].plot(versions["snapshot"], versions["branch_nodes"], marker="o", color="#b35c29")
    axes[1].set(ylabel="Branch nodes (not cyclomatic complexity)")
    axes[1].tick_params(axis="x", rotation=30)
    save(fig, "snapshot_structure.png")

    fig, ax = plt.subplots(figsize=(7, 5))
    joined = tables["hotspot_structure"]
    if not joined.empty:
        ax.scatter(joined["branch_nodes"], joined["commits"], alpha=.75, color="#346c8b")
    else:
        ax.text(.5, .5, "No matched files", ha="center", transform=ax.transAxes)
    ax.set(title="Change frequency vs latest snapshot structure",
           xlabel="Branch nodes in latest selected snapshot", ylabel="Commits in window")
    save(fig, "hotspot_structure.png")


def write_report(tables: dict, manifest: dict, output: Path) -> None:
    monthly, versions, hotspots = (tables[name] for name in ("monthly", "snapshots", "hotspots"))
    top = hotspots.head(5)
    rows = "\n".join(f"| {row.canonical_path} | {row.commits} | {int(row.churn)} |" for row in top.itertuples())
    if not rows:
        rows = "| 无源码变更 | 0 | 0 |"
    report = f"""# 实验结果摘要

本文件由程序根据实际数据自动生成，是课程报告的数据素材。

- 实验标识：`{manifest['run_id']}`
- 上游固定提交：`{manifest['ref_commit']}`
- 时间窗口（UTC，左闭右开）：`{manifest['start']}` 至 `{manifest['end']}`
- 非合并提交：{len(tables['commits'])} 条；提交者身份：{len(tables['contributors'])} 个。
- 源码变更记录：{len(tables['file_changes'].loc[tables['file_changes']['is_source'].eq(True)])} 条。
- 版本快照：{len(versions)} 个；源码解析失败：{int(versions['parse_failures'].sum())} 个文件快照。
- 活跃月份：{int((monthly['commits'] > 0).sum())}/{len(monthly)}。

## 高频修改源码文件

| 文件（规范化路径） | 涉及提交数 | 增删行总量 |
| --- | --- | --- |
{rows}

## 图表

![月度提交](monthly_commits.png)

![月度活跃作者](monthly_authors.png)

![源码变更热点](source_hotspots.png)

![版本结构](snapshot_structure.png)

![热点与结构](hotspot_structure.png)

## 统计口径与局限

1. 提交来自固定 ref 可达历史，排除多父节点合并提交，按 Git Unix 提交时间戳转换为 UTC 后筛选；不使用作者时间归月。这样也能处理历史提交中的异常时区偏移。月份边界按配置裁剪，空月份保留为零。
2. 作者身份按邮箱去首尾空格并转小写，空邮箱回退作者名；未合并不同邮箱的同一人，也未过滤机器人。因此身份数不等于真实人数。
3. 增删行数来自 Git `--numstat -M`，二进制文件以空数值表示并单独计数。源码热点只包含配置源码前缀下的 `.py` 文件。
4. Git 重命名检测为启发式。将 `src/` 前缀去除以对应 Requests 的包路径迁移，保留原始路径。更复杂的文件拆分、合并和重命名不自动追溯到单一历史实体。
5. AST 指标包含嵌套函数、异步函数和方法。物理行数包括空行与注释；函数长度按 def 至 end_lineno 计算，包含函数体内部空行和注释，不包含装饰器行。嵌套函数的行数可能同时计入外层函数。
6. 分支节点统计 If、For、AsyncFor、While、IfExp、ExceptHandler、match_case；不统计布尔短路或推导式过滤。这是结构计数，不是圈复杂度。
7. AST 解析受当前 Python 语法支持范围影响；失败记录在 file_metrics.csv，快照汇总只累加解析成功的文件，并显示覆盖量。
8. 热点与结构图仅包含最后一个快照仍存在且解析成功的匹配文件；已删除文件不进入该图。该图描述关联，不能证明缺陷或因果关系。
9. 版本快照不是所有中间提交，无法反映窗口内每次结构变化。manifest.json 记录固定哈希、配置口径和运行环境。

具体数值见同目录 CSV。正式课程报告还需要围绕研究问题加入人工核验、解释和引用。
"""
    (output / "experiment_summary.md").write_text(report, encoding="utf-8")
