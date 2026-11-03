# T168: culling opportunities

## Result

**No culling was implemented; `RSX_SAFE_CULL` does not exist.** Nothing was found that can be rejected on reliable evidence, and the game already culls before RSX. The one addition is the read-only `RSX_VIS_DIAG`, which measures what a real run would gain.

## Provably unnecessary draws

Offline over 19 captured frames (T145 A1/B1/D1, T113 F/I, T165 B3, T84d, T72; `vis/cull_offline.json`):

| State-based no-effect class | Records of 11,441 |
|---|---|
| Colour and depth output disabled | 0 |
| Zero vertex count | 0 |
| Empty scissor or viewport | 0 |
| Depth func NEVER | 0 |
| Cull both faces | 0 |

**Geometric visibility cannot be decided from captures.** RSXI records no vertex data, no `first`, and constants only to c63, so frustum, coverage and sample counts need a run.

The only sample data is old `RSXI_OCC` (T84d f004962, first 64 ops, black-race era): 21 of 64 ops drew zero samples, 8,910 of 24,516 verts. This is not representative. A zero-sample draw is also only known after it is drawn, and it can change from one frame to the next.

## Pass shares (coordination with the duplicate workstream)

Each capture alternates two types of replay (D1 f006220 and f006245), so I count one pair as a guest frame. This pairing is my reading, not proven.

| Target | Records | Verts | Note |
|---|---|---|---|
| `0x0B030000` 1024×2048 shadow atlas | 647 (45%) | 263,931 (49%) | depth-only |
| `0x00750000` 1280×720 | 407 | 127,668 | main colour |
| `0x07B78D80` 640×480 | 192 | 70,341 | in both replay types |
| `0x00ED0000` 1280×720 | 138 | 63,840 | depth-only |
| All others | 63 | 11,355 | post chain and small targets |

- Shadow and depth passes are legitimate multipass and must not count as redundant. `RSX_VIS_DIAG` keeps each RT, zeta and viewport as its own pass, so a repeat in another pass is never counted as waste.
- T168's duplicate data agrees: on A1 f006148 there are 0 replayed packets, and its class A includes legitimate multipass.
- Shadow casters outside the main camera are required, so main-camera bounds must never cull them.

## Evaluation

| Candidate | Saving | Safety | Decision |
|---|---|---|---|
| CPU frustum cull on the host | At most the expansion, PSO and command cost of the draws culled. **Unmeasured** | No reliable bounds: the VS runs on the GPU and the guest VP is arbitrary. `pvsjob` has already culled by OBB | Rejected |
| Z-based frustum cull | None usable | Wrong: the backend clamps z, so beyond-far draws can paint | Rejected |
| GPU occlusion | Unmeasured | Not original behaviour (§ reconstruction), asynchronous, risks popping | Rejected |
| LOD change | Unmeasured | Would alter the original distances; forbidden | Rejected |
| Shadow culling | Largest pass, unmeasured | Needs light-space bounds the host lacks | Rejected |
| 80 empty kicks of 96 per frame | PPU only, 0 SPU jobs, unmeasured | Guest code; no reason to change it | No change |
| State-based `RSX_SAFE_CULL` | 0 draws | Safe, but useless | Not built |

## Estimated savings (estimate, not a measurement)

T162 profile. These figures aren't from a culling run.

| Scene | CPU per-draw cost (expansion + PSO + commands) | Frame | If 10% of draws were culled |
|---|---|---|---|
| Light (2,004 draws) | 13 + 1.3 + 2.5 ≈ 17 ms | 47 ms | ≈ 1.7 ms, and probably no FPS gain: this scene is PPU-bound |
| Heavy (~6,960 draws) | 47–49 + 8.2 + 9.5 ≈ 65 ms | 270–298 ms | ≈ 6.5 ms, about 2.3% |

- The 10% is an illustration, not a measured share.
- The GPU saving is unknown: T162 did not measure GPU time.
- In the heavy scene, 190–216 ms goes on recording textures. That is the T157 residency work, and culling can't compete with it.
- T162's draw counts are about 5× the captures' records for a guest frame (6,960 vs 1,447). I did not reconcile the units, so use percentages rather than per-draw figures.

## Run plan (needs authorization; not run)

1. `RSX_VIS_DIAG=30 RSX_VIS_DIAG_DRAWS=2`, in a bounded race run on one fixed scene, on the integrated build. Note the diagnostic's frame GPU wait when reading timing.
2. Read `[r3+0x10]` at `0x5F5628` for the occluder count, and the PVS counters with T84's `vis_trace_v2.cfg`.
3. Decide from the results:
   - Under 5% of main-pass draws classed `outside` or `empty`: close culling for good.
   - Above that: find out why `pvsjob` passed them first, since a mismatch with its frustum would be a bug to fix, not a reason to add a cull.
