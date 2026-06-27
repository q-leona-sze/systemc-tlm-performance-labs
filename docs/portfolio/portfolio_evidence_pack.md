# Portfolio Evidence Pack

## 1. 目的

这份 evidence pack 把当前 repo 中的 LT and AT labs 串成一个可复现、可审阅、可用于面试讨论的作品集入口。Project P / S / U / V / W 不新增 SystemC/TLM 功能模型；它把 Stage 1 的 Project K/L 与 Project AT-1/AT-2/AT-3/AT-4/AT-5，以及 Stage 2 的 Project AT-6/AT-7/AT-8 的验证命令、生成结果、关键指标和 claim boundary 汇总成 portfolio-level evidence。

Portfolio evidence p0.5 验证 AT-6/7/8 evidence；Project Y 对 workload symptoms
分类；Project Z 把这些 family 转成 bounded architecture recommendations；Project AA
做 scenario decision benchmark；Project AB 把 decisions 转成 architecture memos。
这些层不会修改 p0.5 harness，也不会扩大模型 claim。

核心目标是让 reviewer 能从一条清楚路径理解项目：先看 architecture story，再运行 validation harness，再读取 CSV-derived evidence summary，最后回到各 Project report 查看细节。

## 2. Evidence Map

| Evidence Area | Projects | What It Shows | Primary Artifacts | How To Reproduce |
| --- | --- | --- | --- | --- |
| LT bottleneck characterization | Project K | synthetic workload pattern 如何触发 queueing、service latency、bank conflict proxy 和 bottleneck attribution | `project_k_workload_bottleneck_summary.csv`、`project_k_what_if_sweep_summary.csv`、`project_k_report.md` | `python3 examples/lt/tools/demo_project_k_workload_bottleneck_lab.py` |
| Evidence-driven recommendation | Project L | 如何把 Project K metrics 转成 bounded memory architecture recommendation | `project_l_recommendations.csv`、`project_l_recommendation_report.md` | `python3 examples/lt/tools/demo_project_k_workload_bottleneck_lab.py` |
| AT transaction timing | Project AT-1 | four-phase AT transaction timing、request acceptance、target service、response latency 和 back-pressure | `project_at1_summary.csv`、`project_at1_report.md`、case trace CSV | `python3 examples/at/tools/demo_project_at1_four_phase_memory_timing.py --build-dir build-at` |
| Arbitration / contention | Project AT-2 | multi-initiator arbitration policy 如何影响 fairness、back-pressure、throughput 和 p99 latency | `project_at2_policy_summary.csv`、`project_at2_report.md`、case trace CSV | `python3 examples/at/tools/demo_project_at2_multi_initiator_arbitration.py --build-dir build-at` |
| QoS-like sensitivity / SLA violation | Project AT-3 | weight vector、queue depth、service latency 如何影响 SLA violation、protected initiator 和 architecture recommendation | `project_at3_policy_sweep.csv`、`project_at3_recommendations.csv`、`project_at3_report.md` | `python3 examples/at/tools/demo_project_at3_qos_sensitivity_sla.py --build-dir build-at` |
| Cache-like shared-resource pressure | Project AT-4 | locality、hit/miss trend、MSHR-like outstanding miss pressure、shared interference / pollution proxy、p95 / p99 tail latency 和 diminishing return | `project_at4_summary.csv`、`project_at4_policy_sweep.csv`、`project_at4_recommendations.csv`、`project_at4_report.md` | `python3 examples/at/tools/demo_at4_cache_mshr_pressure.py --at-build-dir build-at` |
| Backpressure / QoS collapse | Project AT-5 | bounded ingress/downstream queues、downstream saturation、backpressure propagation 和 QoS policy limit | `project_at5_summary.csv`、`project_at5_policy_sweep.csv`、`project_at5_recommendations.csv`、`project_at5_report.md` | `python3 -B examples/at/tools/demo_at5_backpressure_qos_collapse.py --at-build-dir build-at` |
| Heterogeneous SoC shared-memory fabric pressure | Project AT-6 | bounded AT-level synthetic heterogeneous SoC problem type 下的 mixed traffic interference、bandwidth partitioning、latency-sensitive flow protection 和 starvation risk | `summary.csv`、`comparison.md` | `./build-at/project_at6_heterogeneous_soc_fabric --no-trace` |
| GPU-like throughput and memory saturation | Project AT-7 | bounded AT-level synthetic GPU-like throughput problem type 下的 outstanding-depth sensitivity、latency hiding approximation、bandwidth saturation、queue buildup 和 bandwidth wall | `summary.csv`、`comparison.md` | `./build-at/project_at7_gpu_like_throughput_saturation` |
| AMBA-inspired NoC QoS and coherency-boundary pressure | Project AT-8 | bounded AT-level synthetic AMBA-inspired NoC problem type 下的 QoS class pressure、route contention、coherency-boundary pressure、ordering pressure、read/write interference 和 recommendation logic | `summary.csv`、`comparison.md` | `./build-at/project_at8_amba_noc_qos_coherency_boundary` |
| Portfolio-level validation | Project P / S / U / V / W | Stage 1 K/L/AT-1/AT-2/AT-3/AT-4/AT-5 与 Stage 2 AT-6/AT-7/AT-8 的一键 PASS marker 检查和 CSV-derived evidence summary | `tools/run_portfolio_validation.py`、`tools/generate_portfolio_evidence_summary.py`、`docs/generated/portfolio_evidence_summary.md` | `python3 tools/run_portfolio_validation.py --at-build-dir build-at` |
| Architecture recommendation layer | Project Z | 把 Project Y bottleneck families 转换成 bounded architecture recommendation families 和 evidence-backed action | `tools/generate_architecture_recommendations.py`、`docs/generated/architecture_recommendations.md` | `python3 tools/generate_architecture_recommendations.py --input examples/workloads/sample_workload_symptoms.csv --classification docs/generated/workload_bottleneck_classification.md --output docs/generated/architecture_recommendations.md --strict` |
| Scenario decision benchmark | Project AA | 把 scenario constraints 和 candidate actions 转换成 bounded scenario-level recommended action | `tools/run_scenario_decision_benchmark.py`、`examples/scenarios/sample_architecture_scenarios.csv`、`docs/generated/scenario_decision_benchmark.md` | `python3 tools/run_scenario_decision_benchmark.py --input examples/scenarios/sample_architecture_scenarios.csv --output docs/generated/scenario_decision_benchmark.md --strict` |
| Architecture decision memo layer | Project AB | 把 Project AA scenario-level decision 转换成 bounded architecture review memo | `tools/generate_architecture_decision_memos.py`、`examples/decision_memos/sample_decision_memo_requests.csv`、`docs/generated/architecture_decision_memos.md` | `python3 tools/generate_architecture_decision_memos.py --requests examples/decision_memos/sample_decision_memo_requests.csv --scenario-report docs/generated/scenario_decision_benchmark.md --recommendation-report docs/generated/architecture_recommendations.md --classification-report docs/generated/workload_bottleneck_classification.md --output docs/generated/architecture_decision_memos.md --strict` |

