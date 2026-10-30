# T169: integration readiness

**Not ready to merge: `RSX_VISUAL_PROFILE` does nothing in the game, because it sits in `d3d12_init`, which the D3D12 path doesn't call. It must move to `rsx_d3d12_backend_init` with a behavioural test.** No default may change. Nothing was pushed or merged.

| Item | Value |
|---|---|
| ps3recomp | `agent/t169-visual-fidelity-recovery`, `001a56f`, base `b1eb158` (T165) |
| Root reports | `agent/t169-visual-fidelity-report` |
| Port tree used for the build | `port-t161` |
| Build dir | `build/motorstorm-t169` |
| Exe sha256 | `766c45916524b85ff5343807c6bd467f8ec0e07097aba9fa9ab37b3d17f70491` (not launched) |
| Change | 5 files, +632, no deletions |

**What merging adds:** `RSX_VISUAL_PROFILE` (bit mask over existing switches; an explicit switch wins), `RSX_VISUAL_DIAG` (bounded per-draw log), counters, and a WARP test. Rendering fixes themselves were already there as opt-ins. Off: one branch per draw and a few counter increments.

| Bit | Switch | Default-on readiness |
|---|---|---|
| `0x01` | `RSX_COLOR_XFER=7` | Needs game arm C and a PS3 reference; changes exposure input 8.5× in B3 |
| `0x02` | `RSX_GUEST_SAMPLERS=15` | Needs arm S |
| `0x04` | `RSX_TEX_MIPS` | Needs arm S; +29.6 % texture bytes in B3 |
| `0x08` | `RSX_ZETA_EXACT` | Needs arm F |
| `0x10` | `RSX_RT_WINDOW` | Needs arm F |
| `0x20` | `RSX_RT_FEEDBACK` | Needs arm F; extra copies, untimed |
| `0x40` | `RSX_MSAA` (needs `0x02`) | Needs arm M; memory and copy cost unmeasured |
| `0x80` | `RSX_DEPTH_STATE` | Needs arm D; may expose the `0xBF` velocity misread |
| `0x100` | `RSX_MRT_STATE` | Needs arm F |

**Known gaps:**
- `0xBF` over A8R8G8B8 has no fix. It needs a decompiler decode, and should be done before or with `0x80` if arm D smears.
- Blue rectangle: not reproduced.
- CONTROL0-disabled units are still sampled; effect unknown.
- Two suite failures predate this work (`REGRESSION_VALIDATION.md`).

**Conflicts with T167 and T168:** `libs/video/rsx_d3d12_backend.c` will conflict textually at the include block, the GP macro block, `gs_desc_for`/`gs_set`, the upload counter, the top of `d3d12_init`, and the vdiag record site. These are small and additive.

**Must change when merged with T167:** the `D3DCompile` diagnostic counter isn't thread-safe against T167's background compile. Make it atomic.

**Order:** merge after T165's base. Then run the plan's arms against the merged exe, because the hash above stops applying as soon as anything is merged.

**Windows-specific:** the profile sets unset switches with `_putenv_s` at the top of `d3d12_init`. Backends other than D3D12 don't read it.
