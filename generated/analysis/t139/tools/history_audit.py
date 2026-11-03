"""Audit every blob a push would upload, across full history.  history_audit.py <repo> [--exclude-containing <commit>]

Refs: all local branches except `master` and (with --exclude-containing) branches that contain <commit>.
Objects already on the public upstream (refs/remotes/origin/*) are skipped, since they are not new uploads.
Each new blob goes through audit_public.inspect_blob (private-reports rules) plus Sony/SCE notice strings.
Read-only; never fetches (missing promisor blobs are listed, not downloaded)."""
import collections
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("audit_public", ROOT / "tools" / "audit_public.py")
ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ap)
NOTICE = re.compile(rb"(?i)SCE CONFIDENTIAL|Sony (?:Interactive|Computer) Entertainment Inc\.?[^\n]{0,40}All Rights Reserved"
                    rb"|Copyright[^\n]{0,20}Sony|Evolution Studios|Havok\.com|Copyright[^\n]{0,30}Havok|RAD Game Tools")

repo = sys.argv[1]
excl = sys.argv[sys.argv.index("--exclude-containing") + 1] if "--exclude-containing" in sys.argv else None
env = dict(os.environ, GIT_NO_LAZY_FETCH="1")


def git(*a, inp=None):
    return subprocess.run(("git", "-C", repo) + a, input=inp, capture_output=True, env=env).stdout


refs = git("for-each-ref", "--format=%(refname:short)", "refs/heads").decode().split()
blocked = set(git("branch", "--format=%(refname:short)", "--contains", excl).decode().split()) if excl else set()
refs = [r for r in refs if r != "master" and r not in blocked]
upstream = ["--not", "--remotes=origin"] if git("for-each-ref", "refs/remotes/origin").strip() else []
lines = git("rev-list", "--objects", "--missing=print", *refs, *upstream).decode("utf-8", "replace").splitlines()
missing = [l[1:] for l in lines if l.startswith("?")]
paths = {}
for l in lines:
    if not l.startswith("?") and " " in l:
        oid, p = l.split(" ", 1)
        paths.setdefault(oid, p)
# keep blobs only
types = git("cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)", inp="\n".join(paths).encode()).decode().splitlines()
blobs = [(t.split()[0], int(t.split()[2])) for t in types if t.split()[1:2] == ["blob"]]
print(f"{repo}: {len(refs)} refs, {len(blocked)} excluded, {len(blobs)} new blobs, {len(missing)} missing objects")
findings = collections.defaultdict(list)
for oid, size in blobs:
    p = paths[oid]
    data = git("cat-file", "blob", oid) if size <= 8 * 1024 * 1024 else b"\0" * 9 * 1024 * 1024
    reasons = ap.inspect_blob(p, data, private_reports=True)
    # analysis reports are allowed in the private repo; only content rules matter there
    reasons = [r for r in reasons if r not in ("private/generated directory",)]
    if NOTICE.search(data):
        reasons.append("third-party notice: " + NOTICE.search(data).group(0)[:60].decode("utf-8", "replace"))
    for r in reasons:
        findings[r].append(p)
for r, ps in sorted(findings.items(), key=lambda x: -len(x[1])):
    print(f"{len(ps):6d}  {r}")
    for p in sorted(set(ps))[:12]:
        print("          ", p)
for m in missing[:5]:
    print("missing", m)
