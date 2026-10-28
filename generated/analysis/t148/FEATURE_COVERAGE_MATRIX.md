# T148 — feature coverage matrix (miscellaneous features)

Branch `integration/t148-misc-features` (worktree `ps3recomp-t148-misc-integration`), base T146 `80fe5de`.
"Runtime-unverified" = in the built exe (`build/motorstorm-t148`), no game run (not authorised).
Full suite: PASS 144 / SKIP 43 / FAIL 5 (2 RPCN env BLOCK, 2 also failing on T146, 1 load-flaky; see HISTORICAL_FEATURE_INTEGRATION.md 5).
Game import evidence: `generated/analysis/EBOOT.imports.json` (NIDs resolved by name hash).

| Group | Feature | Game imports it | Source | Status |
|---|---|---|---|---|
| A startup | boot / intro / frontend progression fixes (cellFont, LFQueue, NetCtl, GCM) | yes | earlier tasks | **Already present** (base) |
| A startup | early-boot workarounds review | — | — | **Not implemented** (needs game runs to prove removal safe) |
| B input | cellPad SDK packet lengths, sensor-mode refusal, analog triggers (garage-input-audit) | cellPadInit/GetData/SetActDirect/SetPressMode/SetSensorMode/GetCapabilityInfo | garage-input-audit | **Already present** (patch-id in base) |
| B input | vibration (SetActDirect) | yes | base | **Already present**; runtime-unverified |
| C audio | initial port gain, native audio regressions (T118) | cellAudio ×11 | T146 `1aeb09e` | **Already present** (base) |
| D save | cellSaveDataListAutoSave | yes (NID 0x4DD03A4E) | misc-hle `c9abc88` → `f86ec3b` | **Integrated and tested**; runtime-unverified |
| D save | NULL buffer + zero size = empty file op | yes (ListAuto*/Auto*2) | T24 `316747e` → `3eccd28` | **Integrated and tested**; runtime-unverified |
| D fs | cellFsUnlink/Rmdir real delete under writable roots, contained | yes | misc-hle `b3f9812`,`7b6f9f0`,`5b30c3a` | **Integrated and tested**; runtime-unverified |
| D font | cellFontInitLibraryFreeTypeWithRevision, cellFontEndLibrary | yes | misc-hle `b6467d1` → `b21c73c` | **Integrated and tested**; runtime-unverified |
| E sync | sys_lwcond real waiter queue | yes (create/destroy/wait/signal/signal_all) | T24 `2a8522b` → `084bba9` + `e69bafe` | **Integrated and tested, opt-in** (`PS3_LWCOND_QUEUE=1`; default = old poll model) |
| E timer | precise short usleep | yes | T24 `3e9bb93` | **Superseded** by T121 `PS3_USLEEP_SPIN=2` (base) |
| E HLE | NID / return-address dispatch cache | — | T24 `73d6041` | **Not integrated** — performance → T146 handoff |
| E PPU | constant-initialised PPU_THREAD_LOCAL | — | T24 `9da3454` | **Not integrated** — needs re-lift; build/perf → T146 handoff |
| E lifter | two-level switch base skips frame restores | — | T24 `e92508f` | **Not integrated** — lifter change needs re-lift + PPU conformance → T146 |
| E SPU/SPURS | PUTLLC lost update, GETLLAR backoff, EF DMA wake, taskset park, stop 0x110, workload Shutdown lifecycle | — | t28-event-queue / t24-spu | **Not integrated** — T146 scope (handoff list) |
| F net | sceNp RequestTicket2/GetTicket deferred GOT_TICKET | yes | networking-audit `f578741` → `3be1431` | **Integrated and tested**; offline default (no transport) |
| F net | np_auth state, RPCN codec, account config | (RPCN) | `a4945a9` → `e6fcc15` | **Integrated and tested** (offline) |
| F net | RPCN Schannel transport + mock server | (RPCN) | `539450d` → `e22ec5a` | **Integrated, test BLOCKED** (python `cryptography` missing; not installed) |
| F net | rpcn_check, np_ticket_verify | (RPCN) | `13a4e02` → `2b32fa6` | **Integrated, test BLOCKED** (same; live run needs authorisation) |
| F net | matchmaking / lobby (sceNp2 Matching2) | sceNpMatching2Init2 (+25 sceNp2) | — | **Not implemented** |
| G tools | RSXI replay inventory, lossless blobs, capture contract | — | t32/t53 `3316d53`,`dc1780f`,`a311ab9` | **Integrated and tested** |
| G tools | msre RE workbench (5 commits) | — | t36..t53 | **Integrated and tested** |
| G tools | upstream source compare; PRX import boundary test | — | t27 `92cdae7`,`65b20e8` | **Integrated and tested** |
| G tools | PS3 API coverage audit (docs + tools) | — | ps3-api-audit `6bae99b` + `695aaeb` path fix | **Integrated and tested** |
| G tools | offline graphics mod framework (msmods) | — | T111 `d2a65f9` → `373040c` | **Integrated and tested** (57/57 with native shader_tool) |
| G tools | PS3_FTRACE_SPURS spans | — | t25 `991337d` | **Superseded** by T134 PS3_FT_SPURS_PICK/PM |
| G tools | PS3_FTRACE_SPUJOB, PS3_FTRACE_ARM | — | t33/t70 | **Already present** (base) |
| G tools | SPU_JOBCAP job capture | — | perf-intro `7ce5c57` | **Not integrated** — hooks SPU hot paths → T146 handoff |
| G tools | RSX ftrace / tex-snapshot bench / VP strip / VPC trace | — | t25/t18/perf-regression | **Not integrated** — renderer → T146/T147 handoff (conflict with newer code) |
| H build | keep mtimes of byte-identical regenerated SPU files | — | t24-build `2778d7e` → `f9bac03` | **Integrated and tested** |
| H build | suppress warnings on generated SPU sources | — | t24-build `1a415e6` | **Incomplete** — conflicts with current cmake/PS3RecompSPU.cmake; not ported |
| H build | stale sibling-layout path in API audit | — | — | **Integrated and tested** (`695aaeb`) |
| — | WWS AOT exe variant | — | T109 | **Blocked** (needs `port-t106aot`, T146) |
| — | T144 SPURS lane handoff | — | `b00e999` | **Not integrated** — T146 scope; opt-in, net synthetic regression |
| — | Twisted Metal / GT5P / other-title work (tags, stash, t24-infamous-ports) | — | — | **Not applicable** (other titles) |