## 3. 复现流程

先准备 AT build。推荐在 Ubuntu 验证环境中从 repo root 运行：

```bash
cmake -S examples/at -B build-at \
  -DUSER_SYSTEMC_INCLUDE_DIR=$HOME/local/systemc/include \
  -DUSER_SYSTEMC_LIB_DIR=$HOME/local/systemc/lib

cmake --build build-at --target project_at1_four_phase_memory_timing -j
cmake --build build-at --target project_at2_multi_initiator_arbitration -j
cmake --build build-at --target project_at3_qos_sensitivity_sla -j
cmake --build build-at --target project_at4_cache_mshr_pressure -j
cmake --build build-at --target project_at5_backpressure_qos_collapse -j
cmake --build build-at --target project_at6_heterogeneous_soc_fabric -j
cmake --build build-at --target project_at7_gpu_like_throughput_saturation -j
cmake --build build-at --target project_at8_amba_noc_qos_coherency_boundary -j
```

然后运行 Project P validation harness：

```bash
python3 tools/run_portfolio_validation.py --at-build-dir build-at
```

生成 portfolio evidence summary：

```bash
python3 tools/generate_portfolio_evidence_summary.py --strict
```

预期 portfolio PASS marker：

```text
Portfolio Evidence Pack PASS
stage1_projects=AT-1,AT-2,AT-3,AT-4,AT-5,K,L
stage2_projects=AT-6,AT-7,AT-8
projects=AT-1,AT-2,AT-3,AT-4,AT-5,K,L,AT-6,AT-7,AT-8
claim_boundary=PASS
schema_version=p0.5
```

