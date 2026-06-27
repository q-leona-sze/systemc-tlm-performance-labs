# Project R：Headless Regression Harness Design

状态：设计稿

本文档定义 Project R 的设计：新增一个 Ubuntu headless 环境可运行的 regression
harness，把当前主要 architecture-level performance modeling demos 串成一键可复现的
实验入口。

本文档只描述设计，不创建脚本、不修改 README、不修改源码、不提交 generated results。
计划中的实现入口是：

```text
scripts/run_all_regressions.sh
```

Project R 服务于同一条项目证据链：

```text
workload -> trace -> metrics -> sweep -> comparison -> demo -> regression summary
```

## 1. Motivation

当前仓库已经从单个 LT demo 扩展为多个相互关联的 architecture-level performance
modeling demos：

- Project B：normalized trace replay bridge。
- Project C：gem5 SE trace extraction MVP。
- Project D：standalone C++ trace replay engine，并验证 Python/C++ replay summary
  equivalence。
- Project E：standalone C++ banked memory controller queueing model。
- Project F：gem5 stats trend correlation report。

这些 demos 已经能分别证明 trace contract、C++ simulator-engineering migration、
memory subsystem queueing abstraction，以及 trend-level stats report。但如果每次修改后
都手动运行，很容易漏掉 build、demo、optional input、generated summary 或 working tree
检查。

工业 performance modeling 项目需要的不只是单次 demo 成功，而是可复现、可回归、可审计的
workflow：

- 可复现：同一仓库版本、同一命令入口，可以重新生成关键 artifacts。
- 可回归：新改动不会静默破坏 Project D/E/F 等核心 demo。
- 可审计：每次运行记录 git branch、commit、dirty state、PASS/FAIL/SKIPPED 和关键输出路径。
- 可解释：summary 明确说明当前验证的是 demo chain health，不是 cycle accuracy。

Project R 的目标是验证当前 demo chain health，保护 architecture-level performance
modeling framework 的可运行性和输出契约。它不是为了证明模型的 cycle accuracy，也不是为了
引入更高 fidelity 的硬件校准。

## 2. Scope

Project R 第一版覆盖：

1. repo root 检查。
2. Ubuntu headless 环境下的基础工具检查。
3. LT build。
4. Project D demo。
5. Project E demo。
6. Project F demo。
7. 可选 Project B demo。
8. 可选 Project C 检查或跳过逻辑。
9. 生成 `artifacts/regression_summary.md`。

第一版重点保护当前 LT mainline 的核心 demos：

```text
repo root
-> environment check
-> LT build
-> Project D C++ replay demo
-> Project E banked memory controller demo
-> Project F trend correlation demo
-> optional Project B / Project C health checks
-> regression summary
```

Project R 不改变 Project B/C/D/E/F 的输出语义。各 demo 仍然写入它们自己的默认 results
目录；Project R 只负责 orchestration、status collection 和顶层 summary generation。

## 3. Non-Goals

Project R 第一版明确不做：

- 不做 gem5-SystemC live co-simulation。
- 不做 cycle accuracy validation。
- 不做 RTL correlation。
- 不做 silicon correlation。
- 不做 profiler correlation。
- 不做 GUI 依赖。
- 不改 Project B/C/D/E/F 的输出语义。
- 不改 Project B/C/D/E/F 的 CSV schema。
- 不把 generated results 提交进 Git。
- 不把 `artifacts/regression_summary.md` 当作 source artifact 提交。
- 不把 Project C 的 gem5 环境变成所有回归机器的 hard prerequisite。

Project R 只证明 headless demo chain 能否在当前 checkout 中完整跑通，并把失败或跳过原因写清楚。

## 4. Proposed Script

计划新增脚本：

```text
scripts/run_all_regressions.sh
```

脚本设计要求：

- 从 repo root 执行。
- 面向 Ubuntu headless 环境。
- 使用 bash strict mode：

```bash
set -euo pipefail
```

