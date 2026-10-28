#!/usr/bin/env python3
"""Plan private AOT SPU overlays from DMA captures plus actual branch misses.

Use SPU_DUMP_OVL_VERSIONS=1 and SPU_DUMP_OVL=<private-dir>,<LS-base> during a
bounded local probe. A DMA body is considered executable only when a later
unlifted branch in the same SPU image lands inside it and the logged LS words
match the captured bytes. All plans and generated code remain under generated/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CAPTURE = re.compile(r"\[spu-ovl-version\] img=(\d+) ea=0x([0-9A-F]+) lsa=0x([0-9A-F]+) size=(\d+) hash=([0-9A-F]+) file=(\S+)")
RESIDENT = re.compile(r"\[spu-ovl\] image=(\d+) prior=\d+ resident=\d+ LS=0x([0-9A-F]+) EA=0x([0-9A-F]+) span=0x([0-9A-F]+) hash=([0-9A-F]+)")
EXEC_MISS = re.compile(r"\[spu-ovl-exec\] image=(\d+) pc=0x([0-9A-F]+) lr=0x[0-9A-F]+ owner=(\d+) MISS")
MISS = re.compile(r"\[spu\] img=(\d+) branched into unlifted LS 0x([0-9A-F]+)")
WORDS = re.compile(r"LS\[0x([0-9A-F]+)\]:((?: [0-9A-F]{8})+)")


def private_path(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to((ROOT / "generated").resolve()):
        raise ValueError(f"overlay artifact must stay under generated/: {path}")
    return path


def discover(lines: list[str], captures: Path, owner_bodies_override: dict | None = None) -> list[dict]:
    resident: dict[int, dict] = {}
    known: dict[tuple[int, int, int], dict] = {}
    captured_bodies = {}
    owner_bodies = {}
    for path in captures.glob("ovl_*.bin"):
        raw = path.read_bytes()
        captured_bodies[(len(raw), fnv64(raw))] = (path, raw)
        digest = hashlib.sha256(raw).hexdigest()
        owner = 0x60000000 | (int(digest[:8], 16) & 0x1FFFFFFF)
        for stamp_path in (ROOT / "generated/overlays").glob("**/build-stamp.json"):
            stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
            if stamp.get("input_sha256") == digest and stamp.get("size") == len(raw):
                ea_match = re.match(r"ovl_([0-9A-Fa-f]{8})_", path.name)
                if ea_match:
                    owner_bodies[owner] = {"image": 0, "ea": int(ea_match[1], 16),
                                           "base": stamp["base"], "size": len(raw),
                                           "path": path, "raw": raw, "sha256": digest}
                break
    if owner_bodies_override:
        owner_bodies.update(owner_bodies_override)
    found: dict[str, dict] = {}
    pending = None
    for line in lines:
        if match := CAPTURE.search(line):
            image, ea, base, size, short_hash, path = match.groups()
            image, ea, base, size = int(image), int(ea, 16), int(base, 16), int(size)
            body = captures / Path(path).name
            if not body.is_file() or body.stat().st_size != size:
                continue
            raw = body.read_bytes()
            if not any(raw) or int(short_hash, 16) != fnv64(raw):
                continue
            resident[image] = {"image": image, "ea": ea, "base": base,
                               "size": size, "path": body, "raw": raw,
                               "sha256": hashlib.sha256(raw).hexdigest()}
            known[(image, base, fnv64(raw))] = resident[image]
            pending = None
        elif match := RESIDENT.search(line):
            image, base, ea, size, hash_hex = match.groups()
            image, base, ea, size = int(image), int(base, 16), int(ea, 16), int(size, 16)
            body = captured_bodies.get((size, int(hash_hex, 16)))
            if body:
                path, raw = body
                resident[image] = {"image": image, "ea": ea, "base": base,
                                   "size": size, "path": path, "raw": raw,
                                   "sha256": hashlib.sha256(raw).hexdigest()}
            else:
                resident[image] = known.get((image, base, int(hash_hex, 16)))
            pending = None
        elif match := EXEC_MISS.search(line):
            image, _entry, owner = int(match[1]), int(match[2], 16), int(match[3])
            if owner in owner_bodies:
                resident[image] = {**owner_bodies[owner], "image": image}
        elif match := MISS.search(line):
            image, entry = int(match[1]), int(match[2], 16)
            item = resident.get(image)
            pending = (item, entry) if item and item["base"] <= entry < item["base"] + item["size"] else None
        elif pending and (match := WORDS.search(line)):
            item, entry = pending
            if int(match[1], 16) != entry:
                continue
            actual = bytes.fromhex(match[2].replace(" ", ""))
            offset = entry - item["base"]
            pending = None
            if item["raw"][offset:offset + len(actual)] != actual:
                continue
            plan = found.setdefault(item["sha256"], {key: item[key] for key in
                ("image", "ea", "base", "size", "path", "sha256")})
            plan.setdefault("entries", set()).add(entry)
    return [{**p, "path": str(p["path"]), "entries": sorted(p["entries"])}
            for p in found.values()]


def fnv64(raw: bytes) -> int:
    value = 0xCBF29CE484222325
    for byte in raw:
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--captures", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "generated/overlays/discovered")
    ap.add_argument("--build", action="store_true", help="AOT lift only evidence-matched bodies")
    args = ap.parse_args()
    captures, out = private_path(args.captures), private_path(args.out)
    plans = discover(args.log.read_text(encoding="utf-8", errors="replace").splitlines(), captures)
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(plans, indent=2) + "\n", encoding="utf-8")
    for plan in plans:
        print(f"[spu-discover] image={plan['image']} sha256={plan['sha256']} "
              f"entries={','.join(hex(x) for x in plan['entries'])}")
        if args.build:
            existing = None
            for stamp_path in (ROOT / "generated/overlays").glob("**/build-stamp.json"):
                stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
                if stamp.get("input_sha256") == plan["sha256"]:
                    existing = (stamp_path.parent, stamp)
                    break
            output, stamp = existing if existing else (out / plan["sha256"][:16], None)
            if stamp:
                if stamp["base"] != plan["base"] or stamp["size"] != plan["size"]:
                    raise SystemExit("[spu-discover] existing lift has incompatible LS layout")
                entry = stamp["entry"]
                extra = sorted(({entry, *stamp.get("extra_entries", []), *plan["entries"]}) - {entry})
            else:
                entry = plan["entries"][0]
                extra = plan["entries"][1:]
            subprocess.run([sys.executable, str(ROOT / "tools/build_spu_overlay.py"),
                            "--input-dir", str(captures), "--sha256", plan["sha256"],
                            "--out", str(output), "--base", hex(plan["base"]),
                            "--entry", hex(entry), "--size", hex(plan["size"]),
                            "--extra-funcs", ",".join(hex(x) for x in extra)], check=True)
    print(f"[spu-discover] {len(plans)} evidenced variant(s); plan={out / 'plan.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
