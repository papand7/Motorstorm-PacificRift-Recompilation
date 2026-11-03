#!/usr/bin/env python3
"""T164: every ps3recomp_host scene, reference vs batched, on each GPU, under validation.

PASS needs rc 0, no "nothing to check", the layer proved loaded and no validation
message. Frames are compared by the backend's per-frame FNV-1a (RSX_VK_FRAME_HASH=1)
between the two submission paths. No game data is used.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HOST = ROOT / "build" / "vksync-vulkan" / "ps3recomp_host.exe"
SDK = ROOT / "build" / "vulkan-sdk"
OUT = ROOT / "generated" / "analysis" / "vksync" / "logs" / "correctness"
# (name, args, extra env, expect rc)
SCENES = [(s or "default", [s] if s else [], {}, 0) for s in
          ["", "--draw", "--depth", "--tex", "--tex-io", "--quads", "--shader", "--mip", "--rtt",
           "--depthtex", "--mrt", "--mrt-a", "--cube", "--depthbounds", "--split-present",
           "--feedback", "--stencil", "--mip-aniso-guest", "--sync"]]
SCENES += [("--mip-aniso", ["--mip-aniso"], {"PS3_ANISO": "16"}, 0),
           ("--mip-aniso-off", ["--mip-aniso"], {}, 3),      # negative control: must mismatch
           ("bench-a", ["--bench=a"], {}, 0), ("bench-b", ["--bench=b"], {}, 0),
           ("bench-c", ["--bench=c"], {}, 0), ("bench-d", ["--bench=d"], {}, 0)]
DEVICES = {"0": "RTX", "1": "iGPU"}
MSG = re.compile(r"Validation (?:Error|Warning|Performance Warning): \[ ([^\]]+?) \]")


def run(dev, name, args, extra, want_rc, batched, draws=None):
    env = dict(os.environ, PS3RECOMP_VK_DEVICE=dev, PS3RECOMP_VK_GUEST_PROGRAMS="1", RSX_VK_STATS="1",
               RSX_VK_FRAME_HASH="1", VK_LAYER_PATH=str(SDK / "Bin"),
               VK_INSTANCE_LAYERS="VK_LAYER_KHRONOS_validation", VK_LOADER_DEBUG="layer",
               VK_LAYER_REPORT_FLAGS="error,warn", **extra)
    env["PATH"] = str(SDK / "Bin") + os.pathsep + env["PATH"]
    if batched:
        env["RSX_VK_BATCHED_SUBMIT"] = "1"
    if draws:
        env["RSX_VK_BATCH_DRAWS"] = str(draws)
    try:
        p = subprocess.run([str(HOST), "--frames=4"] + args, env=env, cwd=OUT, capture_output=True,
                           text=True, errors="replace", timeout=400)
        rc, text = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        rc, text = "timeout", (e.stdout or b"").decode(errors="replace")
    tag = f"dev{dev}_{name.lstrip('-')}_{'batched' if batched else 'ref'}{draws or ''}.txt"
    (OUT / tag).write_text(text, encoding="utf-8")
    msgs = sorted(set(MSG.findall(text)))
    layer = "Insert instance layer" in text and "VK_LAYER_KHRONOS_validation" in text
    st = re.search(r"\[vk-stats\] (.*)", text)
    stats = dict(x.split("=") for x in st.group(1).split()) if st else {}
    return {"rc": rc, "want": want_rc, "layer": layer, "msgs": msgs,
            "nothing": "nothing to check" in text, "frames": re.findall(r"\[vk-frame\] \d+ (\w+)", text),
            "stats": stats, "stencil_bad": re.findall(r"--stencil\s+\d+ (.*?)\s+0x.*MISMATCH", text),
            "file": tag}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out = []
    for dev, label in DEVICES.items():
        for name, args, extra, want in SCENES:
            r = run(dev, name, args, extra, want, False)
            b = run(dev, name, args, extra, want, True)
            # the smallest batches force a flush between draws and exercise the ring
            s = run(dev, name, args, extra, want, True, 3)
            same = r["frames"] == b["frames"] == s["frames"]
            ok = all(x["rc"] == want and x["layer"] and not x["msgs"] and not x["nothing"] for x in (r, b, s))
            per = {"bench-a": 2000, "bench-b": 6900, "bench-c": 2000, "bench-d": 1200}.get(name)
            if per and not all(x["stats"].get("draws_recorded") == str(per * 4) for x in (r, b, s)):
                ok = False
            dr = (r["stats"].get("draws_recorded"), b["stats"].get("draws_recorded"), s["stats"].get("draws_recorded"))
            rec = {"gpu": label, "scene": name, "ok": ok, "frames_identical": same, "nframes": len(r["frames"]),
                   "ref": r, "batched": b, "small": s, "draws": dr}
            out.append(rec)
            print(label, name, "OK" if ok else "FAIL", "same" if same else "DIFF", len(r["frames"]), dr,
                  "submits", r["stats"].get("submits"), b["stats"].get("submits"), s["stats"].get("submits"),
                  (r["rc"], b["rc"], s["rc"]), (r["msgs"] + b["msgs"] + s["msgs"])[:3],
                  (r["stencil_bad"] + b["stencil_bad"])[:4], flush=True)
    (OUT / "results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


main()
