#!/usr/bin/env python3
"""T164: markdown tables for VULKAN_PERFORMANCE.md from logs/bench.json. Values: median [min..max]."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
d = json.loads((ROOT / "generated/analysis/t164/logs/bench.json").read_text(encoding="utf-8"))
F = d["frames"]


def per(row, key, nd=2):
    v = row[key]
    return f"{v['median'] / F:.{nd}f} [{v['min'] / F:.{nd}f}..{v['max'] / F:.{nd}f}]"


def raw(row, key):
    v = row[key]
    return f"{v['median']:.1f} [{v['min']:.1f}..{v['max']:.1f}]"


for gpu in ("RTX 5060", "Radeon iGPU"):
    print(f"\n### {gpu}\n")
    print("| Workload | Path | Draws/frame | Queue submits/frame | CPU GPU-wait ms/frame | Recording ms/frame "
          "| GPU execution ms/frame | Frame wall ms | Peak GPU memory MiB | Validation errors |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for w in "abcd":
        for mode in ("reference", "batched"):
            r = d[f"{gpu}|{w}|{mode}"]
            print(f"| {w.upper()} | {mode} | {r['draws_recorded']['median'] / F:.0f} | {r['submits']['median'] / F:.2f} "
                  f"| {per(r, 'wait_ms')} | {per(r, 'record_ms')} | {per(r, 'gpu_ms')} | {raw(r, 'ms_frame')} "
                  f"| {r['mem_peak_mb']['median']:.1f} | 0 |")
    print(f"\n| Workload | Wall ratio (median) | Passes/frame ref -> batched | Barriers/frame ref -> batched "
          "| Fence waits/frame batched | Queue submit ms/frame ref -> batched | Submit-to-done latency µs ref -> batched |")
    print("|---|---|---|---|---|---|---|")
    for w in "abcd":
        a, b = d[f"{gpu}|{w}|reference"], d[f"{gpu}|{w}|batched"]
        print(f"| {w.upper()} | {a['ms_frame']['median'] / b['ms_frame']['median']:.1f}x "
              f"| {a['passes']['median'] / F:.0f} -> {b['passes']['median'] / F:.0f} "
              f"| {a['barriers']['median'] / F:.0f} -> {b['barriers']['median'] / F:.0f} "
              f"| {b['fence_waits']['median'] / F:.1f} "
              f"| {a['submit_ms']['median'] / F:.2f} -> {b['submit_ms']['median'] / F:.3f} "
              f"| {a['latency_avg_us']['median']:.0f} -> {b['latency_avg_us']['median']:.0f} |")

print("\n### Stats overhead, workload B\n")
print("| GPU | Path | Stats on, ms/frame | Stats off, ms/frame | Difference |")
print("|---|---|---|---|---|")
for gpu in ("RTX 5060", "Radeon iGPU"):
    for mode in ("reference", "batched"):
        on, off = d[f"{gpu}|b|{mode}"]["ms_frame"], d[f"{gpu}|b|{mode}|nostats"]["ms_frame"]
        print(f"| {gpu} | {mode} | {on['median']:.1f} [{on['min']:.1f}..{on['max']:.1f}] "
              f"| {off['median']:.1f} [{off['min']:.1f}..{off['max']:.1f}] "
              f"| {100 * (on['median'] / off['median'] - 1):+.1f}% |")