- 对 critical steps 使用 hard fail 策略。
- 对 optional steps 使用 SKIPPED 或 soft FAIL 策略，并在 summary 中解释原因。
- 每一步都记录 `PASS`、`FAIL` 或 `SKIPPED`。
- 生成顶层 summary：

```text
artifacts/regression_summary.md
```

脚本不应该依赖 GUI、desktop session、interactive prompt 或 macOS-only 工具。并行 build
优先使用 `nproc`：

```bash
cmake --build build/examples/lt -j$(nproc)
```

如果未来需要支持 macOS local smoke run，可以在后续阶段增加 portability layer；Project R
第一版以 Ubuntu headless regression 为主。

## 5. Regression Steps

### Step 0：Environment Check

目的：在真正 build / demo 之前，快速暴露缺失依赖和错误执行目录。

检查项：

- 当前目录必须是 repo root。
- `python3` 存在。
- `cmake` 存在。
- `git` 存在。
- `nproc` 存在。
- SystemC include/lib path 可发现。

建议检查方式：

```bash
test -f CMakeLists.txt
test -d examples/lt
command -v python3
command -v cmake
command -v git
command -v nproc
```

SystemC path 检查可以分两层：

- 如果默认 CMake discovery 能找到 SystemC，则记录 `PASS`。
- 如果需要显式路径，则检查用户传入或环境中配置的 include/lib path，例如
  `USER_SYSTEMC_INCLUDE_DIR` 和 `USER_SYSTEMC_LIB_DIR`。

如果基础工具缺失，Step 0 是 hard fail。SystemC path 不能发现时，也应 hard fail，因为
Step 1 的 LT build 会失败。

### Step 1：LT Build

目的：确认当前 LT lab 可以从源码重新构建。

计划命令：

```bash
cmake -S examples/lt -B build/examples/lt
cmake --build build/examples/lt -j$(nproc)
```

如果当前环境需要显式 SystemC include/lib path，设计上允许通过环境变量透传到 CMake：

```bash
cmake -S examples/lt -B build/examples/lt \
  -DUSER_SYSTEMC_INCLUDE_DIR="$USER_SYSTEMC_INCLUDE_DIR" \
  -DUSER_SYSTEMC_LIB_DIR="$USER_SYSTEMC_LIB_DIR"
```

Step 1 是 hard fail。LT build 失败说明当前 checkout 的核心 demo 前提不成立。

### Step 2：Project D

目的：保护 standalone C++ trace replay engine、Python/C++ replay summary equivalence，
以及 Project D demo wrapper。

计划命令：

```bash
python3 examples/lt/tools/demo_cpp_trace_replay_lab.py
```

通过标准：

- demo 命令返回 0。
- Project D C++ replay PASS marker 出现。
- Python vs C++ replay summary equivalence PASS marker 出现。
- Project D demo PASS marker 出现。
- 关键输出路径存在，例如：

```text
examples/lt/results/cpp_trace_replay_lab/trace.csv
examples/lt/results/cpp_trace_replay_lab/summary.csv
examples/lt/results/cpp_trace_replay_lab/comparison.md
```

Step 2 是 hard fail。Project D 是当前 C++ simulator-engineering regression 的核心 gate。

### Step 3：Project E

目的：保护 standalone C++ banked memory controller queueing model。

计划命令：

```bash
python3 examples/lt/tools/demo_banked_memory_controller_lab.py
```

通过标准：

- demo 命令返回 0。
- Project E demo PASS marker 出现。
- 关键输出路径存在，例如：

```text
examples/lt/results/project_e_banked_memory_controller/trace.csv
examples/lt/results/project_e_banked_memory_controller/summary.csv
examples/lt/results/project_e_banked_memory_controller/comparison.md
```

Step 3 是 hard fail。Project E 保护 memory subsystem queueing abstraction、tail latency
和 queue pressure 指标链路。

### Step 4：Project F

目的：保护 gem5 stats trend correlation report 的 file-based report chain。

计划命令：

```bash
python3 examples/lt/tools/demo_gem5_stats_correlation_lab.py
```

