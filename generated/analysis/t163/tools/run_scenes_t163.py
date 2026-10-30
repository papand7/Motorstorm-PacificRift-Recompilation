#!/usr/bin/env python3
"""T163: run every ps3recomp_host scene on each GPU under the Khronos validation layer.

A scene counts as PASS only with rc 0, no "nothing to check" and no validation
message; the layer is proved loaded from the loader log. No game data is used.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HOST = ROOT / "build" / "t163-vulkan" / "ps3recomp_host.exe"
SDK = ROOT / "build" / "vulkan-sdk"
OUT = ROOT / "generated" / "analysis" / "t163" / "logs" / "scenes"
SCENES = ["", "--draw", "--depth", "--tex", "--tex-io", "--quads", "--shader", "--mip",
          "--mip-aniso", "--rtt", "--depthtex", "--mrt", "--mrt-a", "--cube",
          "--depthbounds", "--split-present", "--feedback"]
DEVICES = sys.argv[1:] or ["0", "1"]
VUID = re.compile(r"Validation (?:Error|Warning|Performance Warning): \[ ([^\]]+?) \]")


def run(dev, scene):
    env = dict(os.environ, PS3RECOMP_VK_DEVICE=dev, PS3RECOMP_VK_GUEST_PROGRAMS="1",
               VK_LAYER_PATH=str(SDK / "Bin"), VK_INSTANCE_LAYERS="VK_LAYER_KHRONOS_validation",
               VK_LOADER_DEBUG="layer", VK_LAYER_REPORT_FLAGS="error,warn")
    env["PATH"] = str(SDK / "Bin") + os.pathsep + env["PATH"]
    cmd = [str(HOST), "--frames=10"] + ([scene] if scene else [])
    try:
        p = subprocess.run(cmd, env=env, cwd=OUT, capture_output=True, text=True,
                           errors="replace", timeout=120)
        rc, text = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        rc, text = "timeout", (e.stdout or b"").decode(errors="replace")
    name = f"dev{dev}_{(scene or 'default').lstrip('-')}.txt"
    (OUT / name).write_text(text, encoding="utf-8")
    vuids = sorted(set(VUID.findall(text)))
    layer = "VK_LAYER_KHRONOS_validation" in text and "Insert instance layer" in text
    nothing = "nothing to check" in text
    gpu = re.search(r"using device \d+: ([^\n]*)", text)
    ok = rc == 0 and not nothing and not vuids and layer
    status = "PASS" if ok else "NOT-RUN" if nothing else "FAIL"
    return {"device": dev, "gpu": gpu.group(1).strip() if gpu else "?", "scene": scene or "(default)",
            "rc": rc, "status": status, "layer_loaded": layer, "vuids": vuids}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = [run(d, s) for d in DEVICES for s in SCENES]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for r in res:
        print(r["device"], r["gpu"][:24], r["scene"], r["rc"], r["status"],
              "layer" if r["layer_loaded"] else "NOLAYER", len(r["vuids"]), r["vuids"][:4])


main()
