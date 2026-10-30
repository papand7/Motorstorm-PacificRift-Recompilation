# T169: integration readiness

**Not ready to merge as a default set. The opt-in plumbing works in the game, but `RSX_DEPTH_STATE=1` damages vehicles (`REMAINING_VISUAL_DEFECTS.md`), and there's no PS3 reference.** No default changed. Nothing was pushed or merged.

| Item | Value |
|---|---|
| ps3recomp | `agent/t169-visual-fidelity-recovery`, `774c81d`, base `b1eb158` (T165) |
| Root reports | `agent/t169-visual-fidelity-report` |
| Port tree used for the build | `port-t161` |
| Build dir | `build/motorstorm-t169` |
| Exe sha256 | `02b5c83cbb15d61f9cfea46f50868ac4c4c95593fb60976cc862ccf010a23a6f` (launched: D2, F2) |
| Build | Release, clang-cl 23.1.3, `/O2 /Ob2 /DNDEBUG`, `PS3RECOMP_RSX_VULKAN=OFF` |

**What merging adds:** `RSX_VISUAL_PROFILE` (bit mask over existing switches; an explicit switch wins), `RSX_VISUAL_DIAG` (bounded per-draw log), counters, and a WARP test. Rendering fixes themselves were already there as opt-ins. Off: one branch per draw and a few counter increments.

| Bit | Switch | Default-on readiness |
|---|---|---|
| `0x01` | `RSX_COLOR_XFER=7` | Active in F2. Needs a single-switch run and a PS3 reference |
| `0x02` | `RSX_GUEST_SAMPLERS=15` | Active in F2. Needs a single-switch run |
| `0x04` | `RSX_TEX_MIPS` | Active in F2. Near sand looks soft; check |
| `0x08` | `RSX_ZETA_EXACT` | Active in F2. Effect not separable |
| `0x10` | `RSX_RT_WINDOW` | Active in F2. Effect not separable |
| `0x20` | `RSX_RT_FEEDBACK` | Active in F2. Effect not separable |
| `0x40` | `RSX_MSAA` (needs `0x02`) | Not tested in game |
| `0x80` | `RSX_DEPTH_STATE` | **Not ready: vehicle regression** |
| `0x100` | `RSX_MRT_STATE` | Active in F2. Effect not separable |

**Known gaps:**
- `0xBF` over A8R8G8B8 has no fix. It needs a decompiler decode, and should be done before or with `0x80` if arm D smears.
- Blue rectangle: not reproduced.
- CONTROL0-disabled units are still sampled; effect unknown.
- Two suite failures predate this work, and `test_spurs_kick_wake` now fails on this machine at both commits (`REGRESSION_VALIDATION.md`).

**Conflicts with T167 and T168:** `libs/video/rsx_d3d12_backend.c` will conflict textually at the include block, the GP macro block, `gs_desc_for`/`gs_set`, the upload counter, the top of `d3d12_init`, and the vdiag record site. These are small and additive.

**Must change when merged with T167:** the `D3DCompile` diagnostic counter isn't thread-safe against T167's background compile. Make it atomic.

**Order:** merge after T165's base. Then run the plan's arms against the merged exe, because the hash above stops applying as soon as anything is merged.

**Windows-specific:** the profile sets unset switches with `_putenv_s` at the top of `rsx_d3d12_backend_init`. Backends other than D3D12 don't read it.
