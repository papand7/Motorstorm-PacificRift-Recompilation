# Repository structure

The project lives in **two Git repositories**. Neither replaces the other.

| | Project repository | Recompiler repository |
|---|---|---|
| Local path | workspace root `motorstorm/` | `motorstorm/ps3recomp/` (+ ~100 linked worktrees `ps3recomp-*`) |
| Contents | README, `docs/`, `tools/`, `port/` (without lifted code), CI, reviewed `generated/analysis/<task>/` reports and scripts | ps3recomp: lifters, PPU/SPU runtime, SPURS, RSX/D3D12 backend, synthetic tests, MotorStorm agent branches |
| Private GitHub repository (proposed) | `<owner>/motorstorm-pacific-rift-native` | `<owner>/motorstorm-ps3recomp` |
| Remotes | `origin` → private project repository | `origin` → public upstream `sp00nznet/ps3recomp`, **fetch only** (push URL `DISABLED`); `private` → private recompiler repository |
| Default branch | `main` | `main` = the common integration base (T113 `2562ba8` at T139) |
| History | starts at T138 baseline `835ad5a` | upstream history + MotorStorm local commits |

`ps3recomp/` is ignored by the project repository (`.gitignore` ignores every top-level path not re-included).
It may later be linked as a submodule; until then the two are versioned independently.

## Never in either repository

Game disc image, `EBOOT.BIN`/decrypted ELF, PSARC/Bink/audio assets, SPU modules extracted from the game,
`libsre.sprx` or other firmware, lifted PPU/SPU source of the game or firmware, captures, frame or shader dumps,
traces, objects, executables, credentials. The guard is `tools/audit_public.py --staged` (pre-commit hook and CI);
`.gitignore` alone is not a guarantee.

## Branch namespaces (both repositories)

| Pattern | Purpose | Who pushes |
|---|---|---|
| `main` | Reviewed, stable baseline. Protected: pull requests only, no force push, no deletion. | nobody directly; PR merge |
| `agent/t<N>-<topic>` | One agent task, isolated. May stay local forever. | the owning agent, after audit and owner approval |
| `integration/<name>` | Controlled multi-agent integration (merge results of several `agent/*`). | integration task only |
| `release/<version>` | Future release preparation (source only). | owner |
| `legacy/*` | Historical local lines kept for reference (e.g. `motorstorm/v0.15-local`). | owner |

Upstream version tags (`v0.*`) are **not** pushed to the private recompiler repository: upstream's
`release.yml` reacts to `v*` tags.

See [GITHUB_WORKFLOW.md](GITHUB_WORKFLOW.md) for the day-to-day commands.
