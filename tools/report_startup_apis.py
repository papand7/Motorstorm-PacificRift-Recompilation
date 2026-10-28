"""Summarize PS3_HLE_TRACE calls from a local, bounded startup probe.

The input logs and generated import tables stay in private ignored directories.
This tool prints only API names, libraries and counts.
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path


TRACE = re.compile(r"\[HLETRACE\] nid=0x([0-9A-Fa-f]{8})")
REG = re.compile(r'ps3_hle_register\(0x([0-9A-Fa-f]+)u, "([^"]+)"')


def category(library: str, name: str) -> str:
    n = name.lower()
    if n.startswith("cellaudioout"):
        return "optional:functional-audio-query"
    if any(x in n for x in ("audio", "adec", "at3", "atrac", "voice", "mic")):
        return "optional:audio-review"
    if any(x in n for x in ("trophy",)):
        return "optional:trophy"
    if any(x in n for x in ("pad", "gem")):
        return "optional:input"
    if any(x in n for x in ("savedata",)):
        return "optional:save-data"
    if library.lower() in ("cellnetctl", "cellnet", "libnet", "scenp") or \
            n.startswith(("cellnet", "sys_net", "scenp")):
        return "optional:network"
    if any(x in n for x in ("thread", "mutex", "cond", "spinlock", "semaphore",
                              "event", "timer", "time_get", "memory", "mmapper")):
        return "essential:execution"
    if n.startswith(("cellspurs", "_cellspurs", "cellsync", "cellgcm", "cellfs",
                     "cellgame", "cellvideoout", "cellsysmodule", "cellsyscache")):
        return "essential:startup"
    if n.startswith("cellsysutil") or n.startswith("sys_") or n.startswith("_sys_"):
        return "essential:execution"
    return "review"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("log", type=Path)
    p.add_argument("imports", type=Path)
    p.add_argument("registrations", type=Path)
    args = p.parse_args()
    counts = collections.Counter(x.upper() for x in TRACE.findall(
        args.log.read_text(encoding="utf-8", errors="replace")))
    if not counts:
        raise SystemExit("No HLETRACE calls found; set PS3_HLE_TRACE for a bounded probe")
    imports = {int(item["nid"], 16): item["library"] for item in
               json.loads(args.imports.read_text(encoding="utf-8"))}
    names = {nid.upper().zfill(8): name for nid, name in REG.findall(
        args.registrations.read_text(encoding="utf-8", errors="replace"))}
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ps3recomp" / "tools"))
    from nid_database import NIDDatabase
    db = NIDDatabase()
    db.load_builtins()
    print(f"traced_calls={sum(counts.values())} distinct_nids={len(counts)}")
    print("count nid library category name")
    for nid, count in counts.most_common():
        library = imports.get(int(nid, 16), "unknown")
        resolved = db.lookup_nid(int(nid, 16))
        name = names.get(nid, resolved[1] if resolved else "unknown")
        print(f"{count} {nid} {library} {category(library, name)} {name}")


if __name__ == "__main__":
    main()