## Recovered but not integrated (with reasons)

| Commit(s) | Branch | Reason |
|---|---|---|
| `73d6041` HLE dispatch cache | recover/t24-ppu | performance → T146 |
| `9da3454` PPU_THREAD_LOCAL constinit | recover/t24-ppu | needs re-lift → T146 |
| `e92508f` lifter switch base | recover/t24-ppu | lifter change, re-lift + conformance → T146 |
| `23ae052` `69ed8fe` `f04abfb` `24e67f0` `75f2b18` `3493cb6` `11c76d8` | agent/t28-event-queue | SPU/SPURS correctness → T146 (two conflict) |
| `7ce5c57` SPU_JOBCAP | agent/perf-intro | SPU hot-path hooks → T146 |
| `9069985` `eea8f42` `aec8c95` `fab7b2c` `d6d4576` `3d19969` `3b38721` `1595ee4` `3e4696d` | t25-perf / perf-integration-307b08a | renderer/PPU perf, conflicts with newer code → T146 |
| `8f7ac89` VPC trace | agent/t18-c38-trace | renderer diagnostics → T147 |
| `d4c0f78` `0cb58e9` `b76b9c7` (+ t24-render/t61 copies) | t28/t61/t24-render | D3D12 vtable-path visuals → T147 (base has later depth/stencil/sampler work) |
| `1a415e6` cmake SPU warnings | agent/t24-build | conflicts; low value |
| `bf5f54b` `e8c795f` ShutdownJobChain, job index in data2 | stash/tag only | SPURS → T146; reachable via stash, not a branch |
| `8d3eddb` tools/t53 | agent/t53-text-root-cause | task-specific one-off |
