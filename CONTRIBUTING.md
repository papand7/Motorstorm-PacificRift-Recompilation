# Contributing

This is a private repository. Contributions come from the owner and from AI coding agents working under
[AGENTS.md](AGENTS.md) and [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md).

## Ground rules

- **Original behaviour first.** No interpreter replacing lifted code, no engine remake, no approximate physics,
  no changes to physics constants, simulation time step or gameplay logic.
- **Opt-in experiments.** A behaviour change that is not yet verified in a controlled run ships behind an
  environment switch with the original behaviour as default, or is trivially reversible.
- **Evidence.** Label findings VERIFIED, PARTIAL, HYPOTHESIS or BLOCKED. Synthetic benchmarks are not game
  frame rates.
- **Tests.** Add a focused test when changing framework behaviour.
- **No private material in Git** (see below).

## Workflow

1. Branch: `agent/t<N>-<topic>` (agents) or a topic branch; never commit directly to the default branch.
2. One-time setup per clone: `git config core.hooksPath tools/hooks` (runs the audit before every commit).
3. Before committing: `python tools/audit_public.py --staged --private-reports` and `python tools/check_docs.py`
   if documentation changed.
4. Open a pull request; integration happens by review, never by force-push.

## What must never be committed

Game disc images, extracted or decrypted executables (`EBOOT.BIN`, `*.elf`, `*.self`), SPRX/PRX modules, SPU
images, firmware, keys, game textures/models/audio/video, PSARC archives, lifted or decompiled game code, frame
captures, memory dumps, traces, build outputs, credentials and personal data. `.gitignore` and the audit catch
the common cases; they cannot prove provenance, so review every staged file.

## Screenshots

Frame captures show copyrighted game content. To add one to the README:

1. The repository owner approves the specific image.
2. Save it as `docs/media/screenshots/<name>.png` (an audit exception for that exact path must be added in the
   same reviewed change — PNGs are blocked by default).
3. Caption it with the commit, branch, switches and date it was captured on. Never present a mock-up as gameplay.

## Style

Match the surrounding code: naming, comment density and idiom. Keep documentation short and link to
`docs/STATUS.md` and task reports instead of duplicating them.
