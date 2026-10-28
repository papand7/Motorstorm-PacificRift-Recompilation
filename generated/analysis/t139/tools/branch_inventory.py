"""T139: machine-readable inventory of ps3recomp branches/worktrees with an upload-safety scan.

Read-only: runs only `git for-each-ref/worktree/status/rev-list/log/diff-tree/cat-file`, with lazy
fetching disabled (partial clone), so nothing is fetched, written or pushed.
Scans every blob introduced by a commit that is on a local branch but on no remote-tracking ref
(i.e. all history the private repository would receive that the public upstream does not have).

py -3 -I branch_inventory.py <ps3recomp main checkout> <out.json>
"""
import collections, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))
import audit_public as ap  # noqa: E402

REPO, OUT = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
ENV = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
SECRET = re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[0-9A-Z]{16}|xox[abpr]-[A-Za-z0-9-]{10,}"
                    rb"|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:(?:password|passwd|secret|api_?key|token)\s*[:=]\s*[\"'][^\"'\s]{8,}[\"'])")
SYNTHETIC_OK = re.compile(rb"FEEDFACE|SYNTHTOKEN|DEADBEEF|EXAMPLE|dummy|test", re.I)
NOREPLY = re.compile(r"noreply", re.I)


def git(*a, cwd=REPO, check=True):
    p = subprocess.run(["git", *a], cwd=cwd, capture_output=True, env=ENV)
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(a)}: {p.stderr.decode(errors='replace')}")
    return p.stdout.decode("utf-8", errors="replace")


# ---- refs and worktrees
refs = []
for line in git("for-each-ref", "--format=%(refname:short)%00%(objectname)%00%(upstream:short)%00%(committerdate:iso-strict)",
                "refs/heads").splitlines():
    n, h, up, d = line.split("\x00")
    refs.append({"branch": n, "commit": h, "upstream": up or None, "date": d})
wt, cur = {}, {}
for line in git("worktree", "list", "--porcelain").splitlines() + [""]:
    if not line:
        if cur.get("branch"):
            wt[cur["branch"]] = cur
        elif cur:
            wt[f"(detached:{cur.get('worktree')})"] = cur
        cur = {}
        continue
    k, _, v = line.partition(" ")
    cur[k] = v.replace("refs/heads/", "") if k == "branch" else (v or True)
detached = [v for k, v in wt.items() if k.startswith("(detached")]
# Detached worktree HEADs are listed like branches ("(detached) <path>") so their unique commits are counted
# and scanned too; they have no branch name and need one before they can be backed up.
for v in detached:
    h = v.get("HEAD")
    if h:
        name = f"(detached) {Path(v['worktree']).relative_to(REPO.parent).as_posix()}"
        refs.append({"branch": name, "commit": h, "upstream": None, "date": None})
        wt[name] = v
remotes = git("remote", "-v")
tags = git("tag", "--list").split()
base_pin = "0fe7dbf5db9a467aca268865fb26170ea113c541"
has_pin = subprocess.run(["git", "cat-file", "-e", base_pin + "^{commit}"], cwd=REPO, env=ENV).returncode == 0
remote_tips = git("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/remotes").splitlines()

# ---- local-only commits (on no remote-tracking ref) and the blobs they introduce
local_only = git("rev-list", "--branches", *[v["HEAD"] for v in detached if v.get("HEAD")], "--not", "--remotes").split()
commit_info, blob_paths = {}, collections.defaultdict(set)
for c in local_only:
    meta = git("show", "-s", "--format=%an%x00%ae%x00%cn%x00%ce%x00%s", c).rstrip("\n").split("\x00")
    rows = git("diff-tree", "-r", "--root", "--no-commit-id", "--no-renames", "-z", c).split("\x00")
    added = []
    for i in range(0, len(rows) - 1, 2):
        mode_old, mode_new, _, sha_new, status = rows[i].lstrip(":").split()
        if status != "D" and sha_new.strip("0"):
            added.append((rows[i + 1], sha_new, mode_new))
            blob_paths[(sha_new, mode_new)].add(rows[i + 1])
    commit_info[c] = {"author": meta[0], "author_email": meta[1], "committer_email": meta[3], "subject": meta[4], "added": added}

