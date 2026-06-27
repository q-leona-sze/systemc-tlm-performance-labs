# SystemC/TLM 架构性能建模实验链

《芯片架构建模与性能分析：由 SystemC/TLM 到架构诊断》的公开 companion repository。

这个仓库把可控 workload 转成可审查的 trace、metrics、sweep、comparison 与
diagnosis，用于早期 SoC architecture performance modeling 的方法学习、实验复现和
架构诊断讨论。

```text
workload → trace → metrics → sweep → comparison → diagnosis
```

## 从这里开始

- LT 主线从 [`examples/lt/`](examples/lt/) 开始：trace replay、latency decomposition、
  bank conflict、queueing 与 workload bottleneck analysis。
- AT 主线从 [`examples/at/`](examples/at/) 开始：four-phase timing、multi-initiator
  arbitration、QoS-like sensitivity、backpressure、shared-fabric 与 bounded NoC-style
  pressure exploration。
- 方法、建模层级、指标、validation 与产业映射见 [`docs/`](docs/)。
- evidence summary、classification、recommendation、scenario 与 memo 工具见
  [`tools/`](tools/)。

## LT 主线地图

| 范围 | 路径 | 关注点 |
| --- | --- | --- |
| Trace replay | `examples/lt/replay_cpp/` | normalized trace、latency 与 throughput metrics |
| Banked memory | `examples/lt/banked_memory_controller_cpp/` | bank mapping、queueing、row-buffer locality、tail latency |
| RTL reference | `examples/lt/rtl_banked_memory_controller/` | optional Verilator bounded correlation path |
| Analysis tools | `examples/lt/tools/` | trace conversion、sweep、comparison、validation packet |
| Fixtures | `examples/lt/traces/` | small reproducible trace inputs, including gem5-labelled fixtures |

LT 的核心指标包括 `queue_delay_ns`、`target_service_delay_ns`、
`bank_conflict_delay_ns`、`p95/p99 latency`、throughput、bank utilization 与
rejected transaction 计数。

## AT 主线地图

| Lab | 关注点 |
| --- | --- |
| AT-1 | four-phase memory transaction timing and queue visibility |
| AT-2 | multi-initiator arbitration, fairness and tail latency |
| AT-3 | QoS-like policy sensitivity and SLA violations |
| AT-4 | cache-like shared resource and MSHR pressure |
| AT-5 | downstream backpressure and QoS collapse |
| AT-6 | heterogeneous shared-memory fabric pressure |
| AT-7 | GPU-like throughput saturation and bandwidth-wall exploration |
| AT-8 | AMBA-inspired QoS, route contention and coherency-boundary pressure |

AT-1 至 AT-8 都是 bounded synthetic architecture experiments；它们支持趋势、
权衡与诊断讨论，不被表述为真实产品模型。

## 文档地图

| 范围 | 路径 |
| --- | --- |
| Methodology | `docs/methodology/` |
| LT / AT modeling levels | `docs/modeling_levels/{lt,at}/` |
| Metrics and diagnosis | `docs/metrics_and_diagnosis/` |
| Validation and reproducibility | `docs/{validation,reproducibility}/` |
| Portfolio and case study | `docs/portfolio/` |
| Industry-inspired mapping | `docs/industry_mapping/` |
| Generated evidence snapshots | `docs/generated/` |

Generated reports 是由对应输入和脚本生成的证据快照，不是手写 ground truth。

## 工具链

`tools/` 维护仓库级 evidence chain：

- workload bottleneck classification；
- architecture recommendations；
- scenario decision benchmark；
- architecture decision memo generation；
- portfolio evidence summary 与 industry evidence matrix generation；
- portfolio validation 与 visual evidence-card rendering。

`examples/lt/tools/` 和 `examples/at/tools/` 贴近各自模型，负责 demo、sweep、
trace analysis 与 comparison orchestration。

## 快速开始

### 依赖边界

- CMake 3.24+。
- 默认 build 使用 C++17 compiler；C++20 是 required compatibility smoke target；
  C++23 是 optional experimental compatibility。
- 只有 `BUILD_AT_LABS=ON` 时才需要 SystemC。SystemC 3.0.2 是 primary target；
  SystemC 2.3.4 仅作为 compatibility reference。
- Python 3.13 和 3.14 是 support targets。基础 tools 只使用 standard library；
  `matplotlib>=3.8` 仅用于可选 portfolio-card rendering。
- gem5 与 Verilator 是可选外部工具。

默认 LT baseline 构建 standalone LT labs，不要求 SystemC：

```bash
cmake -S . -B artifacts/local-build-lt \
  -DBUILD_LT_LABS=ON \
  -DBUILD_AT_LABS=OFF \
  -DBUILD_RTL_REFERENCE=OFF
cmake --build artifacts/local-build-lt --parallel
```

AT targets 需要提供 SystemC 安装前缀。resolver 接受 `SystemC_DIR`、
`CMAKE_PREFIX_PATH`、`SYSTEMC_ROOT`、`SYSTEMC_HOME`、`USER_SYSTEMC_ROOT`，
也接受 include/lib pair：

```bash
export SYSTEMC_HOME="$HOME/local/systemc-3.0.2"
cmake -S . -B artifacts/local-build-at \
  -DSYSTEMC_HOME="$SYSTEMC_HOME" \
  -DBUILD_LT_LABS=ON \
  -DBUILD_AT_LABS=ON \
  -DSCTL_CXX_STANDARD=17
cmake --build artifacts/local-build-at --target project_at1_four_phase_memory_timing --parallel
```

Python 环境由调用者选择。若需要本地隔离环境：

```bash
PYTHON=python3 VENV_DIR=artifacts/venv/local bash scripts/setup_python_env.sh
```

SystemC 3.0.2 安装步骤、Python 3.13/3.14 策略和 Ubuntu validation matrix 见
[`docs/reproducibility/ubuntu_modern_toolchain_validation.md`](docs/reproducibility/ubuntu_modern_toolchain_validation.md)。

## Current / Supported / Not Supported / Future Work

| Category | Scope |
| --- | --- |
| Current | LT replay/queueing labs, AT-1 through AT-8, reproducible tools, curated evidence snapshots and methodology documents are present. The modern-toolchain entries are targets until a platform-specific artifact records a PASS. |
| Supported targets | Ubuntu 24.04 LTS or newer; SystemC 3.0.2 primary target; CMake 3.24+; GCC 13+ with GCC 14 recommended; C++17 default; C++20 smoke; Python 3.13/3.14. |
| Compatibility | SystemC 2.3.4 may be used for compatibility experiments, but new validation targets SystemC 3.0.2. |
| Not Supported | cycle-accurate claims, AXI/CHI protocol compliance, real NoC or DRAM timing claims, silicon validation and production signoff. |
| Future Work | Record real Ubuntu matrix evidence, external-reference correlation with clearly identified inputs, expanded workload fixtures, optional RTL/profiler paths and additional architecture case studies. |

## 结果与本地产物

已提交的 `results/` 内容只保留小型、可复现、经过挑选的 evidence snapshots。
raw traces、stdout/stderr、临时 CSV 和本地构建输出应写入已忽略的 `artifacts/`
或 build directories。

## 第三方归属

本仓库保留必要的第三方 copyright、license 与 attribution。见 [`NOTICE`](NOTICE)。
已有 copyright headers 的源文件必须保留原 header。