## 4. Industry Release Pack 边界

industry release pack 与 portfolio validation p0.5 分离。Portfolio harness 验证
evidence existence 和 claim boundaries；industry release pack 把 evidence 映射到
industry-inspired problem families。

Project X adds `industry-r1.0` generated documentation over existing AT-6 /
AT-7 / AT-8 artifacts:

```bash
python3 tools/generate_industry_evidence_matrix.py --strict
```

预期 Project X PASS marker：

```text
Industry Evidence Matrix PASS
projects=AT-6,AT-7,AT-8
industry_mappings=Apple-like,NVIDIA-like,Arm-like
claim_boundary=PASS
schema_version=industry-r1.0
```

Project X 不改变 p0.5 validation output，不新增 simulation model，不重新生成 trace CSV，
不修改 AT-6 / AT-7 / AT-8 core `.cpp`，也不改变它们的 `summary.csv` schema。

## 4A. Project Y Workload Decision Layer

Project Y is separate from portfolio validation p0.5. It consumes workload
symptoms and maps them to the evidence families already validated by the
portfolio harness:

- `shared_fabric_pressure` -> AT-6 -> Apple-like heterogeneous SoC shared fabric pressure
- `throughput_bandwidth_wall` -> AT-7 -> NVIDIA-like throughput engine bandwidth wall
- `noc_qos_coherency_boundary` -> AT-8 -> Arm-like AMBA-inspired NoC QoS and coherency-boundary pressure
- `mixed_or_uncertain` -> needs more evidence

Run:

```bash
python3 tools/classify_workload_bottleneck.py \
  --input examples/workloads/sample_workload_symptoms.csv \
  --output docs/generated/workload_bottleneck_classification.md \
  --strict
```

预期 Project Y PASS marker：

```text
Workload Bottleneck Classifier PASS
workloads=6
families=shared_fabric_pressure,throughput_bandwidth_wall,noc_qos_coherency_boundary,mixed_or_uncertain
claim_boundary=PASS
schema_version=classifier-r1.0
```

Project Y does not add a SystemC simulation model, does not modify AT-6 / AT-7 /
AT-8 core simulation `.cpp`, does not modify their `summary.csv` schema, does
not regenerate trace CSV, and does not change portfolio validation p0.5
behavior.

## 4B. Project Z Architecture Recommendation Layer

Project Z is separate from portfolio validation p0.5. It consumes the Project Y
classifier output and maps bottleneck families to bounded recommendation
families:

- `shared_fabric_pressure` -> `fabric_mitigation`
- `throughput_bandwidth_wall` -> `bandwidth_wall_mitigation`
- `noc_qos_coherency_boundary` -> `noc_qos_boundary_mitigation`
- `mixed_or_uncertain` -> `mixed_evidence_required`

Run:

```bash
python3 tools/generate_architecture_recommendations.py \
  --input examples/workloads/sample_workload_symptoms.csv \
  --classification docs/generated/workload_bottleneck_classification.md \
  --output docs/generated/architecture_recommendations.md \
  --strict
```

预期 Project Z PASS marker：

```text
Architecture Recommendation Engine PASS
workloads=6
recommendation_families=fabric_mitigation,bandwidth_wall_mitigation,noc_qos_boundary_mitigation,mixed_evidence_required
claim_boundary=PASS
schema_version=recommendation-r1.0
```

Project Z does not add a SystemC simulation model, does not modify AT-6 / AT-7 /
AT-8 core simulation `.cpp`, does not modify their `summary.csv` schema, does
not regenerate trace CSV, and does not change portfolio validation p0.5
behavior. It is not automatic hardware optimization, not real hardware
profiling, and not production signoff.

## 4C. Project AA Scenario Decision Benchmark

Project AA is separate from portfolio validation p0.5. It consumes architecture
scenario rows and maps candidate actions to bounded scenario-level decisions:

- `shared_fabric_pressure` -> `fabric_decision`
- `throughput_bandwidth_wall` -> `bandwidth_wall_decision`
- `noc_qos_coherency_boundary` -> `noc_qos_boundary_decision`
- `mixed_or_uncertain` -> `mixed_decision`

Run:

```bash
python3 tools/run_scenario_decision_benchmark.py \
  --input examples/scenarios/sample_architecture_scenarios.csv \
  --output docs/generated/scenario_decision_benchmark.md \
  --strict
```

预期 Project AA PASS marker：

```text
Scenario Decision Benchmark PASS
scenarios=6
decision_families=fabric_decision,bandwidth_wall_decision,noc_qos_boundary_decision,mixed_decision
claim_boundary=PASS
schema_version=scenario-r1.0
```

Project AA does not add a SystemC simulation model, does not modify AT-6 / AT-7
/ AT-8 core simulation `.cpp`, does not modify their `summary.csv` schema, does
not regenerate trace CSV, and does not change portfolio validation p0.5
behavior. It is not automatic hardware optimization, not real hardware
profiling, not real design-space exploration, and not production signoff.

## 4D. Project AB Architecture Decision Memo Layer

Project AB is separate from portfolio validation p0.5. It consumes memo request
rows plus Project AA/Z/Y generated markdown and maps scenario decisions to
bounded architecture review memos:

- `fabric_memo`
- `bandwidth_wall_memo`
- `noc_qos_boundary_memo`
- `mixed_evidence_memo`

Run:

```bash
python3 tools/generate_architecture_decision_memos.py \
  --requests examples/decision_memos/sample_decision_memo_requests.csv \
  --scenario-report docs/generated/scenario_decision_benchmark.md \
  --recommendation-report docs/generated/architecture_recommendations.md \
  --classification-report docs/generated/workload_bottleneck_classification.md \
  --output docs/generated/architecture_decision_memos.md \
  --strict
```

Expected Project AB PASS marker:

```text
Architecture Decision Memo Generator PASS
memos=6
memo_types=fabric_memo,bandwidth_wall_memo,noc_qos_boundary_memo,mixed_evidence_memo
claim_boundary=PASS
schema_version=memo-r1.0
```

Project AB does not add a SystemC simulation model, does not modify AT-6 / AT-7
/ AT-8 core simulation `.cpp`, does not modify their `summary.csv` schema, does
not regenerate trace CSV, and does not change portfolio validation p0.5
behavior. It is not automatic hardware optimization, not real hardware
profiling, not real design-space exploration, and not production signoff.

LT K/L demo 依赖 Project E standalone C++ banked memory controller binary。如果本地 LT build 尚未准备好，先按 `README.md` 和 `examples/lt/README_performance_lab.md` 完成 LT build。根 CMake 只纳入书籍支持的 LT/AT targets。portfolio harness 使用明确的 AT named project targets 构建 AT-1/2/3/4/5/AT-6/AT-7/AT-8，并运行 demo 或 Stage 2 binary、检查 PASS marker、CSV contract 和关键 artifacts，不依赖 aggregate `at` target。

