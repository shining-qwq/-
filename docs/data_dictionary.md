# 数据字典与统计口径

## 文件与数据表

| CSV | 关键字段 | 含义 |
| --- | --- | --- |
| commits.csv | commit_hash, author, author_key, authored_at, committed_at, parents, subject, month | 时间窗口内非合并提交；author_key 在导出时转为 SHA-256 前 20 位 |
| file_changes.csv | commit_hash, path, previous_path, canonical_path, added, deleted, binary, is_source | 每个提交涉及的文件变更；Git 启发式重命名记录保留旧路径 |
| monthly.csv | month, commits, active_authors | 窗口覆盖的每个月，包含零提交月 |
| contributors.csv | author_key, author, commits | 按规范化邮箱身份聚合；author 为该身份窗口内首次出现的名字 |
| hotspots.csv | canonical_path, commits, added, deleted, binary_changes, churn | 仅源码文件；commits 是不同提交数，churn 是 added + deleted |
| file_metrics.csv | snapshot, path, canonical_path, physical_lines, functions, classes, branch_nodes, function_lines, max_function_lines, parse_error | 每个快照、每个源码文件的结构指标 |
| snapshots.csv | snapshot, commit_hash, committed_at, files, parsed_files, parse_failures, physical_lines, functions, classes, branch_nodes, function_lines, mean_function_lines | 成功解析文件的合计，另列覆盖量；函数均长按函数总数加权 |
| hotspot_structure.csv | canonical_path, commits, churn, physical_lines, functions, branch_nodes 等 | 历史源码热点与最后选定快照中仍存在且可解析文件的交集 |

SQLite 表为 runs、commits、file_changes、snapshots、file_metrics；每张明细表都含 run_id。runs 保存完整 manifest。汇总表在分析时计算，不冗余写入数据库。

## 定义

- 起止时间：UTC 日期构成的左闭右开区间；结束日期当天不计入。
- 提交范围：固定 ref 可达历史中的非合并提交，所有上游目录均参与提交总量统计。
- 作者身份：邮箱 trim + casefold，缺失邮箱时回退同样规范化的作者名；不同邮箱不自动合并，机器人不排除。
- 源码文件：配置前缀本身或前缀目录内、后缀为 `.py` 的普通 blob 文件；符号链接不作为源码快照解析。
- 规范化路径：移除 `src/` 前缀；原始路径始终保留。
- 物理行数：解码后 splitlines 的行数，包含空白和注释，不代表有效代码行数。
- 函数数：所有 FunctionDef 与 AsyncFunctionDef，包括方法和嵌套函数。
- 类数：所有 ClassDef，包括嵌套类。
- 函数长度：end_lineno - lineno + 1；不含装饰器，含函数内部空白和注释，嵌套结构可能重叠。
- 分支节点：If、For、AsyncFor、While、IfExp、ExceptHandler、match_case，包含默认 match 分支；不等于圈复杂度。
- 失败值：语法或编码失败记录错误，AST 数值为空；快照汇总只包括成功解析文件。
- 二进制改动：added/deleted 为空，binary 为真，不以零伪装行数；热点另输出 binary_changes。

## 复现信息

manifest.json 保存工具/指标版本、核心依赖版本、固定 ref、快照哈希、时间范围和数据量。相同环境和输入下的重复运行应得到同一实验 ID 和一致产物。直接依赖锁文件用于重建本次核心环境，传递依赖与平台差异仍需核对。
