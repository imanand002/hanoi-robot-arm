"""
benchmark.py  --  Race recursive vs iterative and draw graphs.

Run from the project folder:
    python scripts/benchmark.py
It creates:
    docs/performance.png    (two graphs)
    docs/benchmark.csv      (the numbers)
    docs/sample_output.json (moves for 3 disks)
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt

from backend.algorithms import best_time_ms, min_moves, run_algorithm

MAX_DISKS = 18
REPEATS = 3
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

rows = []
for n in range(1, MAX_DISKS + 1):
    rec = best_time_ms("recursive", n, REPEATS)
    ite = best_time_ms("iterative", n, REPEATS)
    rows.append({"disks": n, "moves": min_moves(n), "recursive_ms": rec, "iterative_ms": ite})
    print(f"{n:>2} disks | {min_moves(n):>7} moves | recursive {rec:>10.3f} ms | iterative {ite:>10.3f} ms")

with open(DOCS / "benchmark.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

# ---- the graphs ----
xs = [r["disks"] for r in rows]
rec = [r["recursive_ms"] for r in rows]
ite = [r["iterative_ms"] for r in rows]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))

ax1.plot(xs, rec, marker="o", color="#4f46e5", label="Recursive")
ax1.plot(xs, ite, marker="s", color="#ea580c", label="Iterative")
ax1.set_title("Time to solve (linear scale)")
ax1.set_xlabel("Number of disks")
ax1.set_ylabel("Time (ms)")
ax1.grid(alpha=0.3)
ax1.legend()

ax2.plot(xs, rec, marker="o", color="#4f46e5", label="Recursive")
ax2.plot(xs, ite, marker="s", color="#ea580c", label="Iterative")
ax2.plot(xs, [r["moves"] / 1000 for r in rows], linestyle="--", color="#6b7280", label="Moves (2ⁿ−1, thousands)")
ax2.set_yscale("log")
ax2.set_title("Same data (log scale): a straight line = doubling each disk")
ax2.set_xlabel("Number of disks")
ax2.set_ylabel("Time (ms) / moves (thousands)")
ax2.grid(alpha=0.3, which="both")
ax2.legend()

for ax in (ax1, ax2):
    ax.set_xticks(xs)

fig.suptitle(f"Tower of Hanoi: recursive vs iterative (best of {REPEATS} runs)")
fig.tight_layout()
fig.savefig(DOCS / "performance.png", dpi=130)
print("saved", DOCS / "performance.png")

# ---- sample output (3 disks) ----
sample = run_algorithm("recursive", 3)
with open(DOCS / "sample_output.json", "w") as f:
    json.dump({k: sample[k] for k in sample}, f, indent=2)
print("saved", DOCS / "sample_output.json")
