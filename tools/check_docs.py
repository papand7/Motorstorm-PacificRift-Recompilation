#!/usr/bin/env python3
"""Validate the project's Markdown: relative links and anchors resolve, Mermaid blocks are well formed.

Checks every tracked-style Markdown file at the root and under docs/ (pass paths to check others). Remote URLs
are not fetched. Exit 1 on any problem.
"""

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ["README.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md", "THIRD_PARTY_LICENSES.md", "docs"]
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|<img[^>]+src=\"([^\"]+)\"|!\[[^\]]*\]\(([^)\s]+)\)")
FENCE = re.compile(r"^```(\w*)\s*$")
MERMAID_TYPES = ("flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram", "stateDiagram-v2",
                 "erDiagram", "gantt", "pie", "timeline", "mindmap", "gitGraph")


def slug(heading: str) -> str:
    """GitHub's heading anchor: lower case, drop punctuation except - and _, spaces to -."""
    text = re.sub(r"<[^>]+>", "", heading).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    out = set()
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        m = None if in_fence else re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            s = slug(m.group(1))
            n = seen.get(s, 0)
            out.add(s if n == 0 else f"{s}-{n}")
            seen[s] = n + 1
    return out


def check_mermaid(block: list[str]) -> list[str]:
    errors = []
    body = [l for l in block if l.strip() and not l.strip().startswith("%%")]
    if not body or not body[0].strip().split()[0] in MERMAID_TYPES:
        errors.append("unknown or missing diagram type")
        return errors
    text = "\n".join(body)
    for o, c in ("[]", "()", "{}"):
        if text.count(o) != text.count(c):
            errors.append(f"unbalanced {o}{c}")
    if text.count('"') % 2:
        errors.append("unbalanced quotes")
    opens = sum(1 for l in body if re.match(r"^\s*subgraph\b", l))
    ends = sum(1 for l in body if re.match(r"^\s*end\s*$", l))
    if opens != ends:
        errors.append(f"{opens} subgraph vs {ends} end")
    return errors


def check_file(path: Path) -> list[str]:
    problems = []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_fence, lang, block, start = False, "", [], 0
    for no, line in enumerate(lines, 1):
        m = FENCE.match(line)
        if m:
            if not in_fence:
                in_fence, lang, block, start = True, m.group(1), [], no
            else:
                if lang == "mermaid":
                    problems += [f"{path.relative_to(ROOT)}:{start}: mermaid: {e}" for e in check_mermaid(block)]
                in_fence = False
            continue
        if in_fence:
            block.append(line)
            continue
        for g in LINK.finditer(line):
            target = next(x for x in g.groups() if x)
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            file_part, _, frag = target.partition("#")
            dest = (path.parent / file_part).resolve() if file_part else path
            if not dest.exists():
                problems.append(f"{path.relative_to(ROOT)}:{no}: missing link target {target}")
            elif frag and dest.suffix.lower() == ".md" and frag not in anchors(dest):
                problems.append(f"{path.relative_to(ROOT)}:{no}: missing anchor #{frag} in {dest.name}")
    if in_fence:
        problems.append(f"{path.relative_to(ROOT)}:{start}: unterminated code fence")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=DEFAULT)
    args = parser.parse_args()
    files = []
    for p in args.paths:
        p = (ROOT / p) if not Path(p).is_absolute() else Path(p)
        files += sorted(p.rglob("*.md")) if p.is_dir() else [p]
    problems = [x for f in files for x in check_file(f)]
    for x in problems:
        print(x)
    print(f"check_docs: {len(files)} file(s), {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
