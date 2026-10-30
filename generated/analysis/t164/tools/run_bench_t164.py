#!/usr/bin/env python3
"""T164: synthetic workloads, reference vs batched, per GPU. No validation layer, no game data.

Reports medians and min..max over RUNS. Records any game or peer launcher seen running, since
that would disturb the timings. Also measures RSX_VK_STATS overhead on the heavy workload.
"""
import json
import os
import re
import statistics as st
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HOST = ROOT / "build" / "t164-vulkan" / "ps3recomp_host.exe"
OUT = ROOT / "generated" / "analysis" / "t164" / "logs"
RUNS, FRAMES = 5, 30
DEVICES = {"0": "RTX 5060", "1": "Radeon iGPU"}
WORK = "abcd"
KEYS = ["draws_recorded", "submits", "fence_waits", "passes", "barriers", "desc_allocs", "desc_reused",
        "inflight_peak", "uploads", "wait_ms", "submit_ms", "record_ms", "gpu_ms", "latency_avg_us",
        "mem_peak_mb", "pending_peak_mb"]


def busy():
    p = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, errors="replace")
    return sorted({l.split(",")[0].strip('"') for l in p.stdout.splitlines()
                   if re.search(r"motorstorm|eboot|ps3recomp_game", l, re.I)})


def one(dev, work, batched, stats=True):
    env = dict(os.environ, PS3RECOMP_VK_DEVICE=dev, PS3RECOMP_VK_GUEST_PROGRAMS="1")
    env.pop("VK_INSTANCE_LAYERS", None)
    if stats:
        env["RSX_VK_STATS"] = "1"
    if batched:
        env["RSX_VK_BATCHED_SUBMIT"] = "1"
    p = subprocess.run([str(HOST), f"--frames={FRAMES}", f"--bench={work}"], env=env, cwd=OUT,
                       capture_output=True, text=True, errors="replace", timeout=300)
    t = p.stdout + p.stderr
    assert p.returncode == 0, t[-400:]
    m = re.search(r"--bench=\w: ([\d.]+) ms, ([\d.]+) ms/frame", t)
    out = {"ms_frame": float(m.group(2))}
    s = re.search(r"\[vk-stats\] (.*)", t)
    if s:
        d = dict(x.split("=") for x in s.group(1).split())
        out.update({k: float(d[k]) for k in KEYS})
    return out


def summ(rows, key):
    v = [r[key] for r in rows]
    return {"median": st.median(v), "min": min(v), "max": max(v)}


def main():
    res = {"seen_before": busy(), "runs": RUNS, "frames": FRAMES}
    for dev, name in DEVICES.items():
        for w in WORK:
            for mode, b in (("reference", False), ("batched", True)):
                rows = [one(dev, w, b) for _ in range(RUNS)]
                res[f"{name}|{w}|{mode}"] = {k: summ(rows, k) for k in rows[0]}
                print(name, w, mode, res[f"{name}|{w}|{mode}"]["ms_frame"], flush=True)
        for mode, b in (("reference", False), ("batched", True)):
            rows = [one(dev, "b", b, False) for _ in range(RUNS)]
            res[f"{name}|b|{mode}|nostats"] = {"ms_frame": summ(rows, "ms_frame")}
            print(name, "b nostats", mode, res[f"{name}|b|{mode}|nostats"], flush=True)
    res["seen_after"] = busy()
    (OUT / "bench.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


main()
