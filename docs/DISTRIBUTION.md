# Public source distribution policy

Only independently written source, configuration, scripts, documentation, and licensed dependencies may be published. The original ISO, game assets, firmware modules, decrypted ELFs, generated PPU/SPU output, objects, and linked game executable remain local. This includes `libsre.sprx` and any lifted output from it. Public SPURS compatibility code must be independently implemented from documented behavior and legally usable references.

Keep user inputs in `original/` or `private/`, analysis and lifted code in `generated/`, and binaries in `build/`. These paths are Git-ignored. The build scripts read local user inputs and regenerate their outputs locally. Do not send proprietary inputs or outputs to public CI, cloud builds, third-party APIs, or release artifacts.

The launcher's "Decrypt automatically" (`docs/LAUNCHER.md`) downloads the official RPCS3 Windows build (GPL-2.0) on the player's PC, at the player's request, into a temporary folder and deletes it after one decryption. RPCS3 is not redistributed: never commit, bundle or upload its binaries, and never stage the `EBOOT.elf` it produces (`MotorStorm\decrypted\`, a launcher data folder, is never part of the repository).

RPCS3's installed firmware under `build/rpcs3/dev_flash/`, its PPU cache under `build/rpcs3/cache/`, and local PPU-debug dumps under `build/rpcs3/ppu_progs/` are private `build/` artifacts. `tools/inspect_local_spurs_firmware.py` reads these paths and writes only a local metadata inventory in ignored `generated/firmware_analysis/`. Never stage that inventory, firmware dump, cache objects, disassembly, or traces from a diagnostic run. Public compatibility code must describe independently verified behavior; do not copy or translate the firmware routine.

Private builds channel: the full launcher (with its source snapshot of the port, the runtime and the lifting recipe) is published only as pre-releases of the private repository `papand7/motorstorm-private-builds`, never in this public repository or its releases. Its snapshot is made by the normal `source_bundles.js --with-pcmenu` and passes the same `audit_public.py --tree` and key scan; it is made without `--allow-runtime-keys` (the runtime reads EDAT/SDAT keys at run time from an operator-supplied `PS3_KEYS_FILE` and its tree holds none) and holds no game files, firmware, decrypted ELFs or lifted code: players supply their own disc and EBOOT. The launcher's Private update channel reads that repository with the player's own GitHub token, stored only encrypted by Windows (`docs/LAUNCHER.md`); no token is ever committed, logged or written in plain text.

Before the first commit in a newly initialized public repository, configure the hook:

```powershell
git config core.hooksPath tools/hooks
```

The hook runs `tools/audit_public.py --staged` against staged blob contents, including files force-added past `.gitignore`. To audit a release staging directory before packaging or uploading it:

```powershell
python tools/audit_public.py --tree path/to/public-source-staging
```

`python tools/stage_public_source.py build/public-source-<version>` copies allowlisted source paths into a new local staging directory and audits every copied file. It excludes upstream tests, scratch outputs, packaging media, and PDF/image files, which are not needed for the local build and may have separate provenance. The release audit fails on private paths, executable and asset extensions, known game-input hashes, binary signatures, lifted-code signatures, and symbolic links. Review the staged file list and third-party licenses as well; automated scanning cannot prove copyright ownership. Never audit the live workspace as a release tree, since it intentionally contains private local inputs. Do not release precompiled binaries containing original game code.

If `ps3recomp/` is included in a source release, preserve its MIT license and audit its full staged contents. Changes to ps3recomp's runtime must be independent compatibility implementations; do not publish translated Sony firmware routines.

Copyright ownership, third-party license obligations, local decryption legality and anti-circumvention rules require jurisdiction-specific review before any public release. The local-generation model and automated audit reduce accidental redistribution; neither establishes legal clearance.

- The local RPCS3 LFQueue reference harness, firmware dump, PPU/SPU caches, guest snapshots, and copied disc descriptor live only in ignored `generated/` and `build/` paths. They are diagnostic inputs and are excluded from source staging and release artifacts.

The independently authored PS3 reference fixture sources under `tools/` may be distributed as source, subject to the dependency licenses in `THIRD_PARTY_LICENSES.md`. Their locally compiled PPU/SPU ELF and SELF files, private WSL toolchain outputs, firmware-backed logs, and guest snapshots stay outside public release staging. The fixture uses original firmware installed by the user at runtime; no Sony implementation is linked into public project source.
