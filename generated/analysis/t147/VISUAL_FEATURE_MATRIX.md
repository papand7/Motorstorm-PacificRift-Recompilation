# T147 visual feature matrix

Branch `integration/t147-unified-rsx-visuals` (worktree `ps3recomp-t147-visual-integration`) is based on T145 `f7f9366`.

"Runtime-unverified" means the feature has never been checked in the running game. T113 is the only visual task with in-game runs.

| Task | Correction | Switch (default) | Source commit(s) | In T147 as | Status |
|---|---|---|---|---|---|
| T103 | DPI awareness; RSXI sampler words | on (`PS3_DPI_UNAWARE=1` opts out) | `c2e9eec`, `26f262e` | in base (via T110) | Integrated |
| T107 | `SET_SHADER_PACKER` and colour-transfer report | diagnostic | `ec5cdb3` | equivalent in base (`rsx_color_xfer.h`, `rsx_commands`) | Superseded by T110 |
| T108 | race present probe; RGBA32F classes | diagnostic | `6b1a7e4` | in base | Integrated |
| T110 | guest samplers | `RSX_GUEST_SAMPLERS=15` (off) | `3c1eb4d`…`e3b961d` | in base | Integrated, runtime-unverified |
| T110 | colour transfers (sRGB, gamma, expand) | `RSX_COLOR_XFER=7` (off) | same | in base | Integrated, runtime-unverified (never run in game) |
| T110 | attr0 const, RT pool GF | `RSX_ATTR0_CONST`, `RSX_RTPOOL_GF` (off) | same | in base | Integrated (no visible effect in T113's in-game runs) |
| T113 | FP read through END (`fp_span`) | on (`RSX_FP_SPAN=0` reverts) | `2562ba8` | in base | Integrated; verified in game by T113 (agent-viewed) |
| T113 | RT write-back / exposure readback | on (`RSX_RT_READBACK=0` opts out) | `19d6b6d`…`2562ba8` | in base | Integrated; verified in game by T113 (agent-viewed) |
| T115 | guest mip chains | `RSX_TEX_MIPS=1` (off) | `17b16cb` → `4a74174` | in base (T133 cherry-pick) | Integrated, runtime-unverified |
| T115B | exact texture cache, CONTROL3 row pitch | `RSX_TEX_CACHE=1/2` (off) | `65d2695` | `f3561cd` (clean pick) | Integrated, runtime-unverified |
| T116 | shader/PSO cache | `RSX_SHADER_CACHE=0..3` (off) | `c8d8a0a`, `30b817b` | not picked | Blocked here: a performance feature handed to T146. It conflicts in the backend, and its key must include the T120, T133, T115, T137 and T141 state |
| T117 | decompiler refuses a program with no END | unconditional | `fd97181` (decompiler half) | `f986282` | Integrated |
| T117 | 16 KiB FP window in the backend | unconditional | `fd97181` (backend half) | not picked | Superseded by T113 `fp_span()`, which reads through END up to 64 KiB at every FP walk |
| T119 | compact VP; VS memo | `RSX_VP_COMPACT=1` (off) | `693169a` | not picked | Not applicable here (performance; T146). Merges cleanly onto T147 |
| T120 | RT windows | `RSX_RT_WINDOW=1` (off) | `235b3e6`, `169e618` | in base | Integrated, runtime-unverified |
| T120 | guest depth/stencil state | `RSX_DEPTH_STATE=1` (off) | `169e618` | in base | Integrated, runtime-unverified |
| T122 | submission; texture snapshot epoch | `PS3_TEX_SNAPSHOT_EPOCH=1` (off) | `2b639c2` | not picked | Not applicable here (T146). Merges cleanly onto T147 |
| T133 | FP precision clamps | `RSX_FP_PRECISION=1` (off) | `816a4af` | in base | Integrated, runtime-unverified |
| T137 | 2× MSAA (antialias-3) | `RSX_MSAA=1` (off) | `5d65601`, `f6f9a48`, `876a403` | in base | Integrated, runtime-unverified |
| T141 | RT feedback, exact zeta, MRT state | `RSX_RT_FEEDBACK`, `RSX_ZETA_EXACT`, `RSX_MRT_STATE` (off) | `7b5fcda`…`07b453f` | in base | Integrated, runtime-unverified |
| T142 | only fetched units claim an RT window | under `RSX_RT_WINDOW`/`RSX_MSAA` | `a5171d6`, `e9f3237` | in base | Integrated, runtime-unverified |
| T143 | SRV reuse, bind dedup | `RSX_SRV_REUSE`, `RSX_BIND_DEDUP` (off) | `e2f9435`, `efae357` | not picked | Not applicable here (performance; T146). Conflicts in the backend |
| T144 | exact guest stencil | `RSX_STENCIL_EXACT=1` (off) | `121879f`, `c31aa83` | `505804e`, `c0ff81f` (clean) | Integrated, runtime-unverified |
| T145 | `SET_SHADER_WINDOW` WPOS origin | `RSX_SHADER_WINDOW=1` (off) | `49fc83f`, `1dff0eb`, `f7f9366` | base | Integrated, runtime-unverified |
| T113 × T117 | `test_fp_span` pins the refusal under the legacy window | — | — | `d76e08e` | Integrated (conflict resolution) |