Project V adds AT-7 checks for:

- `examples/at/results/project_at7_gpu_like_throughput_saturation/summary.csv`
- `examples/at/results/project_at7_gpu_like_throughput_saturation/comparison.md`
- six expected cases: `low_occupancy`, `balanced_occupancy`, `high_occupancy`, `bandwidth_saturation`, `bursty_stress`, `throttled_occupancy`
- key `summary.csv` schema fields for latency, throughput, bandwidth, queue pressure, outstanding depth, stall ratio, hidden latency, exposed stall, saturation flag, and knee-point hint
- claim-boundary wording that keeps AT-7 as bounded AT-level synthetic exploration and does not claim NVIDIA GPU simulation, real GPU behavior, CUDA execution modeling, real HBM-controller behavior, cycle-accurate modeling, silicon validation, or production signoff

Project W adds AT-8 checks for:

- `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/summary.csv`
- `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/comparison.md`
- six expected cases: `baseline_qos_rr`, `latency_qos_priority`, `bulk_dma_pressure`, `boundary_crossing_stress`, `route_hotspot`, `mixed_qos_collapse`
- key `summary.csv` schema fields for latency, throughput, route utilization, ordering delay, boundary penalty, coherency-boundary events, read/write tail latency, QoS-class tail latency, starvation, collapse score, and recommendation
- claim-boundary wording that keeps AT-8 as bounded AT-level synthetic AMBA-inspired NoC QoS and coherency-boundary exploration and does not claim Arm CHI compliance, AXI compliance, ACE compliance, real AMBA protocol behavior, real NoC behavior, real cache coherency, cycle-accurate modeling, silicon validation, or production signoff

## 5. 关键结果产物

- Project K summary / sweep / report: `examples/lt/results/project_k_workload_bottleneck/`
- Project L recommendations / report: `examples/lt/results/project_l_memory_architecture_recommendation/`
- Project AT-1 summary / report / traces: `examples/at/results/project_at1_four_phase_memory_timing/`
- Project AT-2 policy summary / report / traces: `examples/at/results/project_at2_multi_initiator_arbitration/`
- Project AT-3 policy sweep / recommendations / report / traces: `examples/at/results/project_at3_qos_sensitivity_sla/`
- Project AT-4 summary / policy sweep / recommendations / report / traces: `examples/at/results/project_at4_cache_mshr_pressure/`
- Project AT-5 summary / policy sweep / recommendations / report / traces: `examples/at/results/project_at5_backpressure_qos_collapse/`
- Project AT-6 summary / comparison: `examples/at/results/project_at6_heterogeneous_soc_fabric/`
- Project AT-7 summary / comparison: `examples/at/results/project_at7_gpu_like_throughput_saturation/`
- Project AT-8 summary / comparison: `examples/at/results/project_at8_amba_noc_qos_coherency_boundary/`
- Generated portfolio evidence summary: `docs/generated/portfolio_evidence_summary.md`
- Generated industry evidence matrix: `docs/generated/industry_evidence_matrix.md`
- Industry release pack docs: `docs/industry_mapping/industry_evidence_release_pack.md`
- Project Y workload symptom input: `examples/workloads/sample_workload_symptoms.csv`
- Project Y generated classifier output: `docs/generated/workload_bottleneck_classification.md`
- Project Z recommendation engine docs: `docs/metrics_and_diagnosis/architecture_recommendation_engine.md`
- Project Z generated recommendations: `docs/generated/architecture_recommendations.md`
- Project AA scenario input: `examples/scenarios/sample_architecture_scenarios.csv`
- Project AA generated decision benchmark: `docs/generated/scenario_decision_benchmark.md`
- Project AB memo request input: `examples/decision_memos/sample_decision_memo_requests.csv`
- Project AB generated architecture decision memos: `docs/generated/architecture_decision_memos.md`