通过标准：

- demo 命令返回 0。
- Project F demo PASS marker 出现。
- 关键输出路径存在，例如：

```text
examples/lt/results/project_f_gem5_stats_correlation/correlation_summary.csv
examples/lt/results/project_f_gem5_stats_correlation/correlation_report.md
```

Step 4 在默认 Project R profile 中是 hard fail，因为 Project F 已经是当前 repo 的主要
trend-level report demo。若某台机器没有 Project C / gem5 stats 输入，应该先在 Step 6
记录 Project C missing context，并由 Project F 的错误信息提示前置输入缺失；不能用 synthetic
stats 冒充真实 gem5 stats correlation。

### Step 5：Project B Optional

目的：补充检查 normalized trace replay bridge 的原始 Python demo 是否仍然健康。

计划命令：

```bash
python3 examples/lt/tools/demo_trace_replay_lab.py
```

Project B 默认作为 soft optional check：

- 如果 demo 成功，记录 `PASS`。
- 如果 demo 文件不存在，记录 `SKIPPED`。
- 如果 demo 存在但运行失败，记录 `FAIL`，但默认不让总回归失败。

原因：

- Project D 已经通过 standalone C++ replay 和 Python/C++ equivalence 覆盖 normalized
  replay contract 的主路径。
- Project B 仍有文档和历史价值，但 Project R 第一版的 hard gates 应聚焦当前主要
  C++ simulator、memory model 和 correlation report。
- 如果后续发现 Project B 是必须长期保护的 source-level contract，可以增加
  `--strict-project-b` 或 CI profile，把 Project B failure 升级为 hard fail。

summary 中必须写明 Project B 是 optional soft check，避免把 soft FAIL 误读为整体通过。

### Step 6：Project C Optional

目的：对 gem5 SE trace extraction MVP 做环境敏感的 health check，但不把 gem5 依赖强加到
所有 headless regression 环境。

Project C 可能依赖 gem5 binary、target workload、外部生成目录或历史 results。第一版策略：

- 如果 Project C extraction inputs / outputs 存在，则检查关键文件或运行对应 demo。
- 如果缺少 gem5 extraction prerequisites，则记录 `SKIPPED`。
- Project C `SKIPPED` 不让总回归失败。

建议检查优先级：

1. 检查默认 Project C 输出是否存在：

```text
examples/lt/results/gem5_se_trace_extraction/sequential/stats.txt
examples/lt/results/gem5_se_trace_extraction/stride/stats.txt
examples/lt/results/gem5_trace_replay_lab/summary.csv
examples/lt/results/gem5_trace_replay_lab/comparison.md
```

2. 如果默认输出存在，记录 `PASS`，并把路径写入 summary。
3. 如果存在明确的 Project C demo / extraction command，且所需 gem5 binary 和 workload
   inputs 都存在，可以运行该 demo。
4. 如果 prerequisites 不完整，记录 `SKIPPED`，原因写为：

```text
Project C requires gem5 extraction inputs or externally generated results.
```

Project C 失败策略：

- 缺少 prerequisites：`SKIPPED`，不影响总回归。
- prerequisites 存在但检查文件损坏或 demo 返回非 0：记录 `FAIL`。
- 第一版中 Project C `FAIL` 默认不让总回归失败，但 summary 必须清楚标注。这是因为 Project C
  仍依赖外部 gem5 环境；Project F 才是当前默认 chain 中的 hard report gate。

如果未来 CI runner 固定提供 gem5 环境，可以增加 strict Project C profile。

## 6. Output Design

Project R 生成：

```text
artifacts/regression_summary.md
```

summary 至少包含：

- timestamp。
- git branch。
- git commit hash。
- dirty working tree indicator。
- build status。
- Project B status。
- Project D status。
- Project E status。
- Project F status。
- Project C status。
- key output paths。
- scope boundary。

建议结构：

