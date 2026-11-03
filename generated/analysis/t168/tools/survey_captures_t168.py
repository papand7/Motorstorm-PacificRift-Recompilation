#!/usr/bin/env python3
"""T168: list existing game RSXI captures that carry FIFO offsets. Reads files only."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rsxi_load import manifest

ROOT = Path(__file__).resolve().parents[4]
rows = []
for base in (ROOT / "generated/analysis", ROOT / "generated/runs"):
    for m in base.rglob("rsxi/manifest.json"):
        cap = m.parent
        try:
            d = manifest(cap)
        except Exception:
            continue
        if d.get("title") != "ps3recomp":     # synthetic harnesses set their own title
            continue
        fr = d.get("frames", [])
        if not fr:
            continue
        nums = [f["frame"] for f in fr]
        gaps = [b - a for a, b in zip(nums, nums[1:])]
        rows.append({"cap": str(cap.relative_to(ROOT)).replace("\\", "/"), "build": d.get("build"),
                     "unavailable": d.get("unavailable"), "n": len(fr), "frames": nums[:12],
                     "records": [f["records"] for f in fr][:12], "dropped": sum(f.get("dropped_events", 0) for f in fr),
                     "consec": sum(g == 1 for g in gaps), "present": [f.get("presented") for f in fr][:12]})
rows.sort(key=lambda r: (-r["consec"], -max(r["records"])))
for r in rows:
    print(json.dumps(r))
print(len(rows), "captures")
