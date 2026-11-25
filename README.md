# 开源软件基础大作业

基于 Git 与 AST 的 Python 开源项目提交与代码结构演化分析——以 Requests 为例。

本工具读取本地 Git 对象，按配置完成提交采集、SQLite 存储、AST 结构分析、CSV 导出、绘图与实验摘要生成。分析时不切换上游分支或执行上游源码，不需要 GitHub Token。

## 当前成果

已实现完整命令行流程、自动化测试和 Requests 真实实验。默认分析窗口为 UTC `2023-01-01` 至 `2026-01-01`（不含结束时刻），包含 8 个固定版本快照。输出 8 张 CSV 表、5 张 PNG 图和实验摘要，固定 Git 哈希与环境信息记录在 manifest 中。

查看 [实验摘要](results/requests/experiment_summary.md)、[实验分析与代码核验](docs/experiment_notes.md)、[数据字典](docs/data_dictionary.md)、[设计说明](docs/design.md) 和 [开发验证记录](docs/validation.md)。本项目的代码与实验结果已完成第一版；课程 Word/PDF 报告另行按提供的模板整理。

## 安装与运行

需要 Git 和 Python 3.11 或以上。下面以 PowerShell 为例，在本仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
git clone -c fetch.fsck.badTimezone=ignore https://github.com/psf/requests.git data/repos/requests
.\.venv\Scripts\python.exe -m repo_evolution.cli run --config configs/requests.json
.\.venv\Scripts\python.exe scripts/verify_experiment.py --config configs/requests.json
.\.venv\Scripts\python.exe -m pytest -q --basetemp=data/pytest-tmp
```

本机已在 `.venv` 安装项目并缓存上游，直接运行第四行即可。首次建环境时使用了 `--system-site-packages` 复用现有数据分析库，README 命令则创建独立环境。Linux/macOS 使用 `.venv/bin/python` 替代解释器路径。Windows 的默认系统临时路径过长时，测试使用上面指定的短路径；`data/pytest-tmp` 专供测试使用，pytest 会清理该目录，不要放个人文件。

如需使用本次记录的直接依赖版本，在 Python 3.14 环境安装：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

`requirements-lock.txt` 固定直接依赖，不是所有平台的传递依赖完整锁文件。manifest 记录本次实际核心环境；不同版本的 Python 可能有不同 AST 支持范围，比较结果时应先核对环境。

## 配置

配置位于 `configs/requests.json`，所有磁盘路径相对配置文件所在目录解析。`start` 是包含边界的 UTC 日期，`end` 是不包含边界的 UTC 日期。`ref` 固定可达历史的提交哈希，`snapshots` 列出版本标签或哈希，`source_paths` 是仓库内源码前缀。

工具会把标签解析为提交哈希、按提交时间排序，要求快照位于时间窗口内且是 ref 的祖先；不匹配源码会报错。正式复现实验以已保存的 `manifest.json` 中哈希为准，若上游移动标签，应将配置中的标签替换为其记录的哈希。

输入仓库应包含所需完整历史，浅克隆可能缺失提交。默认配置使用 2026 年获取的上游固定 ref，只统计 2023～2025 年提交，8 个版本由 v2.28.2 覆盖到 v2.32.5；快照是抽样版本，未覆盖窗口结束前的每次提交。

## 输出

```text
src/repo_evolution/      采集、存储、AST、统计、绘图、命令行模块
configs/requests.json   实验配置
tests/                  合成 Git 仓库与边界情况测试
scripts/                独立数据一致性核验
docs/                   设计、数据字典和验证记录
results/requests/       可提交的实验 CSV、图表、摘要和 manifest
data/                   本地上游仓库、数据库与测试临时文件（不提交 Git）
```

每次实验按固定输入、工具与环境生成实验 ID。相同 ID 在数据库中事务性替换，失败时回滚，不累积重复数据；不同 ID 可以共存。输出文件先在临时目录全部生成，再逐一替换，manifest 最后写入。文件替换整体不具备跨文件事务性，如遇进程中断应重跑，不把中断后的文件集合当作完整结果。

## 统计解释

提交总量包含整个上游仓库的非合并提交；源码热点只包含指定路径内 `.py` 文件，两个口径不应混用。提交不等于功能数量，作者身份不等于真实人数，分支节点数不等于圈复杂度，改动频繁不意味着存在缺陷。作者按规范化邮箱分组，CSV 只输出邮箱身份的哈希，数据库保留分组原值；机器人未过滤。

更多定义和研究限制见自动生成的实验摘要。课程要求使用的 Git、SQLAlchemy、pandas、Matplotlib 与 AST 在项目中均有实际用途；pytest 承担自动化测试。

## 数据来源

- [Requests 官方仓库](https://github.com/psf/requests)，许可证为 [Apache-2.0](https://github.com/psf/requests/blob/main/LICENSE)。上游源码仅缓存于本地，未复制进本项目源码目录。
- [课程材料仓库](https://bitbucket.org/rezilla/open-lecture-notes/src/master/README.md)，用于确定技术与课程的对应关系。

仓库中只包含项目与研究输出。个人封面和学校模板保留在上级工作目录，最终提交报告时再填写。
