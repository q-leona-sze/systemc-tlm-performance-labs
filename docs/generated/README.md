# Generated evidence snapshots

Files in this directory are generated evidence snapshots. Their conclusions must
not be hand-edited: regenerate them from the corresponding source inputs and
repository tools when the underlying evidence changes.

Primary generators live in `tools/`; the LT and AT demos that produce their source
CSV artifacts live under `examples/lt/tools/` and `examples/at/tools/`.

Snapshots are intentionally retained in the companion repository because they make
the workload-to-diagnosis evidence chain reviewable without claiming that generated
reports are independent ground truth.
