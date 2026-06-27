# Project R：Headless Regression Harness

Project R 是当前 `SystemC/TLM Architecture Performance Labs` 的 Ubuntu headless
回归入口。它把主要 demo chain 串成一条可审计的本地回归流程，用于验证当前
architecture-level performance modeling framework 没有被新改动破坏。

Project R 验证的是 demo chain health 和 generated artifact presence，不代表 cycle
accuracy validation。

> 现代 toolchain baseline 请使用
> [`ubuntu_modern_toolchain_validation.md`](ubuntu_modern_toolchain_validation.md) 与
> `bash scripts/ubuntu_verify.sh`。它只覆盖 standalone LT 与 AT book baseline，且 build、log
> 与 Python bytecode 全部隔离在 `artifacts/ubuntu-validation/<run-id>/`。本 Project R
> 文档保留 historical demo-chain regression contract；其既有 demo output path 不作为
> 新 book baseline 的验证路径。

## 如何运行

从仓库根目录执行：

```bash
bash scripts/run_all_regressions.sh
cat artifacts/regression_summary.md
```

SystemC 路径必须由调用者显式提供；脚本不内置本机用户名或路径：

```text
USER_SYSTEMC_LIB_DIR=/absolute/path/to/systemc/lib
USER_SYSTEMC_INCLUDE_DIR=/absolute/path/to/systemc/include
```

如果 SystemC 安装在其他路径，可以用环境变量覆盖：

```bash
USER_SYSTEMC_LIB_DIR=/absolute/path/to/systemc/lib \
USER_SYSTEMC_INCLUDE_DIR=/absolute/path/to/systemc/include \
bash scripts/run_all_regressions.sh
```

## 需要的环境

Project R 第一版面向 Ubuntu headless 环境，需要：

- `bash`
- `python3`
- `cmake`
- `git`
- `nproc`
- SystemC include / lib path

脚本必须从 repo root 执行。如果当前目录不包含 `CMakeLists.txt`、`docs/`、`scripts/`、
`tools/` 和 `examples/lt/`，脚本会直接失败并给出错误。

## 回归步骤

| Step | Project | 含义 | 策略 |
| --- | --- | --- | --- |
| 0 | Environment check | 检查 repo root、工具链和 SystemC 路径。 | hard fail |
| 1 | LT build | 运行 `cmake -S examples/lt -B build/examples/lt` 并构建 LT lab。 | hard fail |
| 2 | Project D | 运行 standalone C++ trace replay demo，保护 Python/C++ replay summary equivalence。 | hard fail |
| 3 | Project E | 运行 standalone C++ banked memory controller queueing model demo。 | hard fail |
| 4 | Project F | 运行 gem5 stats trend correlation report demo。 | hard fail |
| 5 | Project B | 运行 normalized trace replay bridge demo。 | optional soft check |
| 6 | Project C | 检查 gem5 SE extraction demo wrapper 或默认 generated outputs。 | optional / skipped |

关键命令包括：

```bash
python3 examples/lt/tools/demo_cpp_trace_replay_lab.py
python3 examples/lt/tools/demo_banked_memory_controller_lab.py
python3 examples/lt/tools/demo_gem5_stats_correlation_lab.py
python3 examples/lt/tools/demo_trace_replay_lab.py
```

Project C 当前可能依赖 gem5 binary、workload binary 或外部生成结果。如果没有明确
one-command demo wrapper，且默认 gem5 outputs 不存在，Project C 会标记为 `SKIPPED`，
不会导致总回归失败。

## 失败策略

这些步骤失败会让脚本最终返回非 0：

- environment check
- LT build
- Project D
- Project E
- Project F

这些步骤默认不会让脚本返回非 0：

- Project B：optional soft check；失败会写入 summary，但默认不破坏 hard-gate result。
- Project C：缺少 gem5 环境或默认 outputs 时标记 `SKIPPED`；部分 outputs 存在但不完整时
  标记 `FAIL`，但默认仍是 optional。

每一步都会打印：

```text
[regression] START ...
[regression] PASS ...
[regression] SKIP ...
[regression] FAIL ...
```

## 输出

脚本会创建：

```text
artifacts/regression_summary.md
artifacts/logs/
```

summary 至少包含：

- generated timestamp
- git branch
- git commit hash
- dirty working tree indicator
- LT build status
- Project B/C/D/E/F status
- key output paths
- scope boundary

重点输出路径：

```text
examples/lt/results/cpp_trace_replay_lab/summary.csv
examples/lt/results/project_e_banked_memory_controller/summary.csv
examples/lt/results/project_f_gem5_stats_correlation/correlation_summary.csv
```

如果运行环境不是 Git worktree，summary 会把 branch / commit / dirty state 标记为
unavailable 或 unknown。完整审计建议在带 `.git` metadata 的 checkout 中运行。

## Generated Outputs Policy

这些都是 generated local outputs，不应该提交进 Git：

- `artifacts/regression_summary.md`
- `artifacts/logs/`
- `examples/lt/results/`
- `examples/at/results/`
- `__pycache__/`
- `*.tar.gz`
- `.DS_Store`
- `._*`

当前 `.gitignore` 已忽略 `artifacts`、`examples/lt/results/` 和 `examples/at/results/`。
如果需要提交 summary 示例，应放在 `docs/sample_regression_summary.md`，不要提交真实
`artifacts/regression_summary.md`。

## Scope Boundary

Project R 不做：

- gem5-SystemC live co-simulation。
- cycle accuracy validation。
- RTL correlation。
- silicon correlation。
- profiler correlation。
- GUI regression。
- Project B/C/D/E/F 输出语义变更。
- Project D C++ replay core 变更。
- Project E C++ banked memory controller core 变更。

Project R 的面试表达重点是：

```text
从多个单点 demos，推进到可复现、可回归、可审计的 architecture-level modeling workflow。
它保护 C++ replay engine、banked memory controller model 和 trend correlation report
不被新改动静默破坏，但不声称 cycle accuracy 或硬件相关性。
```
