#!/usr/bin/env python3
"""Vulkan guest-sync check: ps3recomp_host --sync, reference vs batched, per GPU. No game data.

PASS needs rc 0, the label equal to the number of sync points, identical per-frame hashes
between the two submission paths, and the same draw count. Reports submits for both."""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HOST = ROOT / "build" / "vksync-vulkan" / "ps3recomp_host.exe"
SDK = ROOT / "build" / "vulkan-sdk"
OUT = ROOT / "generated" / "analysis" / "vksync" / "logs"


def run(dev, batched, scene):
    env = dict(os.environ, PS3RECOMP_VK_DEVICE=dev, PS3RECOMP_VK_GUEST_PROGRAMS="1", RSX_VK_STATS="1",
               RSX_VK_FRAME_HASH="1")
    env["PATH"] = str(SDK / "Bin") + os.pathsep + env["PATH"]
    env.pop("RSX_VK_BATCHED_SUBMIT", None)
    if batched:
        env["RSX_VK_BATCHED_SUBMIT"] = "1"
    p = subprocess.run([str(HOST), "--frames=4", scene], env=env, cwd=OUT, capture_output=True,
                       text=True, errors="replace", timeout=300)
    t = p.stdout + p.stderr
    (OUT / f"dev{dev}_{scene.lstrip('-')}_{'batched' if batched else 'ref'}.txt").write_text(t, encoding="utf-8")
    st = re.search(r"\[vk-stats\] (.*)", t)
    stats = dict(x.split("=") for x in st.group(1).split() if "=" in x) if st else {}
    return p.returncode, re.findall(r"\[vk-frame\] \d+ (\w+)", t), stats, "--sync: label" in t and "OK" in t


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bad = 0
    for dev in ("0", "1"):
        r = run(dev, False, "--sync")
        b = run(dev, True, "--sync")
        d = run(dev, True, "--draw")
        ok = (r[0] == b[0] == 0 and r[3] and b[3] and r[1] == b[1] and r[1]
              and r[2].get("draws_recorded") == b[2].get("draws_recorded"))
        bad += not ok
        print(f"dev{dev} {'OK' if ok else 'FAIL'} frames_identical={r[1] == b[1]} draws={r[2].get('draws_recorded')} "
              f"submits ref={r[2].get('submits')} batched={b[2].get('submits')} batched --draw (no sync)={d[2].get('submits')}")
    raise SystemExit(1 if bad else 0)


main()
