#!/usr/bin/env python3
"""Vulkan vs D3D12 on the race-shaped host scene (--bench=r) and --bench=a. No game data.

Arms: Vulkan reference, Vulkan batched (RSX_VK_BATCHED_SUBMIT=1), D3D12 (RSX_BACKEND=d3d12, vsync on and RSX_PRESENT_INTERVAL=0, with
the game runner's RSX_* settings). RTX device. Host ms/frame per run; median and range of RUNS.
For D3D12 also the backend's own [rsx-frame-perf] wall_ms and wait_ms (median over frames 10+),
because the host's wall time includes pacing outside the D3D12 backend."""
import os
import re
import statistics as st
import subprocess
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HOST = ROOT / "build" / "vkgame-host" / "ps3recomp_host.exe"
OUT = ROOT / "generated" / "analysis" / "vksync" / "logs"
RUNS, FRAMES = 5, 60
GAME_RSX = dict(RSX_BIND_DEDUP="1", RSX_FP_SCAN_MEMO="1", RSX_FP_SPAN="1", RSX_SRV_REUSE="1", RSX_TEX_CACHE="1",
                RSX_TEX_SLOTS="1024", RSX_TEX_BUDGET_MB="1024", RSX_VP_COMPACT="1", RSX_RT_READBACK="1",
                PS3_TEX_SNAPSHOT="1", PS3_TEX_SNAPSHOT_EPOCH="1", PS3_TEX_SNAPSHOT_WWATCH="1", RSX_TEX_WWATCH="1")
ARMS = {"vk_ref": {}, "vk_batched": {"RSX_VK_BATCHED_SUBMIT": "1"},
        "d3d12": dict(GAME_RSX, RSX_BACKEND="d3d12", RSX_FRAME_PERF="1000"),
        "d3d12_novsync": dict(GAME_RSX, RSX_BACKEND="d3d12", RSX_FRAME_PERF="1000", RSX_PRESENT_INTERVAL="0")}


def one(arm, bench):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RSX", "PS3_", "BENCH_"))}
    env.update(PS3RECOMP_VK_DEVICE="0", PS3RECOMP_VK_GUEST_PROGRAMS="1", **ARMS[arm])
    p = subprocess.run([str(HOST), f"--frames={FRAMES}", f"--bench={bench}"], env=env, cwd=OUT,
                       capture_output=True, text=True, errors="replace", timeout=900)
    t = p.stdout + p.stderr
    assert p.returncode == 0, t[-400:]
    ms = float(re.search(r"--bench=\w: [\d.]+ ms, ([\d.]+) ms/frame", t).group(1))
    perf = [(int(g), float(w), float(x)) for g, w, x in
            re.findall(r"gframe=(\d+) .*?wall_ms=([\d.]+) .*?wait_ms=([\d.]+)", t)]
    perf = [p for p in perf if p[0] >= 10]
    be = (st.median(p[1] for p in perf), st.median(p[2] for p in perf)) if perf else None
    return ms, be


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for bench in ("r", "a"):
        for arm in ARMS:
            rows = [one(arm, bench) for _ in range(RUNS)]
            v = [r[0] for r in rows]
            rec = {"median": st.median(v), "min": min(v), "max": max(v)}
            if rows[0][1]:
                rec["backend_wall_ms"] = st.median(r[1][0] for r in rows)
                rec["backend_wait_ms"] = st.median(r[1][1] for r in rows)
            res[f"{bench}/{arm}"] = rec
            print(bench, arm, json.dumps(rec), flush=True)
    (OUT / "race_bench.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


main()
