# Project X: Apple / NVIDIA / Arm Industry Evidence Release Pack

schema_version: `industry-r1.0`

## Purpose

Project X 把 Stage 2 已进入 portfolio evidence harness 的 AT-6 / AT-7 / AT-8
证据组织成一个面向 portfolio、interview 和 release review 的 industry-inspired
release pack。它不新增 simulation model，不修改 AT-6 / AT-7 / AT-8 core
simulation `.cpp`，也不改变 p0.5 portfolio validation 行为。

This release pack is an industry-inspired mapping layer over bounded synthetic architecture labs. It does not claim Apple Silicon simulation, NVIDIA GPU simulation, Arm CHI compliance, AXI compliance, ACE compliance, real NoC behavior, real cache coherency, cycle-accurate modeling, silicon validation, or production signoff.

## Why This Exists

AT-6 / AT-7 / AT-8 已经有可复现 evidence artifacts：

- `summary.csv` 提供 metrics 和 case coverage。
- `comparison.md` 提供工程解释、recommendation 和 claim boundary。
- `tools/run_portfolio_validation.py` 以 p0.5 schema 验证 artifacts、PASS marker
  和 claim-boundary wording。

Project X 的作用是增加一层面向产业表达的问题类型映射，让 reviewer 能快速理解这些
synthetic labs 分别对应哪类 SoC architecture performance conversation。

## Project Y Decision Layer

Project Y 在 Project X 之上增加 workload-to-bottleneck decision layer。Project X
回答 “AT-6 / AT-7 / AT-8 evidence 如何映射到 industry-inspired problem
families”；Project Y 则回答 “给定 workload symptoms，应优先讨论哪个 evidence
family”。

Project Y artifacts:

- `tools/classify_workload_bottleneck.py`
- `examples/workloads/sample_workload_symptoms.csv`
- `docs/metrics_and_diagnosis/workload_bottleneck_classifier.md`
- `docs/generated/workload_bottleneck_classification.md`

Project Y maps:

- `shared_fabric_pressure` -> AT-6 -> Apple-like heterogeneous SoC shared fabric pressure
- `throughput_bandwidth_wall` -> AT-7 -> NVIDIA-like throughput engine bandwidth wall
- `noc_qos_coherency_boundary` -> AT-8 -> Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure
- `mixed_or_uncertain` -> needs more evidence

It is a bounded rule-based classifier, not machine learning and not real
hardware profiling. It does not add a SystemC simulation model, does not
regenerate trace CSV, and does not change portfolio evidence harness p0.5.

## Project Z Recommendation Layer

Project Z is the recommendation layer of this release pack. Project X organizes
AT-6 / AT-7 / AT-8 evidence into industry-inspired problem families; Project Y
classifies workload symptoms into bottleneck families; Project Z turns those
families into bounded architecture recommendation families.

Project Z artifacts:

- `tools/generate_architecture_recommendations.py`
- `docs/metrics_and_diagnosis/architecture_recommendation_engine.md`
- `docs/generated/architecture_recommendations.md`

Project Z maps:

- `shared_fabric_pressure` -> `fabric_mitigation`
- `throughput_bandwidth_wall` -> `bandwidth_wall_mitigation`
- `noc_qos_coherency_boundary` -> `noc_qos_boundary_mitigation`
- `mixed_or_uncertain` -> `mixed_evidence_required`

It is a bounded rule-based recommendation engine and architecture reasoning
layer, not an optimizer, not machine learning, not real hardware profiling, and
not automatic hardware optimization. It does not add a SystemC simulation model,
does not regenerate trace CSV, and does not change portfolio evidence harness
p0.5.

## Project AA Scenario Decision Benchmark Layer

Project AA is the scenario-level decision benchmark layer. Project X organizes
AT-6 / AT-7 / AT-8 evidence into industry-inspired problem families; Project Y
classifies workload symptoms; Project Z turns those families into bounded
recommendation families; Project AA compares candidate actions under scenario
constraints and emits a bounded recommended action.

Project AA artifacts:

- `tools/run_scenario_decision_benchmark.py`
- `examples/scenarios/sample_architecture_scenarios.csv`
- `docs/metrics_and_diagnosis/scenario_decision_benchmark.md`
- `docs/generated/scenario_decision_benchmark.md`