blob_issue = {}
keys = sorted(blob_paths)
p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=ENV)
for sha, mode in keys:
    p.stdin.write(sha.encode() + b"\n"); p.stdin.flush()
    hdr = p.stdout.readline().split()
    if len(hdr) < 3 or hdr[1] == b"missing":
        blob_issue[(sha, mode)] = {"missing blob (not local)"}
        continue
    data = p.stdout.read(int(hdr[2])); p.stdout.read(1)
    reasons = set()
    for path in blob_paths[(sha, mode)]:
        reasons |= set(ap.inspect_blob(path, data, symlink=(mode == "120000")))
    if ap.LOCAL_USER_PATH.search(data):
        reasons.add("local user path")
    for m in SECRET.finditer(data):
        if not SYNTHETIC_OK.search(data[max(0, m.start() - 200):m.end() + 200]):
            reasons.add("possible secret")
    blob_issue[(sha, mode)] = reasons
p.stdin.close(); p.wait()

findings_by_commit = {}
for c, ci in commit_info.items():
    f = [{"path": path, "reasons": sorted(blob_issue[(sha, mode)])} for path, sha, mode in ci["added"] if blob_issue[(sha, mode)]]
    findings_by_commit[c] = f


# ---- per branch
def dirty(path):
    if not path or not Path(path).is_dir():
        return None
    s = git("status", "--porcelain=v1", "--untracked-files=normal", cwd=path, check=False).splitlines()
    return {"modified": sum(1 for l in s if not l.startswith("??")), "untracked": sum(1 for l in s if l.startswith("??"))}


inv = []
for r in refs:
    b = r["branch"]
    own = git("rev-list", r["commit"], "--not", "--remotes").split()
    ab_pin = (git("rev-list", "--left-right", "--count", f"{base_pin}...{r['commit']}").split() if has_pin
              else ["0", str(len(git("rev-list", r["commit"]).split()))])
    w = wt.get(b, {}).get("worktree")
    d = dirty(w)
    finds = [dict(commit=c[:12], **f) for c in own for f in findings_by_commit.get(c, [])]
    emails = sorted({commit_info[c][k] for c in own for k in ("author_email", "committer_email")} )
    personal = [e for e in emails if not NOREPLY.search(e)]
    merged_into = [x for x in git("for-each-ref", "--format=%(refname:short)", "--contains", r["commit"], "refs/heads").split()
                   if x != b] if own else []
    if finds:
        elig = "blocked"
    elif not own:
        elig = "nothing-to-back-up"
    elif personal:
        elig = "eligible-after-email-decision"
    else:
        elig = "eligible"
    inv.append({
        "branch": b, "commit": r["commit"], "date": r["date"], "upstream": r["upstream"], "worktree": w,
        "behind_pin": int(ab_pin[0]), "ahead_pin": int(ab_pin[1]), "local_only_commits": len(own),
        "contained_in": merged_into[:8], "contained_in_count": len(merged_into),
        "dirty": d, "author_emails_non_noreply": len(personal),
        "findings": finds,
        "proposed_destination": None if not own else
            (f"private:legacy/detached/{b.split()[-1].replace('/', '-')}" if b.startswith("(detached)") else f"private:{b}"),
        "upload_eligibility": elig})

out = {
    "repo": "ps3recomp", "generated_by": "generated/analysis/t139/tools/branch_inventory.py",
    "remotes": remotes.splitlines(), "remote_tracking": remote_tips, "tags": tags, "pin": base_pin,
    "head": git("rev-parse", "--abbrev-ref", "HEAD").strip(),
    "worktrees_total": len(wt), "detached_worktrees": [v.get("worktree") for v in detached],
    "local_only_commits_total": len(local_only), "blobs_scanned": len(keys),
    "blobs_flagged": sum(1 for v in blob_issue.values() if v),
    "branches": inv,
}
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
c = collections.Counter(x["upload_eligibility"] for x in inv)
print(f"branches={len(inv)} worktrees={len(wt)} local_only={len(local_only)} blobs={len(keys)} flagged={out['blobs_flagged']} {dict(c)}")
