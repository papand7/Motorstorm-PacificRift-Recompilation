#!/usr/bin/env python3
"""T164: D3D12 side of the synthetic comparison. No game data; never launches a game.

Preflight only until the host can select D3D12: it exits 2 and records why, and writes no timings.
Once `RSX_BACKEND=d3d12` is honoured by ps3recomp_host, this runs the same workloads, repeats and
frame count as run_bench_t164.py and writes logs/d3d12_bench.json. Frame wall time is the only
number the host prints for every backend; the Vulkan-only counters have no D3D12 equivalent yet.
"""
import json
import os
import re
import statistics as st
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "ps3recomp-t164-vulkan"
HOST = ROOT / "build" / "t164-vulkan" / "ps3recomp_host.exe"
OUT = ROOT / "generated" / "analysis" / "t164" / "logs"
RUNS, FRAMES = 5, 30


def preflight():
    host_src = (SRC / "runtime" / "host" / "host_posix.c").read_text(encoding="utf-8", errors="replace")
    sysdir = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32"
    checks = {
        "d3d12.dll": (sysdir / "d3d12.dll").exists(),
        "D3DCompiler_47.dll": (sysdir / "D3DCompiler_47.dll").exists(),
        "host_binary": HOST.exists(),
        "backend_object": any(HOST.parent.rglob("rsx_d3d12_backend.c.obj")),
        "host_selects_d3d12": bool(re.search(r"rsx_d3d12_backend_init|rsx_live_draw_init", host_src)),
    }
    return checks


def main():
    checks = preflight()
    print(json.dumps(checks, indent=1))
    if not all(checks.values()):
        print("NOT RUN: missing " + ", ".join(k for k, v in checks.items() if not v))
        return 2
    res = {}
    for w in "abcd":
        vals = []
        for _ in range(RUNS):
            env = dict(os.environ, RSX_BACKEND="d3d12", PS3RECOMP_VK_GUEST_PROGRAMS="1")
            p = subprocess.run([str(HOST), f"--frames={FRAMES}", f"--bench={w}"], env=env, cwd=OUT,
                               capture_output=True, text=True, errors="replace", timeout=300)
            m = re.search(r"--bench=\w: [\d.]+ ms, ([\d.]+) ms/frame", p.stdout + p.stderr)
            if p.returncode or not m:
                print(f"workload {w}: rc={p.returncode}, no timing; stopping")
                return 1
            vals.append(float(m.group(1)))
        res[w] = {"median": st.median(vals), "min": min(vals), "max": max(vals)}
    (OUT / "d3d12_bench.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


sys.exit(main())
