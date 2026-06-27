#!/usr/bin/env python3
from pathlib import Path
import matplotlib.pyplot as plt
import textwrap

OUT = Path("assets/portfolio")
OUT.mkdir(parents=True, exist_ok=True)

def save_card(filename, title, subtitle, body_lines, footer=None):
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    ax.text(
        0.06, 0.88, title,
        fontsize=28,
        fontweight="bold",
        va="top",
    )

    ax.text(
        0.06, 0.80, subtitle,
        fontsize=15,
        va="top",
    )

    y = 0.68
    for line in body_lines:
        wrapped = textwrap.wrap(line, width=82)
        for w in wrapped:
            ax.text(0.08, y, w, fontsize=18, va="top")
            y -= 0.065
        y -= 0.025

    if footer:
        ax.text(
            0.06, 0.06, footer,
            fontsize=12,
            va="bottom",
        )

    fig.savefig(OUT / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_bar_card(filename, title, subtitle, labels, before_after, ylabel, callout):
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_axes([0.12, 0.18, 0.78, 0.58])

    x = range(len(labels))
    width = 0.35

    before = [v[0] for v in before_after]
    after = [v[1] for v in before_after]

    ax.bar([i - width / 2 for i in x], before, width, label="baseline")
    ax.bar([i + width / 2 for i in x], after, width, label="changed")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=13)
    ax.set_ylabel(ylabel, fontsize=13)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    fig.text(0.06, 0.92, title, fontsize=26, fontweight="bold", va="top")
    fig.text(0.06, 0.86, subtitle, fontsize=14, va="top")
    fig.text(0.06, 0.06, callout, fontsize=15, va="bottom")

    fig.savefig(OUT / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_table_card(filename, title, subtitle, columns, rows, callout):
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_axes([0.04, 0.12, 0.92, 0.62])
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=columns,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(13)
    table.scale(1, 2.0)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(fontweight="bold")

    fig.text(0.06, 0.92, title, fontsize=26, fontweight="bold", va="top")
    fig.text(0.06, 0.86, subtitle, fontsize=14, va="top")
    fig.text(0.06, 0.06, callout, fontsize=15, va="bottom")

    fig.savefig(OUT / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


# 1. README Project Map
save_card(
    "01_project_map.png",
    "SystemC/TLM Architecture Performance Labs",
    "From LT architecture-level performance workflow to AT phase-level arbitration refinement",
    [
        "LT Performance Lab: workload → trace → metrics → sweep → comparison → demo.",
        "AT Arbitration Lab: phase trace → transaction reconstruction → arbitration policy sweep → comparison → demo.",
        "The project turns SystemC/TLM examples into reproducible architecture experiments.",
    ],
    "Boundary: experimental modeling lab, not cycle-accurate AXI / CHI / NoC."
)

# 2. LT comparison: stride=16 effect
save_bar_card(
    "02_lt_stride16_bank_conflict.png",
    "LT Evidence: Access Locality Changes Latency",
    "stride=16 increases bank conflict ratio and average delay",
    ["bank_conflict_ratio_pct", "avg_delay_ns"],
    [(46.875, 98.438), (164.688, 185.312)],
    "value",
    "Observation: stride=16 raises bank conflict ratio from 46.875% to 98.438%, and avg_delay_ns from 164.688 ns to 185.312 ns."
)

# 3. AT comparison: policy effect
columns = ["Policy", "101xxx avg accept", "102xxx avg accept", "Interpretation"]
rows = [
    ["fifo", "mixed", "mixed", "natural pending order"],
    ["priority_101", "1.000 ns", "6.000 ns", "101 favored"],
    ["priority_102", "6.000 ns", "1.000 ns", "102 favored"],
]
save_table_card(
    "03_at_policy_latency.png",
    "AT Evidence: Arbitration Policy Changes Accept Latency",
    "request_accept_latency_ns exposes arbitration behavior",
    columns,
    rows,
    "Observation: priority_101 makes 101xxx faster; priority_102 makes 102xxx faster. The effect is visible directly in AT phase timing."
)

# 4. demo_at_lab.py key conclusions
save_card(
    "04_at_demo_key_conclusions.png",
    "One-Command AT Demo",
    "demo_at_lab.py generates trace, analysis, sweep summary, and comparison",
    [
        "fifo complete_transactions = 4",
        "priority_101 accepts 101xxx faster: 101xxx avg = 1.000 ns, 102xxx avg = 6.000 ns",
        "priority_102 accepts 102xxx faster: 102xxx avg = 1.000 ns, 101xxx avg = 6.000 ns",
        "comparison.md generated for portfolio-ready evidence.",
    ],
    "Command: python3 examples/at/tools/demo_at_lab.py --binary ./build/examples/at/at"
)

print("Generated portfolio cards:")
for p in sorted(OUT.glob("*.png")):
    print(" ", p)
