# T165: material diagnostics

## `RSX_VEHICLE_DIAG` (ps3recomp `agent/t165-vehicle-render-fix`)

RSXI already records programs, textures, samplers, depth, blend, cull and constants, and `RSXI_VP_CONSTS=512` lifts its constant limit. So the new switch adds only what RSXI lacks: vertex attribute formats and constant attribute registers.

| Switch | Effect |
|---|---|
| `RSX_VEHICLE_DIAG=1` | enable; only the exact value 1 |
| `RSX_VEHICLE_DIAG_GO=<path>` | start once the file exists (polled every 256 draws) |
| `RSX_VEHICLE_DIAG_MAX=<n>` | line limit, default 20,000, at most 200,000 |
| `RSX_VEHICLE_DIAG_FP=<hex>` | only this program |

Line: `[veh-diag] gf= fp= prim= count= idx= rt= alpha=en,func,ref blend= depth=en,func,mask cull=en,face attrs=<attr:type:size:stride:freq/regW | attr:reg:x,y,z,w>`

Read-only (const state). Off, the cost is one branch per recorded draw.

## Tools (`tools/`)

| Tool | Purpose |
|---|---|
| `material_census_t165.py` | RSXI census: transfers, blend, gamma, expansion, texture source |
| `null_census_t165.py` | null-SRV units against what the program samples |
| `lit_transfer_model_t165.py` | RSX vs default transfer table |

## Census results

| Capture | Draws | Transfers | Texture sources |
|---|---|---|---|
| Race, T145 A1 (corrected: the first census dropped draws with `-nan`) | 1,446 | `host_xfer=none`; `srgb_output` on 608; gamma 7 on units 0/2/14/15; expansion 0 | upload 12,286, rt_exact 5,004, null 930, zeta 574, zeta_as_color 4 |
| Garage, `runs/20261025-102805-garage-capture-probe` | 2,494 | capture predates the transfer fields | upload 21,709, rt_exact 7,203, zeta 1,240, null 1,058, zeta_as_color 14 |

The race light constants quoted in the root-cause report come from the same capture's draw op 423 (VP c40, c41).
