# LT 架构性能建模实验链

`examples/lt/` 是本书配套仓库的 LT 主线。它通过 trace replay、latency
decomposition、bank-conflict analysis、queueing 和 bounded memory-system
experiments，建立：

```text
workload → trace → metrics → sweep → comparison → diagnosis
```

完整 LT guide 见 [`README_performance_lab.md`](README_performance_lab.md)。

当前 standalone 路径包括 `replay_cpp/`、`banked_memory_controller_cpp/`、
`rtl_banked_memory_controller/`、`tools/`、`traces/`、`counter_samples/` 和
`validation_packet/`。
