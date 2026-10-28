#!/usr/bin/env python3
"""Lift a locally captured SPU DMA code body; keep every output private.

The input is produced by SPU_DUMP_OVL with SPU_DUMP_OVL_LATEST=1. No game
bytes, decoded instructions, or generated sources belong in public source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "ps3recomp" / "tools"


def fnv64(raw: bytes) -> int:
    value = 0xCBF29CE484222325
    for byte in raw:
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--sha256", default="", help="Select one captured code version")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--base", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--entry", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--size", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--extra-funcs", default="",
                    help="Comma-separated observed indirect LS targets")
    args = ap.parse_args()
    offset = args.entry - args.base
    if args.base < 0 or args.entry & 3 or offset < 0 or offset + 16 > args.size:
        ap.error("entry must be a 16-byte signature inside the code body")
    candidates = []
    for path in sorted(args.input_dir.glob("ovl_*.bin")):
        raw = path.read_bytes()
        if args.sha256 and hashlib.sha256(raw).hexdigest().lower() != args.sha256.lower():
            continue
        if len(raw) != args.size or not any(raw[offset:offset + 16]):
            continue
        candidates.append((path, raw))
    if not candidates:
        if (args.out / "spu_recomp.c").exists():
            raise SystemExit("[spu-overlay] capture missing but stale AOT output exists")
        print("[spu-overlay] no populated local capture; skipping")
        return 0
    hashes = {hashlib.sha256(raw).digest() for _, raw in candidates}
    if len(hashes) != 1:
        raise SystemExit("[spu-overlay] multiple distinct populated captures; select one explicitly")
    path, raw = candidates[0]
    digest = hashlib.sha256(raw).digest()
    image_id = 0x60000000 | (int.from_bytes(digest[:4], "big") & 0x1FFFFFFF)
    prefix = f"local_overlay_{digest.hex()[:12]}_"
    out = args.out
    extra_entries = {int(x.strip(), 0) for x in args.extra_funcs.split(",") if x.strip()}
    previous_stamp = out / "build-stamp.json"
    if previous_stamp.exists():
        previous = json.loads(previous_stamp.read_text(encoding="utf-8"))
        if (previous.get("input_sha256") == digest.hex() and
                previous.get("base") == args.base and
                previous.get("entry") == args.entry and
                previous.get("size") == args.size):
            extra_entries.update(previous.get("extra_entries", []))
    extra_entries = sorted(extra_entries)
    stamp = {
        "input_sha256": digest.hex(), "base": args.base, "entry": args.entry,
        "size": args.size, "extra_entries": extra_entries,
        "tools_sha256": {name: hashlib.sha256((TOOLS / name).read_bytes()).hexdigest()
                         for name in ("wrap_spu_elf.py", "spu_lifter.py")},
        "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    if (out / "build-stamp.json").exists() and all(
        (out / name).exists() for name in ("spu_recomp.c", "spu_recomp.h", "overlay_register.c")
    ) and json.loads((out / "build-stamp.json").read_text(encoding="utf-8")) == stamp:
        print(f"[spu-overlay] unchanged {digest.hex()[:12]}: {out}")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    elf = out / "overlay.elf"
    subprocess.run([sys.executable, str(TOOLS / "wrap_spu_elf.py"), str(path),
                    "--base", hex(args.base), "--entry", hex(args.entry),
                    "--out", str(elf)], check=True)
    report = out / "lift-report.json"
    extra = ",".join([hex(args.entry)] + [hex(x) for x in extra_entries])
    subprocess.run([sys.executable, str(TOOLS / "spu_lifter.py"),
                    "--auto-functions", str(elf), "--extra-funcs", extra,
                    "--output", str(out), "--report", str(report),
                    "--symbol-prefix", prefix], check=True)
    findings = json.loads(report.read_text(encoding="utf-8"))
    if findings.get("unsupported"):
        raise SystemExit(f"[spu-overlay] unsupported instructions: {findings['unsupported']}")
    for name in ("spu_recomp.c", "spu_recomp.h"):
        source = out / name
        source.write_text(source.read_text(encoding="utf-8").replace(
            '"../../runtime/spu/', '"'), encoding="utf-8")
    sig = ", ".join(f"0x{b:02X}" for b in raw[offset:offset + 16])
    registration = f'''/* Locally generated from user-supplied SPU code. Keep private. */
#include <stdint.h>
extern void spu_begin_image(int);
extern void {prefix}spu_recomp_register(void);
extern void spu_overlay_register_region_fingerprint(const uint8_t[16], uint32_t, uint32_t, uint64_t, int);
__attribute__((constructor)) static void register_local_overlay(void)
{{
    static const uint8_t sig[16] = {{{sig}}};
    spu_begin_image({image_id});
    {prefix}spu_recomp_register();
    spu_overlay_register_region_fingerprint(sig, 0x{offset:X}u, 0x{args.size:X}u,
                                            UINT64_C(0x{fnv64(raw):016X}), {image_id});
    spu_begin_image(0);
}}
'''
    (out / "overlay_register.c").write_text(registration, encoding="utf-8")
    (out / "build-stamp.json").write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"[spu-overlay] {path.name} sha256={digest.hex()} id={image_id} "
          f"functions={len(findings.get('functions', []))} output={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