## 6. 这个 evidence pack 能回答的问题

- Which workload pattern creates memory bottlenecks?
- Which memory architecture action is supported by metrics?
- How does a four-phase AT transaction expose timing?
- How do arbitration policies affect fairness and p99 latency?
- How does weighted arbitration protect one initiator and hurt another?
- When does queue depth cause back-pressure?
- How do locality and hit/miss trend affect tail latency?
- When does MSHR-like outstanding miss pressure dominate?
- When does shared traffic interference or pollution proxy explain p95 / p99 growth?
- When does memory service latency dominate and make arbitration tuning insufficient?
- When do larger MSHR-like resources show diminishing return?
- When does downstream saturation make QoS priority insufficient?
- When do bounded queues propagate backpressure upstream?
- How does heterogeneous SoC shared-memory fabric pressure affect CPU-like, NPU-like, DMA-like, and ISP-like traffic?
- When does bandwidth capping protect latency-sensitive flows at the cost of throughput-oriented traffic?
- When does GPU-like throughput pressure stop improving useful throughput and mostly become queue delay?
- How do AMBA-inspired NoC QoS, route contention, and coherency-boundary pressure affect tail latency and bounded recommendation logic?
- How do AT-6 / AT-7 / AT-8 map to Apple-like, NVIDIA-like, and Arm-like
  industry-inspired problem families without claiming vendor-internal models?
- How does a classified bottleneck family become a bounded architecture
  recommendation family?
- Which architecture recommendation is supported by evidence?
- Which scenario-level action is most defensible under workload-specific
  constraints and candidate actions?
- How can a scenario-level decision be communicated as an architecture review
  memo with evidence chain, risk, and next measurements?

## 7. 面试使用方式

- Start with `docs/portfolio/portfolio_architecture_story.md` for narrative.
- Use `docs/portfolio/portfolio_evidence_pack.md` for reproducibility.
- Use `docs/generated/portfolio_evidence_summary.md` for metric snippets.
- Use `docs/industry_mapping/industry_evidence_release_pack.md` and
  `docs/generated/industry_evidence_matrix.md` for Project X industry-inspired
  mapping.
- Use `docs/metrics_and_diagnosis/workload_bottleneck_classifier.md` and
  `docs/generated/workload_bottleneck_classification.md` for Project Y
  workload-to-bottleneck decision discussion.
- Use `docs/metrics_and_diagnosis/architecture_recommendation_engine.md` and
  `docs/generated/architecture_recommendations.md` for Project Z
  family-to-action recommendation discussion.
- Use `docs/metrics_and_diagnosis/scenario_decision_benchmark.md` and
  `docs/generated/scenario_decision_benchmark.md` for Project AA
  scenario-level decision benchmark discussion.
- Use `docs/metrics_and_diagnosis/architecture_decision_memo_generator.md` and
  `docs/generated/architecture_decision_memos.md` for Project AB architecture
  decision memo discussion.
- Use `docs/portfolio/INTERVIEW_NOTES.md` for pitch.

## 8. 边界声明

Project P / S / U / V / W supports bounded portfolio and early architecture exploration discussion. It does not turn the repo into a production interconnect, protocol-complete model, real memory controller, real SoC fabric, real GPU simulator, real AMBA / NoC / cache-coherency implementation, or silicon correlation result.

- no AXI / CHI protocol compliance
- no ACE protocol compliance
- no real AMBA protocol behavior
- no cycle accuracy
- no real NoC model
- no real cache coherency
- no Apple Silicon simulation
- no NVIDIA GPU simulation
- no real GPU behavior
- no CUDA execution modeling
- no real HBM-controller behavior
- no cache coherence model
- no real L1/L2/L3 hierarchy model
- no real DRAM timing model
- no silicon validation
- no production signoff
- no real workload performance claim
