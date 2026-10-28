#!/usr/bin/env python3
"""Inventory a user-installed RPCS3 SPURS module without exporting its code.

Reads local firmware and RPCS3's optional PPU-debug dump. Writes only hashes,
ELF metadata, and export addresses to an ignored output directory. The dump and
any disassembly stay local and must not be staged for a public release.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct


EXPORT_RE = re.compile(
    r"cellSpurs export: \(0x(?P<nid>[0-9a-fA-F]{8})\) at "
    r"0x(?P<descriptor>[0-9a-fA-F]+) \[at:0x(?P<entry>[0-9a-fA-F]+),"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def elf_segments(path: Path) -> list[dict[str, int]]:
    with path.open("rb") as stream:
        header = stream.read(64)
        if header[:6] != b"\x7fELF\x02\x02":
            raise ValueError(f"{path} is not a big-endian ELF64 image")
        phoff = struct.unpack_from(">Q", header, 32)[0]
        entsize, count = struct.unpack_from(">HH", header, 54)
        segments = []
        for index in range(count):
            stream.seek(phoff + index * entsize)
            ph = stream.read(56)
            kind, flags = struct.unpack_from(">II", ph)
            offset, vaddr = struct.unpack_from(">QQ", ph, 8)
            filesz = struct.unpack_from(">Q", ph, 32)[0]
            segments.append(
                {"type": kind, "flags": flags, "offset": offset,
                 "vaddr": vaddr, "filesz": filesz}
            )
        return segments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rpcs3", type=Path, help="local RPCS3 data directory")
    parser.add_argument("--nid", type=lambda value: int(value, 0), default=0x8A85674D)
    parser.add_argument(
        "--output", type=Path,
        default=Path("generated/firmware_analysis/libsre-inventory.json"),
    )
    args = parser.parse_args()
    module = args.rpcs3 / "dev_flash/sys/external/libsre.sprx"
    log = args.rpcs3 / "log/RPCS3.log"
    if not module.is_file() or not log.is_file():
        raise SystemExit("libsre.sprx or RPCS3.log is missing")

    lines = log.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    exports = [(index, match) for index, line in enumerate(lines)
               if (match := EXPORT_RE.search(line)) and int(match["nid"], 16) == args.nid]
    if not exports:
        raise SystemExit(f"NID 0x{args.nid:08X} absent from local RPCS3 export log")
    export_index, match = exports[-1]
    entry = int(match["entry"], 16)
    # The export list follows the module's two PT_LOAD mappings. Validate both
    # against the dumped ELF's OPD descriptor below before trusting them.
    mappings = [int(found.group(1), 16) for line in lines[:export_index]
                if (found := re.search(r"ppu_loader: \*\*\*\* Loaded to 0x([0-9a-fA-F]+)", line))]
    if len(mappings) < 2:
        raise SystemExit("Cannot locate both firmware PT_LOAD mappings")
    code_base = mappings[-2]
    data_base = mappings[-1]
    dumps = list((args.rpcs3 / "ppu_progs").glob("*-libsre.sprx/prog.prx"))
    if len(dumps) != 1:
        raise SystemExit(f"Expected one local decrypted libsre dump; found {len(dumps)}")
    dump = dumps[0]
    segments = elf_segments(dump)
    cache_dirs = list((args.rpcs3 / "cache").glob("ppu-*-libsre.sprx"))
    cache_objects = []
    for cache_dir in cache_dirs:
        for artifact in sorted(cache_dir.glob("*.obj.gz")):
            with gzip.open(artifact, "rb") as stream:
                header = stream.read(20)
            cache_objects.append({
                "path": str(artifact.resolve()), "size": artifact.stat().st_size,
                "sha256": sha256(artifact),
                "uncompressed_coff_machine": f"0x{struct.unpack_from('<H', header)[0]:04X}",
            })
    relative = entry - code_base
    location = next((seg["offset"] + relative - seg["vaddr"] for seg in segments
                     if seg["type"] == 1 and seg["vaddr"] <= relative
                     < seg["vaddr"] + seg["filesz"]), None)
    if location is None:
        raise SystemExit("Export entry is outside the dumped ELF's file-backed segments")
    descriptor = int(match["descriptor"], 16)
    data_segment = next((seg for seg in segments if seg["type"] == 1 and
                         seg["vaddr"] != 0), None)
    if data_segment is None:
        raise SystemExit("Decrypted ELF has no data segment for the export descriptor")
    descriptor_vaddr = data_segment["vaddr"] + descriptor - data_base
    descriptor_offset = data_segment["offset"] + descriptor_vaddr - data_segment["vaddr"]
    with dump.open("rb") as stream:
        stream.seek(descriptor_offset)
        descriptor_entry = struct.unpack(">I", stream.read(4))[0]
    if descriptor_entry != relative:
        raise SystemExit("Export descriptor disagrees with the inferred code load base")
    inventory = {
        "nid": f"0x{args.nid:08X}",
        "module_path": str(module.resolve()),
        "module_sha256": sha256(module),
        "module_size": module.stat().st_size,
        "module_magic": module.read_bytes()[:4].hex(),
        "dump_path": str(dump.resolve()),
        "dump_sha256": sha256(dump),
        "dump_size": dump.stat().st_size,
        "export_descriptor_guest": f"0x{int(match['descriptor'], 16):08X}",
        "export_entry_guest": f"0x{entry:08X}",
        "code_load_base": f"0x{code_base:08X}",
        "entry_elf_vaddr": f"0x{relative:X}",
        "entry_file_offset": f"0x{location:X}",
        "elf_segments": segments,
        "rpcs3_ppu_cache_objects": cache_objects,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"Local firmware inventory written to {args.output}")
    print(f"NID {inventory['nid']} -> entry {inventory['export_entry_guest']}; "
          f"dump SHA-256 {inventory['dump_sha256']}")


if __name__ == "__main__":
    main()
