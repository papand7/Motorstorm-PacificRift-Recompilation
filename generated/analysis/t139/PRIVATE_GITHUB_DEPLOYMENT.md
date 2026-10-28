# T139: private GitHub deployment and agent synchronisation

Date: 2026-10-28. I created no repository, pushed nothing, and ran no merge, rebase, reset or history rewrite. I
deleted no branch or worktree and touched no other agent's branch or worktree. Nothing was built or launched.
Paths are relative to the workspace (the `motorstorm/` folder). The machine-readable inventories are
`ps3recomp_branch_inventory.json` / `.csv` and `root_branch_inventory_pre.json`, all in this folder.

**Status: BLOCKED at the approval boundary.** The `gh` token is invalid and no GitHub owner has been named. All
local preparation is done (§11).

## 1. Current Git topology (VERIFIED)

```
motorstorm/                     project repo, branch agent/t138-private-github-setup -> agent/t139-… (same tree), no remote
├── ps3recomp/                  recompiler repo (partial clone, blob:none), HEAD motorstorm/v0.15-local
│     origin  fetch https://github.com/sp00nznet/ps3recomp.git   (PUBLIC upstream)
│             push  DISABLED                                      (T138 guard, verified)
├── ps3recomp-*/ , Motorstorm01/t*-worktree/, scratch/t*/        105 linked worktrees of ps3recomp in total
└── original/ generated/ build/ scratch/ …                       ignored by the project repo
```

## 2. Root repository inventory (VERIFIED)

| Item | State |
|---|---|
| Branch / HEAD | `agent/t138-private-github-setup` at `f18a620` before T139; all 8 T138 commits are present (`835ad5a`, `08d9e43`, `dc140fc`, `e3cdee1`, `714b7e8`, `558d07a`, `0ac419c`, and `f18a620` for the push-guard note). |
| Tracked | 123 files before T139. `audit_public.py --staged --private-reports` passes; `check_docs.py` finds 0 problems. |
| Remotes | none |
| History | 8 commits, all with the noreply author/committer `papand7 <…@users.noreply.github.com>`. 131 blobs scanned: no secrets, no binaries, no real user paths. The two user-profile-path hits are placeholders (`<name>` in AGENT_WORKFLOW.md, `someone` in a test fixture). |
| Uncommitted before T139 | none tracked; 92 untracked `generated/analysis/<task>/` folders (reports, visible to Git but deliberately not committed) |
| Handoff accuracy | T138 report confirmed: the push guard is applied and `gh` is still invalid. One update: there are now 104 local branches (new: `agent/t141-rsx-blending-feedback`, an active agent) and 105 worktrees. |

## 3. ps3recomp branch/worktree inventory (VERIFIED, `tools/branch_inventory.py`)

| Item | Count / state |
|---|---|
| Local branches | 104: `master`, `motorstorm/v0.15-local`, `motorstorm/v0.17-integration`, and 101 `agent/*` |
| Worktrees | 105. 13 are detached; 12 branches have no worktree. |
| Remote-tracking refs | 15 `origin/*` (public). Local `master` tracks `origin/master` and is 198 commits behind it, with no local commits. No other branch has an upstream. |
| Tags | 14: 10 upstream `v0.*`, plus `baseline/int4-chain-27fps`, `baseline/int5-lsinline-2754fps`, `ms-baseline-v0.15-local`, `rollback/pre-spu-direct-branch` |
| Local-only commits | 340 in total: 312 on branches, plus **28 reachable only from detached worktree HEADs**. The detached ones are `scratch/t109/onto_t108` (18), `ps3recomp-t24-ppu` (6), `scratch/t58/nolink` (2), and `scratch/t58/{cp,merged,prop}` and `scratch/t59/w_nolink` (1 each). |
| Unique work | 41 branch tips have commits that no other branch contains (the `tip_unique` column in the CSV). |
| Dirty worktrees | 14: the main checkout (2 modified `scratch/ppu_conformance*`, as in T138); `t18-c38-trace`, `t49`, `t83` and `t89b` with modified files; 9 others with only untracked files. Uncommitted work is never uploaded; it belongs to its agent. |
| Lineage | All current lines descend from T113 `2562ba8`, which contains upstream `origin/master` (v0.17.0, `a6d76c8`) and the pin `0fe7dbf`. 11 branches contain `2562ba8`. |

