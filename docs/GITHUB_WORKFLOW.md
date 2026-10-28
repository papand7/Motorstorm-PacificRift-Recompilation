# GitHub workflow (private repositories)

How agents and the owner share work through the two **private** GitHub repositories described in
[REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md). Local commits and offline tests remain the normal way of
working: **publishing is deliberate, reviewed and approved by the owner — never automatic, never after every
commit.**

`<owner>` below is the GitHub account or organisation the owner chose. Commands are given for Git Bash; PowerShell
differences are noted (`git -C <path>` works the same in both).

## 0. One-time setup (owner)

```bash
# Project repository (workspace root)
git remote add origin https://github.com/<owner>/motorstorm-pacific-rift-native.git
# Recompiler repository: the public upstream stays fetch-only, the private one is a second remote
git -C ps3recomp remote set-url --push origin DISABLED        # already applied (T138)
git -C ps3recomp remote add private https://github.com/<owner>/motorstorm-ps3recomp.git
git -C ps3recomp config remote.private.tagOpt --no-tags       # do not import or push upstream tags by accident
git -C ps3recomp config push.default nothing                  # a bare `git push` pushes nothing
git -C ps3recomp config branch.autoSetupMerge false           # new branches do not track origin/* (public)
```

Remote configuration lives in `ps3recomp/.git/config` and is **shared by every linked worktree** — one change
protects all agents at once, and no agent needs to repeat it.

## 1. Fetch from the private repository

```bash
git -C ps3recomp fetch private                 # all agents see private/<branch>
git -C ps3recomp fetch origin                  # public upstream, read-only (partial clone: blobs on demand)
git fetch origin                               # project repository
```

Fetching never changes a branch or worktree.

## 2. Create an isolated worktree

```bash
git -C ps3recomp worktree add ../ps3recomp-t<N> -b agent/t<N>-<topic> private/main
```

PowerShell: identical. Base on what the task brief names; `private/main` is the canonical integration baseline
(section 7). Because `branch.autoSetupMerge=false`, the new branch tracks nothing.

## 3. Publish a reviewed branch (only after owner approval)

```bash
cd ps3recomp-t<N>
python ../tools/audit_public.py --staged                       # 25 inherited upstream items are expected
python ../tools/github_preflight.py --repo . --remote private \
       --branch agent/t<N>-<topic> --expect <owner>/motorstorm-ps3recomp
# preflight prints the exact command when everything passes:
git push private refs/heads/agent/t<N>-<topic>:refs/heads/agent/t<N>-<topic>
```

Always name the source and destination ref explicitly. Never use `git push --all`, `--mirror`, `--tags`, or push
to `origin` in ps3recomp (it is the public upstream; its push URL is `DISABLED` and pushes fail by design).

PowerShell:

```powershell
Set-Location ps3recomp-t<N>
python ..\tools\github_preflight.py --repo . --remote private --branch agent/t<N>-<topic> --expect <owner>/motorstorm-ps3recomp
git push private "refs/heads/agent/t<N>-<topic>:refs/heads/agent/t<N>-<topic>"
```

## 4. Open a pull request

```bash
gh pr create --repo <owner>/motorstorm-ps3recomp --base main --head agent/t<N>-<topic> \
   --title "T<N>: <topic>" --body-file generated/analysis/t<N>/PR_BODY.md --draft
```

Always pass `--repo`: without it `gh` may pick the public upstream (`origin`) in ps3recomp. The template in
`.github/pull_request_template.md` lists the required evidence (tests, audit, VERIFIED/PARTIAL/HYPOTHESIS labels).
Merges into `main` happen through the PR only, by the owner or an authorised integration task.

## 5. Conflicting renderer modifications

The D3D12 backend (`runtime/rsx/d3d12_*`, `rsx_*`) is changed by several lines at once (T113/T119/T120/T133/T137).

1. Do not resolve conflicts on someone else's branch. Check first, without touching any worktree:
   `git -C ps3recomp merge-tree --write-tree --name-only private/main agent/t<N>-<topic>`.
2. If it conflicts, create `integration/<name>` from `private/main` in a new worktree and merge the agent branches
   there (`git merge --no-ff`), one at a time, running the renderer tests after each.
3. Keep every renderer change behind its runtime switch (`RSX_*`) until a controlled game run validates it, so
   integration can take both sides without changing default behaviour.
4. Record the resolution in the integration report; open one PR from `integration/<name>` to `main`.

## 6. Preserve local-only commits

- Local commits are valid; nobody is required to push. Before deleting a worktree or branch (owner only), list what
  exists nowhere else: `git -C ps3recomp log --oneline <branch> --not --remotes`.
- Regenerate the inventory of all branches and their unique commits:
  `python generated/analysis/t139/tools/branch_inventory.py ps3recomp <out.json>`.
- Back up a whole repository without publishing it: `git -C ps3recomp bundle create <path>.bundle --branches`
  (stored outside the workspace, never uploaded to a public service).

## 7. Canonical integration baseline

`private/main` in the recompiler repository and `origin/main` in the project repository. At T139 the proposed
recompiler `main` is `2562ba8` (T113, contained in every current line: T119, T120, T122, T132B, T133, T134, T136,
T137). It moves only through reviewed PRs; `docs/STATUS.md` names the current baseline in its newest entry.

## 8. Prevent force pushes

- GitHub: `main` protection forbids force pushes and deletion (owner applies; see the T139 report).
- Locally: never use `--force` / `+refspec`; if a push is rejected, fetch and inspect — do not overwrite.
  `git config --global push.useForceIfIncludes true` limits damage if a force push is ever authorised.

## 9. Offline tests before submitting

Project repository:

```bash
python tools/audit_public.py --staged --private-reports
python tools/check_docs.py
python tools/test_audit_public.py && python tools/test_github_preflight.py
```

ps3recomp: the focused test of the change plus the relevant suite (e.g. `tools/test_spu_*.py`,
`runtime/spu/tests`, the renderer tests named in the task report). No game build or launch without the owner's
authorisation.

## 10. Keep proprietary assets out

- The pre-commit hook (`git config core.hooksPath tools/hooks`, already set at the root) and CI run
  `audit_public.py`; `github_preflight.py` repeats the check on the outgoing **history**, so a file added and
  later deleted is still caught.
- Never `git add -f`; never commit from `original/`, `generated/` (except reviewed reports), `build/`, `scratch/`.
- Lifted output of the game or firmware, extracted SPU modules, captures and dumps stay local even in a private
  repository: private hosting is still a copy on a third-party service.
- Replace absolute paths like `C:\Users\<name>\...` with workspace-relative paths.
