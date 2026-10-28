"""Extract the observed MotorStorm Wws_Job SPURS policy module from its PPU ELF.

The guest passes EA 0x00FFCC80, size 0x2D00 to cellSpursAddWorkload. The
runtime loads those exact bytes at SPU LS 0xA00 and enters at that address.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ps3recomp" / "tools"))
from wrap_spu_elf import wrap

EA = 0x00FFCC80
SIZE = 0x2D00
BASE = 0xA00
EXPECTED_FP = 0x093FC7EE6C9F7E84


def fnv1a(data):
    value = 1469598103934665603
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return value


def elf_offset(data, guest_ea, size):
    if data[:6] != b"\x7fELF\x02\x02":
        raise ValueError("Expected big-endian ELF64")
    phoff = struct.unpack_from(">Q", data, 32)[0]
    phentsize, phnum = struct.unpack_from(">HH", data, 54)
    for index in range(phnum):
        at = phoff + index * phentsize
        kind, flags, offset, vaddr, _, filesz, _, _ = struct.unpack_from(">IIQQQQQQ", data, at)
        if kind == 1 and vaddr <= guest_ea and guest_ea + size <= vaddr + filesz:
            return offset + guest_ea - vaddr
    raise ValueError(f"No file-backed PT_LOAD segment contains {guest_ea:#x}+{size:#x}")


def main():
    source = ROOT / "generated" / "decrypted" / "EBOOT.elf"
    dest = ROOT / "generated" / "spu_raw"
    data = source.read_bytes()
    offset = elf_offset(data, EA, SIZE)
    raw = data[offset:offset + SIZE]
    fingerprint = fnv1a(raw)
    if fingerprint != EXPECTED_FP:
        raise ValueError(f"Wws_Job fingerprint mismatch: {fingerprint:016X}")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "wws_job_pm.bin").write_bytes(raw)
    (dest / "wws_job_pm.elf").write_bytes(wrap(raw, base=BASE, entry=BASE))
    result = {"source": str(source), "guest_ea": hex(EA), "file_offset": hex(offset),
              "size": SIZE, "spu_base": hex(BASE), "entry": hex(BASE),
              "fingerprint": f"{fingerprint:016X}", "sha256": hashlib.sha256(raw).hexdigest()}
    (dest / "wws_job_pm.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