Project AA maps:

- `shared_fabric_pressure` -> `fabric_decision`
- `throughput_bandwidth_wall` -> `bandwidth_wall_decision`
- `noc_qos_coherency_boundary` -> `noc_qos_boundary_decision`
- `mixed_or_uncertain` -> `mixed_decision`

It is a bounded rule-based scenario decision benchmark and architecture
reasoning layer, not an optimizer, not machine learning, not real hardware
profiling, not automatic hardware optimization, and not real design-space
exploration. It does not add a SystemC simulation model, does not regenerate
trace CSV, and does not change portfolio evidence harness p0.5.

## Project AB Architecture Review Memo Layer

Project AB is the architecture review memo layer. Project X organizes AT-6 /
AT-7 / AT-8 evidence into industry-inspired problem families; Project Y
classifies workload symptoms; Project Z turns families into bounded
recommendations; Project AA benchmarks scenario decisions; Project AB turns
those decisions into architecture decision memos.

Project AB artifacts:

- `tools/generate_architecture_decision_memos.py`
- `examples/decision_memos/sample_decision_memo_requests.csv`
- `docs/metrics_and_diagnosis/architecture_decision_memo_generator.md`
- `docs/generated/architecture_decision_memos.md`

Project AB memo types:

- `fabric_memo`
- `bandwidth_wall_memo`
- `noc_qos_boundary_memo`
- `mixed_evidence_memo`

It is a bounded rule-based architecture decision memo generator and architecture
reasoning layer, not an optimizer, not machine learning, not real hardware
profiling, not automatic hardware optimization, and not real design-space
exploration. It does not add a SystemC simulation model, does not regenerate
trace CSV, and does not change portfolio evidence harness p0.5.

## Repository Evidence Foundation

当前 portfolio evidence harness schema 是 `p0.5`。它验证 Stage 1
AT-1/AT-2/AT-3/AT-4/AT-5/K/L，以及 Stage 2 AT-6/AT-7/AT-8。

Industry release pack schema 是 `industry-r1.0`。它读取现有 Stage 2 artifacts：

- `examples/at/results/project_at6_heterogeneous_soc_fabric/summary.csv`
- `examples/at/results/project_at6_heterogeneous_soc_fabric/comparison.md`
- `examples/at/results/project_at7_gpu_like_throughput_saturation/summary.csv`
- `examples/at/results/project_at7_gpu_like_throughput_saturation/comparison.md`
- `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/summary.csv`
- `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/comparison.md`

生成的 matrix 位于：

- `docs/generated/industry_evidence_matrix.md`

## Industry-Inspired Mapping

| Project | Industry-inspired mapping | Problem type | Primary evidence |
| --- | --- | --- | --- |
| AT-6 | Apple-like heterogeneous SoC shared fabric pressure | heterogeneous initiators、shared fabric / shared memory pressure、bandwidth cap、latency-sensitive flow protection、starvation risk | `summary.csv` / `comparison.md` |
| AT-7 | NVIDIA-like throughput engine bandwidth wall | throughput engine、outstanding-depth sensitivity、bandwidth saturation、latency hiding approximation、queue buildup、burstiness、memory wall | `summary.csv` / `comparison.md` |
| AT-8 | Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure | QoS classes、route contention、coherency-boundary pressure、ordering delay、read/write interference、starvation / collapse signal | `summary.csv` / `comparison.md` |

## Apple-Like Mapping

AT-6 对应 Apple-like heterogeneous SoC shared fabric pressure 的问题类型。它可以用来讨论
CPU-like、GPU-like、NPU-like、ISP-like、DMA-like architectural roles 如何在一个
bounded shared fabric / shared memory pressure 场景下互相影响。

Supported discussion:

- heterogeneous initiators
- shared fabric / shared memory pressure
- bandwidth cap
- latency-sensitive flow protection
- starvation risk
- unified-memory-inspired architecture pressure

Boundary: 这不是 Apple Silicon simulation，不声称 M-series internal fabric，不声称
real unified memory controller，不声称真实 Neural Engine / GPU / ISP behavior，也不是
silicon validation 或 production signoff。

