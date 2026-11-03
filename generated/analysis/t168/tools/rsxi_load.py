#!/usr/bin/env python3
"""T168: read RSXI captures. Backends print C floats, so nan/inf are mapped before json parsing."""
import json
import re
from pathlib import Path

_BAD = re.compile(r"(?<![\w\"])-?(nan|inf)(?:\([a-z]*\))?(?![\w\"])", re.I)


def events(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                try:
                    out.append(json.loads(_BAD.sub("null", line)))
                except json.JSONDecodeError:
                    out.append({"e": "unparsed"})
    return out


def manifest(capdir):
    return json.loads((Path(capdir) / "manifest.json").read_text(encoding="utf-8", errors="replace"))