The CSV has, for every branch: name, hash, worktree, ahead/behind the pin, local-only count, whether its tip is
unique, dirty state, proposed destination and upload eligibility.

## 4. Security audit results

| Check | Result |
|---|---|
| `audit_public.py --staged` at proposed ps3recomp `main` (`2562ba8`) | **The same 25 inherited upstream items as T138**; nothing new (VERIFIED). |
| 1,106 blobs introduced by the 340 local-only commits (history, including later-deleted files) | 1 flagged: `tools/msre/INTEGRATION.md` (commit `65ea4b0`) contains a real local user-profile path. |
| Secrets (GitHub/AWS/Slack tokens, private keys, password literals) | 0 real hits; the known synthetic RPCN fixtures were already noted by T138. |
| Binaries, ELF/SELF, PSARC, lifted-code signatures, known input hashes | 0 in local-only history. |
| Git LFS / submodules | none: there is no `.gitmodules` and no LFS pointer. The only `.gitattributes` is `tools/msre/.gitattributes` (`eol=lf`). |
| Commit e-mail | **6 commits carry the owner's personal e-mail** (`f373398`, `02646b7`, `0847afe`, `b5e2831`, `8e82d28`, `ab989d3`). `f373398` is the base of `motorstorm/v0.15-local` and an ancestor of 103 of the 104 branches, so every upload contains it. |
| Root repo | clean (§2) |
| Upstream workflows on every ps3recomp branch | `linux*`, `macos` and `windows` run on push to main/master and on every PR (macOS minutes are expensive in a private repo). `release.yml` runs on `v*` tags with `contents: write`. Mitigation: keep Actions **disabled** in the private ps3recomp repository and push no tags (§6). |

**Per-branch upload safety** (`upload_eligibility` in the JSON/CSV):

| Class | Branches | Meaning |
|---|---|---|
| `eligible-after-email-decision` | 111 (98 branches + 13 detached HEADs) | They pass every content check. Only the personal-e-mail commits need a decision. |
| `blocked` | 5: `agent/t39-workbench-integration`, `t43-menu-dependencies`, `t46-ui-text`, `t49-glyph-integrity`, `t53-text-root-cause` | They contain `65ea4b0` (the local user path). Keep them local, back them up with a bundle, or the owner accepts the path. |
| `nothing-to-back-up` | `master` | upstream only |

Private hosting is still a copy on a third-party service. Proprietary game data stays excluded no matter which way
these decisions go.

## 5. Proposed private GitHub destinations

| Repository | Contents | Default branch |
|---|---|---|
| `<owner>/motorstorm-pacific-rift-native` (A) | the project repo: README, docs, tools, CI, templates, approved reports | `main` |
| `<owner>/motorstorm-ps3recomp` (B) | the recompiler, runtime, SPU/SPURS, RSX/D3D12, synthetic tests, MotorStorm branches | `main` = `2562ba8` |

Both repositories are **private** and created standalone. Do not use a GitHub fork: a fork of a public repository
cannot be private.

## 6. Remote configuration

The push guard is already applied (T138) and verified: `git -C ps3recomp remote get-url --push origin` returns
`DISABLED`. Fetching from the public upstream still works. The setting lives in `ps3recomp/.git/config`, so it
covers all 105 worktrees at once; a push to `origin` from any worktree fails with "repository 'DISABLED' does not
exist". I did not test the guard by pushing.

**Still to apply after approval** (the shared config affects every worktree, so this is listed rather than done):

