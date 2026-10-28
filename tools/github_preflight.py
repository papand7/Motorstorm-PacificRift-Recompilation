#!/usr/bin/env python3
"""Read-only pre-push check for the private GitHub repositories. It never pushes.

    python tools/github_preflight.py --repo <path> --remote private --branch <local> [--dest <remote branch>]
                                      [--expect <owner>/<name>] [--offline]

Fails (exit 1) unless all of these hold:
  * the remote URL points at github.com/<expect> and not at a public upstream (sp00nznet/ps3recomp);
  * every other remote whose URL is public upstream has push URL DISABLED;
  * GitHub reports the destination repository as private (skipped with --offline, reported as UNVERIFIED);
  * every blob introduced by the outgoing commits passes tools/audit_public.py's rules, has no local user path
    and no credential pattern;
  * no outgoing commit carries a non-noreply author/committer e-mail (warning only, use --allow-email);
  * no outgoing commit adds a .gitmodules entry or a Git LFS pointer (warning).
The outgoing set is `git rev-list <branch> --not --remotes`: commits no remote-tracking ref already has.
Lazy fetching is disabled, so in a partial clone nothing is downloaded.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_public as ap  # noqa: E402

PUBLIC_UPSTREAM = re.compile(r"github\.com[:/]+sp00nznet/ps3recomp(?:\.git)?/?$", re.I)
SECRET = re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[0-9A-Z]{16}"
                    rb"|xox[abpr]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
USER_PATH = re.compile(rb"(?i)[A-Z]:[\\/]+Users[\\/]+([^\\/\s\"'`]+)")
# Documentation and test fixtures use these stand-ins; any other profile name is treated as personal data.
PLACEHOLDER_USERS = {b"<name>", b"<user>", b"<username>", b"someone", b"username", b"%username%", b"$env:username",
                     b"public", b"default", b"..."}
LFS_POINTER = re.compile(rb"^version https://git-lfs\.github\.com/spec/v1\n")
ENV = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")


def git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=ENV)
    if p.returncode:
        raise SystemExit(f"git {' '.join(args)} failed: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout.decode("utf-8", errors="replace")


def remotes(repo: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for line in git(repo, "remote", "-v").splitlines():
        name, url, kind = line.split()[:3]
        out.setdefault(name, {})["push" if kind == "(push)" else "fetch"] = url
    return out


def outgoing_blobs(repo: Path, commits: list[str]):
    seen = set()
    for c in commits:
        rows = git(repo, "diff-tree", "-r", "--root", "--no-commit-id", "--no-renames", "-z", c).split("\x00")
        for i in range(0, len(rows) - 1, 2):
            _, mode, _, sha, status = rows[i].lstrip(":").split()
            if status != "D" and (sha, rows[i + 1]) not in seen:
                seen.add((sha, rows[i + 1]))
                yield c, rows[i + 1], sha, mode


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--repo", type=Path, default=Path("."))
    a.add_argument("--remote", required=True)
    a.add_argument("--branch", required=True)
    a.add_argument("--dest", help="remote branch name (default: same as --branch)")
    a.add_argument("--expect", help="<owner>/<name> the remote must point at")
    a.add_argument("--offline", action="store_true", help="skip the GitHub visibility query")
    a.add_argument("--allow-email", action="store_true", help="accept non-noreply commit e-mails")
    a.add_argument("--json", type=Path, help="also write the result as JSON")
    o = a.parse_args()
    repo, dest = o.repo.resolve(), o.dest or o.branch
    fail, warn, info = [], [], []

    rem = remotes(repo)
    if o.remote not in rem:
        raise SystemExit(f"remote '{o.remote}' is not configured in {repo}")
    url = rem[o.remote].get("push", rem[o.remote].get("fetch", ""))
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    slug = f"{m.group(1)}/{m.group(2)}" if m else None
    if PUBLIC_UPSTREAM.search(url):
        fail.append(f"remote '{o.remote}' pushes to the PUBLIC upstream ({url})")
    if not slug:
        fail.append(f"remote '{o.remote}' is not a github.com URL ({url})")
    if o.expect and slug and slug.lower() != o.expect.lower():
        fail.append(f"remote '{o.remote}' points at {slug}, expected {o.expect}")
    for name, r in rem.items():
        if PUBLIC_UPSTREAM.search(r.get("fetch", "")) and r.get("push") != "DISABLED":
            fail.append(f"public remote '{name}' push URL is {r.get('push')!r}, not DISABLED")

    visibility = "UNVERIFIED (offline)"
    if not o.offline and slug:
        p = subprocess.run(["gh", "api", f"repos/{slug}", "--jq", ".private,.visibility,.fork"],
                           capture_output=True, text=True)
        if p.returncode:
            fail.append(f"cannot read repository metadata for {slug} (gh auth / name?)")
        else:
            private, vis, fork = (p.stdout.split() + ["", "", ""])[:3]
            visibility = vis
            if private != "true" or vis != "private":
                fail.append(f"{slug} is not private (visibility={vis})")
            if fork == "true":
                fail.append(f"{slug} is a fork; create a standalone private repository")
    elif o.offline:
        warn.append("visibility not checked (--offline)")

    tip = git(repo, "rev-parse", "--verify", f"refs/heads/{o.branch}^{{commit}}").strip()
    commits = git(repo, "rev-list", tip, "--not", "--remotes").split()
    bad, emails, lfs, modules, nblobs = [], set(), [], [], 0
    batch = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, env=ENV)
    for c, path, sha, mode in outgoing_blobs(repo, commits):
        if mode == "160000":
            modules.append(path)
            continue
        batch.stdin.write(sha.encode() + b"\n")
        batch.stdin.flush()
        hdr = batch.stdout.readline().split()
        if len(hdr) < 3 or hdr[1] == b"missing":
            bad.append((c, path, ["blob not available locally"]))
            continue
        data = batch.stdout.read(int(hdr[2]))
        batch.stdout.read(1)
        nblobs += 1
        reasons = ap.inspect_blob(path, data, symlink=(mode == "120000"), private_reports=True)
        real_path = any(m.group(1).lower() not in PLACEHOLDER_USERS for m in USER_PATH.finditer(data))
        if "local user path (personal data)" in reasons and not real_path:
            reasons.remove("local user path (personal data)")
        elif real_path and "local user path (personal data)" not in reasons:
            reasons.append("local user path")
        if SECRET.search(data):
            reasons.append("credential pattern")
        if LFS_POINTER.match(data):
            lfs.append(path)
        if path == ".gitmodules":
            modules.append(path)
        if reasons:
            bad.append((c, path, reasons))
    batch.stdin.close()
    batch.wait()
    for c in commits:
        for e in git(repo, "show", "-s", "--format=%ae%n%ce", c).split():
            if not re.search(r"noreply", e, re.I):
                emails.add(c[:12])
    for c, path, reasons in bad:
        fail.append(f"{c[:12]} {path}: {', '.join(reasons)}")
    if emails:
        (warn if o.allow_email else fail).append(f"{len(emails)} outgoing commit(s) carry a non-noreply e-mail")
    if lfs:
        warn.append(f"Git LFS pointer(s): {lfs[:5]}")
    if modules:
        warn.append(f"submodule entries: {modules[:5]}")

    info += [f"repository   {repo}", f"remote       {o.remote} -> {url}", f"visibility   {visibility}",
             f"branch       {o.branch} ({tip[:12]}) -> {o.remote}/{dest}",
             f"outgoing     {len(commits)} commit(s), {nblobs} blob(s) scanned"]
    print("\n".join(info))
    for w in warn:
        print("WARN ", w)
    for f in fail[:200]:
        print("FAIL ", f)
    if len(fail) > 200:
        print(f"FAIL  ... {len(fail) - 200} more")
    ok = not fail
    print("RESULT", "PASS" if ok else "FAIL")
    if ok:
        print(f"push command (run it yourself, after approval): git -C \"{repo}\" push {o.remote} "
              f"refs/heads/{o.branch}:refs/heads/{dest}")
    if o.json:
        o.json.write_text(json.dumps({"ok": ok, "slug": slug, "visibility": visibility, "tip": tip,
                                      "commits": len(commits), "blobs": nblobs, "fail": fail, "warn": warn},
                                     indent=1), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
