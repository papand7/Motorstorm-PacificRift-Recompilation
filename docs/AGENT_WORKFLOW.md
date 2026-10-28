# Agent workflow

Several AI coding agents work on this project at the same time, each on one task (T<number>). These rules keep
their work isolated and keep private material out of Git. [AGENTS.md](../AGENTS.md) has the project rules; this
page has the procedure.

## Procedure

1. **Read** `AGENTS.md`, the newest entries of `docs/STATUS.md`, and the task brief.
2. **Inspect** what exists: `git -C ps3recomp worktree list`, `git -C ps3recomp branch --list 'agent/*'`, and the
   reports of related tasks in `generated/analysis/`.
3. **Create a dedicated worktree** for ps3recomp work, from the base the brief names:
   `git -C ps3recomp worktree add ../ps3recomp-t<N> -b agent/t<N>-<topic> <base>`.
   Project-repository work (docs, tools) goes on its own `agent/t<N>-<topic>` branch of this repository.
4. **Commit in small, logical, local commits.** Run `python tools/audit_public.py --staged` before each commit;
   in a ps3recomp worktree run `python ../tools/audit_public.py --staged` and compare against the base: the 25
   upstream items listed in `generated/analysis/t138/PRIVATE_GITHUB_SETUP.md` are expected.
   End messages with the attribution trailer the session provides.
5. **Test**: the focused test for the change plus the relevant offline suite. A game build or launch needs the
   owner's authorisation; never claim an in-game result without a controlled run.
6. **Hand off** with `generated/analysis/t<N>/<REPORT>.md`: what changed, commit hashes, test results, findings
   labelled VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED, and the exact next step. Add a short entry to
   `docs/STATUS.md`.
7. **Never merge, rebase, push or rewrite history** without explicit authorisation. In ps3recomp, `origin` is the
   public upstream: a push there would publish MotorStorm work.
8. **Do not modify another agent's files, branch or worktree.** Use `git merge-tree` to check integration
   conflicts instead of merging; cherry-pick with `-x` onto your own branch if the brief allows it.
9. **Keep proprietary material outside Git**: game inputs in `original/`, lifted code and captures in
   `generated/`, binaries in `build/`. Never `git add -f` past `.gitignore`.

## Shared resources

- The Git stash is shared by every worktree. Do not use bare `git stash`; prefer a temporary WIP commit.
- One GPU and one game instance at a time: check that no other run is active before launching (when authorised).
- `build/motorstorm-t<N>/` is yours; `build/motorstorm/` is the shared baseline — do not rebuild it unless asked.

## Promoting a report to Git

Reports and analysis scripts under `generated/analysis/<task>/` are visible to Git (`*.md`, `tools/*.py`); every
other generated file stays ignored. The pre-commit hook (`git config core.hooksPath tools/hooks`) runs
`audit_public.py --staged --private-reports`, which also rejects guest disassembly listings, hex dumps and local
user paths in those files. Replace `C:\Users\<name>\...` with workspace-relative paths before committing.