```markdown
# Project R Headless Regression Summary

## Run Metadata

- Timestamp:
- Git branch:
- Git commit:
- Dirty working tree:
- Host:
- Runner:

## Status Matrix

| Step | Component | Status | Hard Gate | Notes |
| --- | --- | --- | --- | --- |
| 0 | Environment check | PASS/FAIL | yes | ... |
| 1 | LT build | PASS/FAIL | yes | ... |
| 2 | Project D | PASS/FAIL | yes | ... |
| 3 | Project E | PASS/FAIL | yes | ... |
| 4 | Project F | PASS/FAIL | yes | ... |
| 5 | Project B | PASS/FAIL/SKIPPED | no | optional soft check |
| 6 | Project C | PASS/FAIL/SKIPPED | no | gem5-dependent optional check |

## Key Output Paths

- Project D trace:
- Project D summary:
- Project D comparison:
- Project E trace:
- Project E summary:
- Project E comparison:
- Project F summary:
- Project F report:
- Project B outputs:
- Project C outputs:

## Scope Boundary

- No cycle accuracy validation.
- No RTL / silicon / profiler correlation.
- No gem5-SystemC live co-simulation.
- Regression validates demo chain health and artifact generation only.
```

Status 语义：

- `PASS`：命令返回 0，且必要 output / marker 检查通过。
- `FAIL`：命令返回非 0，或必要 output / marker 缺失。
- `SKIPPED`：optional step prerequisites 不存在，且跳过原因已记录。

summary 应该使用中文解释工程语义，但关键 status token 保持英文，方便 grep 和 CI parsing。

## 7. `.gitignore` Plan

建议 `artifacts/` 作为 generated outputs 被忽略。

当前设计中：

- `artifacts/regression_summary.md` 是每次回归运行生成的本地结果。
- 它包含 timestamp、branch、commit、dirty state 和本机路径，属于 run-specific artifact。
- 不应该把 `artifacts/regression_summary.md` 提交进 Git。

如果需要提交示例 summary，建议新增文档路径：

```text
docs/sample_regression_summary.md
```

示例文件应该使用脱敏、稳定、非本机依赖的内容，只展示 summary format，不代表某次真实
regression 结果。

Project R 第一版实现时应确认 `.gitignore` 包含：

```text
artifacts
```

如已存在，则不需要修改 `.gitignore`。

## 8. Failure Policy

### Hard Fail Steps

以下步骤失败会导致脚本最终返回非 0：

- Step 0：environment check。
- Step 1：LT build。
- Step 2：Project D demo。
- Step 3：Project E demo。
- Step 4：Project F demo。

这些步骤代表当前 architecture-level performance modeling framework 的核心 demo chain。
任何 hard fail 都说明当前 checkout 不能作为完整证据包交付。

### Optional / Soft Steps

以下步骤可以 `SKIPPED`，默认不导致脚本失败：

- Step 5：Project B demo。
- Step 6：Project C check。

Project B soft failure 的处理：

- demo script 不存在：`SKIPPED`。
- demo script 存在但失败：`FAIL`，默认不影响整体 exit code。
- summary 中写清楚 Project B 是 optional soft check。

Project C skip / failure 的处理：

- gem5 extraction prerequisites 不存在：`SKIPPED`。
- prerequisites 存在但检查失败：`FAIL`，默认不影响整体 exit code。
- summary 中写清楚 Project C 可能依赖 gem5 环境或外部生成结果。

### Summary Recording

无论成功、失败或跳过，脚本都应尽力生成 `artifacts/regression_summary.md`。如果 hard fail
发生在 summary 目录创建之前，脚本应先创建 `artifacts/`，再记录失败原因。

每个失败记录至少包含：

- step name。
- command。
- exit code。
- short failure reason。
- log path 或 last relevant stderr/stdout snippet。
- expected output path / marker。

### Intermediate Results

Project R 第一版保留中间 results，不主动删除各 demo 生成的输出：

- 便于失败后审计。
- 避免破坏开发者正在检查的 generated artifacts。
- 与当前 generated files policy 一致：results 是本地生成物，不提交进 Git。

