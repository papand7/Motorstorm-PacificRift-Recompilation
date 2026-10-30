#!/usr/bin/env python3
"""T164: the four workloads for the benchmark's 30 frames, batched, under validation, per GPU.

The correctness matrix runs 4 frames of each path; this one covers ring wrap and retirement
over a run as long as the timed one. No game data is used.
"""
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HOST = ROOT / "build" / "t164-vulkan" / "ps3recomp_host.exe"
SDK = ROOT / "build" / "vulkan-sdk"
OUT = ROOT / "generated" / "analysis" / "t164" / "logs"
MSG = re.compile(r"Validation (?:Error|Warning|Performance Warning): \[ ([^\]]+?) \]")
res = []
for dev, name in (("0", "RTX 5060"), ("1", "Radeon iGPU")):
    for w in "abcd":
        env = dict(os.environ, PS3RECOMP_VK_DEVICE=dev, PS3RECOMP_VK_GUEST_PROGRAMS="1", RSX_VK_STATS="1",
                   RSX_VK_BATCHED_SUBMIT="1", VK_LAYER_PATH=str(SDK / "Bin"),
                   VK_INSTANCE_LAYERS="VK_LAYER_KHRONOS_validation", VK_LOADER_DEBUG="layer",
                   VK_LAYER_REPORT_FLAGS="error,warn")
        env["PATH"] = str(SDK / "Bin") + os.pathsep + env["PATH"]
        p = subprocess.run([str(HOST), "--frames=30", f"--bench={w}"], env=env, cwd=OUT, capture_output=True,
                           text=True, errors="replace", timeout=550)
        t = p.stdout + p.stderr
        dr = re.search(r"draws_recorded=(\d+)", t)
        row = {"gpu": name, "work": w, "rc": p.returncode, "layer": "Insert instance layer" in t,
               "msgs": sorted(set(MSG.findall(t))), "draws": dr and dr.group(1)}
        res.append(row)
        print(row, flush=True)
(OUT / "longval.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
