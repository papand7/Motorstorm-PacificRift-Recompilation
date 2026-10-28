# RSX blend state on the garage loading screen (offline, 2026-10-23)

Run `generated/runs/20261023-150148-garage-render/` (exe `8baed049…`). RSXI frames 1361, 1371, 1381. Source: ps3recomp-int `c874771`. MotorStorm was not launched.

## What `0x0122418B` is

It is **not an RSX register**. It is the D3D12 pipeline key that the backend packs from three RSX methods (`rsx_blend_key`, `libs/video/rsx_d3d12_backend.c:1946`).

| RSX method | Offset | Content (decoded in `rsx_commands.c:529–547`) |
|---|---|---|
| `NV4097_SET_BLEND_ENABLE` | `0x310` | enable |
| `NV4097_SET_BLEND_FUNC_SFACTOR` | `0x314` | `(alpha << 16) \| rgb`, GL factor enums |
| `NV4097_SET_BLEND_FUNC_DFACTOR` | `0x318` | same layout |
| `NV4097_SET_BLEND_COLOR` | `0x31C` | **not decoded**; the backend never calls `OMSetBlendFactor` |
| `NV4097_SET_BLEND_EQUATION` | `0x320` | `(alpha << 16) \| rgb`, GL equation enums |

Register offsets: `rsx_commands.h:177–181`. The key layout is bit 0 enable, [5:1] colour source, [10:6] colour destination, [15:11] alpha source, [20:16] alpha destination, [23:21] colour op, [26:24] alpha op.

## Decoded (VERIFIED: key arithmetic, plus `tools/test_d3d12_blend_state.py`)

| Field | Value |
|---|---|
| Blend enable | on |
| Colour source / destination / equation | `SRC_ALPHA` / `INV_SRC_ALPHA` / `ADD` |
| Alpha source / destination / equation | `INV_DEST_ALPHA` / `ONE` / `ADD` |
| Blend constant | not used by this state (and not implemented) |
| Colour write mask | `cmask=15`: R, G, B and A written |
| Render target | the display buffer (`rt=0`), guest format `0x148` (colour A8R8G8B8); native `R8G8B8A8_UNORM` back buffer |

**Guest words that produce it:**
- source = `(0x0305 or 0x0307) << 16 | 0x0302`;
- destination = `0x0001 << 16 | 0x0303`;
- equation = `ADD` (`0x8006`) or unset, both halves.

The exact words were not logged. Two more caveats:
- An unrecognised factor also maps to `ONE`, and an unrecognised equation to `ADD`.
- `BLENDDBG=1` prints the raw words (32 distinct at most). It is in the next run.

**Meaning:** standard straight-alpha blending for colour. The alpha channel accumulates coverage (`dstA' = srcA·(1−dstA) + dstA`). Colour uses only the *source* alpha, so the destination alpha has no effect on what is seen.

## D3D12 against RSX

`tools/test_d3d12_blend_state.py` lifts `gl_blend_factor_d3d`, `gl_blend_op_d3d`, `rsx_blend_key` and the PSO blend fill (`:2440`) into a harness: 12 harness checks plus 5 source and build checks PASS (WSL). It confirms:

| Risk | Result |
|---|---|
| Factor mapping | correct for every GL factor used here |
| Equations | colour and alpha are translated independently (e.g. `MAX` for colour, `SUBTRACT` for alpha) |
| Colour/alpha confusion | colour factors in the alpha slot become their alpha forms, as D3D12 requires |
| Enable handling | off gives key 0 and a pass-through `ONE`/`ZERO`/`ADD`; off → on → off leaves nothing behind |
| Stale pipeline state | each draw keys its pipeline on the state when it was recorded; three record paths, and the replay uses `dr->blend_key` |
| Write masks | reach every bound target; a guest mask of 0 is honoured |
| Premultiplied vs straight alpha | the state is straight alpha, and so is the translation |
| Target format | 8-bit UNORM on both sides |

**No blend-translation defect was found** for this state.

**Gaps (not involved here):**
- `SET_BLEND_COLOR` is not implemented. `CONSTANT_ALPHA` is approximated by the blend factor.
- Unknown factors and equations silently become `ONE` / `ADD`.

## Related fix (VERIFIED by test, effect on this title UNKNOWN)

The D3D12 `vp_get_vs` decompiled each vertex program from its start slot without calling `rsx_vp_set_branch_base`. A branching program at a non-zero slot therefore took wrong branch targets.

- Fixed in `c874771`.
- Test: `tools/test_vp_branch_base.py`. The source check fails on `dadfcaa`.
- Whether the loading-screen vertex program branches is unknown. The next capture dumps it.