## NVIDIA-Like Mapping

AT-7 对应 NVIDIA-like throughput engine bandwidth wall / GPU-like memory saturation
problem type。它可以用来讨论 throughput-oriented lanes、outstanding depth、
latency hiding approximation、queue buildup、burstiness 和 memory wall。

Supported discussion:

- throughput engine
- outstanding-depth sensitivity
- bandwidth saturation
- latency hiding approximation
- queue buildup
- burstiness
- roofline-like intuition

Boundary: 这不是 NVIDIA GPU simulation，不声称 CUDA execution modeling，不声称
SM scheduler behavior 或 warp scheduler behavior，不声称 real HBM controller、
Tensor Core behavior 或 TMEM behavior，不是 cycle-accurate modeling，也不是
silicon validation 或 production signoff。

## Arm-Like Mapping

AT-8 对应 Arm-like AMBA-inspired interconnect / NoC QoS / coherency-boundary problem
type。它可以用来讨论 QoS classes、route contention、coherency-boundary pressure、
ordering delay、read/write interference 和 starvation / collapse signal。

Supported discussion:

- QoS classes
- route contention
- coherency-boundary pressure
- ordering delay
- read/write interference
- starvation / collapse signal
- protocol-inspired but not protocol-compliant behavior

Boundary: 这不是 Arm CHI compliance，不是 AXI compliance，不是 ACE compliance，
不声称 real AMBA protocol behavior，不声称 real NoC behavior，不声称 real cache
coherency，不是 cycle-accurate modeling，也不是 silicon validation 或 production
signoff。

## What Can Be Claimed

- Current: AT-6 / AT-7 / AT-8 已经进入 portfolio evidence harness p0.5。
- Current: Project X 已实现 release-pack mapping layer，schema_version 是
  `industry-r1.0`。
- Supported: 可以说这些 labs 支持 bounded synthetic architecture exploration、
  bottleneck isolation、trend comparison、evidence-driven recommendation 和
  interview discussion。
- Supported: 可以说 AT-6 / AT-7 / AT-8 分别映射 Apple-like、NVIDIA-like、Arm-like
  industry problem families。

## What Cannot Be Claimed

- Not supported: Apple Silicon simulation.
- Not supported: NVIDIA GPU simulation.
- Not supported: Arm CHI compliance.
- Not supported: AXI compliance.
- Not supported: ACE compliance.
- Not supported: real AMBA protocol behavior.
- Not supported: real NoC behavior.
- Not supported: real cache coherency.
- Not supported: real unified memory controller.
- Not supported: real HBM controller.
- Not supported: CUDA execution modeling.
- Not supported: SM scheduler behavior.
- Not supported: Tensor Core behavior.
- Not supported: TMEM behavior.
- Not supported: cycle-accurate modeling.
- Not supported: silicon validation.
- Not supported: production signoff.

## How To Validate

生成 industry evidence matrix：

```bash
python3 tools/generate_industry_evidence_matrix.py --strict
```

保持 portfolio p0.5 validation 不变：

```bash
python3 tools/run_portfolio_validation.py --at-build-dir build-at
```

Expected Project X output:

```text
Industry Evidence Matrix PASS
projects=AT-6,AT-7,AT-8
industry_mappings=Apple-like,NVIDIA-like,Arm-like
claim_boundary=PASS
schema_version=industry-r1.0
```

Expected Project Y output:

```text
Workload Bottleneck Classifier PASS
workloads=6
families=shared_fabric_pressure,throughput_bandwidth_wall,noc_qos_coherency_boundary,mixed_or_uncertain
claim_boundary=PASS
schema_version=classifier-r1.0
```

Expected Project Z output:

```text
Architecture Recommendation Engine PASS
workloads=6
recommendation_families=fabric_mitigation,bandwidth_wall_mitigation,noc_qos_boundary_mitigation,mixed_evidence_required
claim_boundary=PASS
schema_version=recommendation-r1.0
```

Expected Project AA output:

```text
Scenario Decision Benchmark PASS
scenarios=6
decision_families=fabric_decision,bandwidth_wall_decision,noc_qos_boundary_decision,mixed_decision
claim_boundary=PASS
schema_version=scenario-r1.0
```

Expected Project AB output:

```text
Architecture Decision Memo Generator PASS
memos=6
memo_types=fabric_memo,bandwidth_wall_memo,noc_qos_boundary_memo,mixed_evidence_memo
claim_boundary=PASS
schema_version=memo-r1.0
```

Expected p0.5 output:

```text
Portfolio Evidence Pack PASS
stage1_projects=AT-1,AT-2,AT-3,AT-4,AT-5,K,L
stage2_projects=AT-6,AT-7,AT-8
projects=AT-1,AT-2,AT-3,AT-4,AT-5,K,L,AT-6,AT-7,AT-8
claim_boundary=PASS
schema_version=p0.5
```

## Interview Usage

30 秒说法：

> Stage 2 takes my reproducible SystemC/TLM evidence chain and maps three bounded
> synthetic labs to industry-inspired problem families: Apple-like heterogeneous
> shared fabric pressure, NVIDIA-like throughput-engine bandwidth wall, and
> Arm-like AMBA-inspired NoC QoS / coherency-boundary pressure. The key is not
> claiming real company IP or protocol compliance; the key is evidence-backed
> architecture reasoning with explicit claim boundaries.

面试展开时按这个顺序讲：

1. 先说 p0.5 portfolio harness 已经验证 AT-6 / AT-7 / AT-8 artifacts。
2. 再说 Project X 的 `industry-r1.0` matrix 只是 mapping layer。
3. 用 Project Y 的 `classifier-r1.0` output 说明 workload symptoms 如何指向
   bounded bottleneck family。
4. 用 Project Z 的 `recommendation-r1.0` output 说明 bottleneck family 如何转成
   evidence-backed action family。
5. 用 Project AA 的 `scenario-r1.0` output 说明 candidate actions 如何在
   scenario constraints 下变成 bounded recommended action。
6. 用 Project AB 的 `memo-r1.0` output 说明 scenario decision 如何变成
   architecture review memo。
7. 每个 mapping 只讲 problem type、metrics、observed bottleneck 和 bounded
   recommendation。
8. 最后主动说 unsupported claims，显示 claim boundary discipline。

## Claim Boundary

Project X 只组织和解释现有 evidence。它不新增模型，不重新生成 trace，不改变
summary CSV schema，不改变 p0.5 portfolio validation 输出。它是面向产业表达的
bounded synthetic architecture exploration release pack，不是 vendor-specific
implementation、protocol compliance artifact、silicon validation result 或 production
signoff package。

Project Y 只读取 workload symptom CSV 并生成 classifier markdown。它是 bounded
rule-based architecture reasoning tool，不是 Apple Silicon simulation、NVIDIA GPU
simulation、Arm CHI compliance、AXI compliance、ACE compliance、real hardware
profiling、real NoC behavior、real cache coherency、cycle-accurate modeling、
silicon validation 或 production signoff。

Project Z 只读取 workload symptom CSV 和 Project Y classifier markdown，并生成
architecture recommendation markdown。它是 bounded rule-based recommendation
engine，不是 Apple Silicon simulation、NVIDIA GPU simulation、Arm CHI compliance、
AXI compliance、ACE compliance、real hardware profiling、automatic hardware
optimization、real NoC behavior、real cache coherency、cycle-accurate modeling、
silicon validation 或 production signoff。

Project AA 只读取 architecture scenario CSV，并生成 scenario decision benchmark
markdown。它是 bounded rule-based scenario decision benchmark，不是 Apple Silicon
simulation、NVIDIA GPU simulation、Arm CHI compliance、AXI compliance、ACE
compliance、real hardware profiling、automatic hardware optimization、real
design-space exploration、real NoC behavior、real cache coherency、
cycle-accurate modeling、silicon validation 或 production signoff。

Project AB 只读取 memo request CSV 和 Project AA/Z/Y generated markdown，并生成
architecture decision memo markdown。它是 bounded rule-based architecture
decision memo generator，不是 Apple Silicon simulation、NVIDIA GPU simulation、
Arm CHI compliance、AXI compliance、ACE compliance、real hardware profiling、
automatic hardware optimization、real design-space exploration、real NoC
behavior、real cache coherency、cycle-accurate modeling、silicon validation 或
production signoff。