如未来 CI 需要 clean run，可增加显式 `--clean` 选项；默认不删除 `examples/lt/results/`、
`examples/at/results/`、`artifacts/` 或 `build/`。

## 9. Validation Plan

Project R 实现完成后，最小验证命令：

```bash
bash scripts/run_all_regressions.sh
cat artifacts/regression_summary.md
git status
git ls-files examples/lt/results | head
git ls-files examples/at/results | head
```

验证目标：

- `bash scripts/run_all_regressions.sh` 在 Ubuntu headless 环境从 repo root 可运行。
- hard gate 全部通过时，脚本 exit code 为 0。
- hard gate 任一失败时，脚本 exit code 非 0。
- optional Project B / Project C 缺 prerequisites 时可记录 `SKIPPED`。
- `artifacts/regression_summary.md` 包含 metadata、status matrix、key output paths 和
  scope boundary。
- `git status` 不应显示被误提交的 generated results 需求。
- `git ls-files examples/lt/results | head` 应为空或只显示历史上已经被错误跟踪的文件，用于
  发现 generated results policy 偏差。
- `git ls-files examples/at/results | head` 应为空或只显示历史上已经被错误跟踪的文件，用于
  发现 generated results policy 偏差。

如果需要从 Mac 打包 Project R patch 到 Ubuntu，使用：

```bash
tar --disable-copyfile --no-xattrs
```

避免 macOS resource fork 和 xattrs 生成 `._*` 文件污染源码。

## 10. Interview Framing

Project R 的面试价值是把项目叙事从单点 demo 推进到可回归的 modeling framework：

- From demos to reproducible modeling framework：不只是能跑一个脚本，而是能从 repo
  root 一键重建主要 evidence chain。
- From ad-hoc scripts to regression discipline：把 build、demo、summary、optional
  dependency 和 dirty state 都纳入可审计流程。
- Protects the C++ simulator：Project D 的 standalone C++ replay engine 和 Python/C++
  summary equivalence 被纳入 hard gate。
- Protects the memory model：Project E 的 banked memory controller queueing model 被纳入
  hard gate，避免 queueing / latency / output schema 被静默破坏。
- Protects the correlation report：Project F 的 qualitative trend-level correlation report
  被纳入 hard gate，同时继续声明 no cycle accuracy、no RTL/silicon/profiler correlation。

推荐面试表达：

```text
After building several standalone demos, I added a headless regression harness
to turn the project into a reproducible modeling workflow. The harness rebuilds
the LT lab, runs the C++ replay engine, runs the banked memory controller model,
checks the trend-correlation report, and emits an auditable summary with git
metadata. It validates demo-chain health and artifact contracts; it does not
claim cycle accuracy or hardware correlation.
```

## 11. Current / Supported / Not Supported / Future Work

### Current

Project R 当前是设计文档。它定义未来 `scripts/run_all_regressions.sh` 的 scope、steps、
failure policy 和 summary format。

### Supported

设计支持：

- Ubuntu headless regression。
- repo root execution。
- bash strict mode。
- hard gates for environment、LT build、Project D、Project E、Project F。
- optional Project B / Project C health checks。
- generated `artifacts/regression_summary.md`。
- generated results 不提交进 Git。

### Not Supported

设计不支持：

- GUI-based regression。
- gem5-SystemC live co-simulation。
- cycle accuracy validation。
- RTL / silicon / profiler correlation。
- 自动清理所有 generated outputs。
- 改写 Project B/C/D/E/F 的输出语义。

### Future Work

后续可以小步扩展：

- 增加 `--strict-project-b` 和 `--strict-project-c` profile。
- 增加 per-step log files，例如 `artifacts/logs/project_d.log`。
- 增加 summary JSON，例如 `artifacts/regression_summary.json`，方便 CI parsing。
- 增加 AT lab regression profile，但应作为独立阶段设计，避免混淆 LT / AT mainline。
- 增加 clean-run mode，但默认仍保留中间 results 便于审计。
