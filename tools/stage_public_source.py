#!/usr/bin/env python3
"""Stage and audit an allowlisted, source-only release from this workspace."""

import argparse
from pathlib import Path
import shutil
import sys

from audit_public import PRIVATE_DIRS, audit_tree


ROOT = Path(__file__).resolve().parents[1]
FILES = (".gitignore", "AGENTS.md", "README.md", "THIRD_PARTY_LICENSES.md")
DIRS = ("docs", "tools", "port", "ps3recomp")
SKIP_DIRS = PRIVATE_DIRS | {
    ".github", ".agents", ".codex", ".aws", ".venv", ".vs", ".vscode",
    # Upstream test output and packaging media are not needed to rebuild the
    # toolkit, and include generated fixtures or media with unclear provenance.
    "tests", "scratch", "packaging",
}
SKIP_SUFFIXES = {".pdf", ".png", ".icns"}


def copy_source_tree(source: Path, dest: Path) -> None:
    for item in source.iterdir():
        if item.is_symlink():
            raise ValueError(f"Symlink in source tree: {item}")
        if item.is_dir():
            if item.name.lower() in SKIP_DIRS:
                continue
            child = dest / item.name
            child.mkdir()
            copy_source_tree(item, child)
        elif item.is_file():
            if item.suffix.lower() in SKIP_SUFFIXES:
                continue
            # The audit validates every staged byte, including filenames and
            # content. All other files are copied and checked, not hidden.
            shutil.copy2(item, dest / item.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="new, empty staging path")
    args = parser.parse_args()
    dest = args.destination.resolve()
    if dest.exists():
        parser.error(f"Refusing to overwrite existing path: {dest}")
    if dest == ROOT or ROOT not in dest.parents:
        parser.error("Destination must be a new path inside the project workspace")
    dest.mkdir(parents=True)
    try:
        for name in FILES:
            shutil.copy2(ROOT / name, dest / name)
        for name in DIRS:
            (dest / name).mkdir()
            copy_source_tree(ROOT / name, dest / name)
        findings = audit_tree(dest)
        if findings:
            for path, reasons in findings:
                print(f"BLOCK {path}: {', '.join(reasons)}")
            print(f"Staging failed: {len(findings)} audit finding(s); inspect {dest}", file=sys.stderr)
            return 1
    except (OSError, ValueError) as error:
        print(f"Staging failed: {error}; inspect {dest}", file=sys.stderr)
        return 2
    print(f"Public source staged and audited: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