```bash
git remote add origin https://github.com/<owner>/motorstorm-pacific-rift-native.git      # root
git -C ps3recomp remote add private https://github.com/<owner>/motorstorm-ps3recomp.git
git -C ps3recomp config remote.private.tagOpt --no-tags     # no tag traffic with private
git -C ps3recomp config push.default nothing                # a bare `git push` pushes nothing, anywhere
git -C ps3recomp config branch.autoSetupMerge false         # new branches never track origin/* (public)
```

What these do to other agents: a bare `git push` now does nothing, which is intended. New branches start with no
upstream. Fetching, commits and worktrees are unaffected. All of this is scripted in `tools/github_setup.sh`.

## 7. Branch upload manifest

Every push goes through `tools/github_preflight.py` and uses an explicit refspec. No tags are pushed.

| Wave | Local ref | Destination (`private` = B, `origin` = A) | Condition |
|---|---|---|---|
| A-1 | root `main` (created locally at the T139 tip, which contains T138) | `origin/main` | owner approval |
| A-2 | `agent/t138-private-github-setup`, `agent/t139-private-github-deployment` | same names | optional record |
| B-1 | `agent/t113-black-race-repair` @ `2562ba8` | `private/main` | e-mail decision |
| B-2 | current lines: `agent/t119-…`, `t120-…`, `t122-…`, `t123-…`, `t123b-…`, `t131-…`, `t132-…`, `t132b-…`, `t133-…`, `t134-…`, `t136-…`, `t137-…` | same names | approval per branch. `t141` (active) only when its agent hands off. |
| B-3 | the other 41 unique-tip and remaining eligible `agent/*`; `motorstorm/v0.15-local`, `motorstorm/v0.17-integration` → `legacy/…` | same names / `legacy/*` | bulk backup approval |
| B-4 | 6 detached HEADs with unique commits | `legacy/detached/<worktree>` (needs a local branch created first) | approval |
| — | the 5 blocked branches | not uploaded; `git bundle` backup | owner decision |
| — | `master`, upstream tags `v0.*`, local tags | not uploaded | — |

No branch is merged into `main`. `integration/*` and `release/*` start empty.

## 8. GitHub Actions review

**Root `ci.yml`** (parsed with PyYAML 6, VERIFIED):

- Triggers: `pull_request`, `push: main`, `workflow_dispatch`. `permissions: contents: read`.
- Concurrency group per ref.
- `actions/checkout` and `actions/setup-python` are pinned by SHA, with `persist-credentials: false`.
- Steps: audit, docs check, `compileall`, and 8 synthetic tests (T139 added `test_github_preflight`).
- No secrets, artifacts, caches, game data or network fetches beyond the actions.
- All steps pass locally on Python 3.14. They have not run on GitHub yet (the job uses 3.12).

T139 also added: `dependabot.yml` (monthly action updates), PR and issue templates (`blank_issues_enabled: false`).
I left out CODEOWNERS: with one owner it adds nothing, and an unknown handle would show errors on GitHub.

**ps3recomp:** the upstream workflows are not appropriate for the private repository (cost, and `release.yml` can
publish), so keep Actions disabled. A later task can add a lightweight Windows-only workflow on an `agent/*`
branch: the SPU helper and runtime unit tests, plus `audit_public --staged`. It must stay offline and use no SDK.

## 9. README presentation review

| Item | Result |
|---|---|
| Banner | Renders (original SVG, no external fonts or scripts). |
| Badges | Static shields that state facts; no CI badge until CI has run. |
| Mermaid | Basic `flowchart` syntax; `check_docs` checks its structure. It has not been rendered on GitHub (PARTIAL). |
| Tables, links | `check_docs`: 61 files, 0 problems. |
| Status | Accurate: race ≈ 4–5 FPS. The 720p/60 target is labelled as a target, not as achieved. |
| Screenshots | Placeholders only; none were fabricated. |
| Legal notice | Present. |

T139 changes:

- The repository-layout row now points to the private ps3recomp repository.
- New links to `docs/GITHUB_WORKFLOW.md` and `docs/REPOSITORY_STRUCTURE.md`.
- New `docs/media/social-preview.svg` (1280×640, original artwork in the banner's motifs). A rendered PNG check is
  at `generated/analysis/t139/social_preview.png`; GitHub needs a PNG upload, which is optional for a private
  repository.

## 10. Agent synchronisation

The procedure is in `docs/GITHUB_WORKFLOW.md`, with Git Bash and PowerShell commands. It covers:

- fetch and worktree creation from `private/main`;
- reviewed publishing with preflight and an explicit refspec, and `gh pr create --repo …` (always with `--repo`);
- renderer conflicts, checked with `merge-tree`, merged only in `integration/*`, and kept behind `RSX_*` switches;
- local commits, which remain valid (inventory script, bundles);
- the canonical baseline (`private/main`);
- no force pushes;
- offline tests;
- asset exclusion.

`docs/REPOSITORY_STRUCTURE.md` describes the two repositories and the branch namespaces.

## 11. Exact approvals still required

1. **GitHub owner** (account or organisation) for both repositories, and confirmation of the names
   `motorstorm-pacific-rift-native` and `motorstorm-ps3recomp`.
2. **Re-authenticate:** run `gh auth login -h github.com` yourself (token scopes `repo`, `workflow`). I never handle
   the credentials.
3. **Creation and settings:** approve running `bash tools/github_setup.sh <owner> --apply`.
   It creates both repositories as private, verifies `PRIVATE fork=false`, adds the remotes and the three ps3recomp
   config lines (§6), and applies the settings. It pushes nothing.
4. **Personal e-mail on 6 commits:** accept it (it is visible to collaborators of the private repository), or
   authorise a separate history rewrite (that changes every hash below `f373398` and affects all worktrees; not
   recommended). If your GitHub account blocks pushes that expose a private e-mail, the push will be refused (GH007)
   until you change that setting.
5. **Blocked branches** (5 branches containing `65ea4b0`): accept the local path, or keep them local with a bundle.
6. **Upload waves** A-1, B-1, B-2, B-3, B-4 (§7), each one explicitly.
7. **Plan limits:** branch protection on private repositories needs GitHub Pro or Team; secret scanning needs
   Secret Protection. If neither is available, `main` is protected only by convention and the local guards.
8. Optional: commit approved `generated/analysis/<task>/` reports (T138: 293 pass, 32 need path edits).

## 12. Final deployment status

| Step | State |
|---|---|
| Inventory, audit, history scan | done (VERIFIED) |
| Public upstream push guard | applied in T138, re-verified |
| Docs, templates, Dependabot, preflight tool and its tests, setup script | committed locally on the root branch `agent/t139-private-github-deployment` (`8704ded` + report commit); local root `main` created at the same commit |
| Repositories created | **no**: there is no owner and the token is invalid |
| Remotes `origin` (root) and `private` (ps3recomp) | not added (they need the URLs) |
| Push | **none** |
| Post-push verification | to do: `gh repo view <r> --json visibility` → PRIVATE; `git ls-remote private refs/heads/<b>` equals the local hash; check expected files with `gh api repos/<r>/contents`; check the CI run with `gh run list --repo <A>`; check `git ls-remote origin` in ps3recomp, which must still equal the earlier `origin/*` refs |

### Commands and tools

- `py -3 -I generated/analysis/t139/tools/branch_inventory.py ps3recomp <out.json>` is read-only and disables lazy
  fetching. It takes about 3 minutes.
- `python tools/github_preflight.py --repo <r> --remote <private|origin> --branch <b> --expect <owner>/<name>` is
  the pre-push gate. It never pushes. Tests: `tools/test_github_preflight.py`, 13/13 pass.
- `bash tools/github_setup.sh <owner> [--apply]` does a dry run by default.
