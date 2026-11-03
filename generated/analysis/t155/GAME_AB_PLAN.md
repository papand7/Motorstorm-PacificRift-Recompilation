# T155: proposed game A/B for `RSX_TEX_SLOTS` (NOT RUN; needs explicit authorisation for 4 launches)

## Arms (one exe, one switch)

| Item | Value |
|---|---|
| exe (both arms) | `build/motorstorm-t155` at `c1512fb`, `MSPR_WWS_AOT=ON`, sha256 `d8483b4a3ed18907b232ca2e8b18a648980a6f53f860241e5a6ffb6559ef1c6c`, already pinned as `ab/exe_f` (`run_t155ab.py prepare f`) |
| common environment | exactly T154 arm BA: T153 preset (`PS3_TEX_SNAPSHOT_EPOCH`, `RSX_VP_COMPACT`, `RSX_SHADER_CACHE`, `RSX_SRV_REUSE`, `RSX_BIND_DEDUP`, `PS3_SPURS_EVENT_SCHED`) + T146 defaults + `PS3_TEX_SNAPSHOT_WWATCH=1` + `PS3_SPU_WWS_STATS=1000:3214:1320` + `PS3_SPU_WWS_AOT=1` + `PS3_CRITICAL_PATH_TRACE=175:65` + `RSX_TEXREC_STATS=1` |
| A | `RSX_TEX_SLOTS` unset (96 slots: the T154 behaviour; the same exe also checks that the default is unchanged against T154 BA and the T155 diagnostic) |
| B | A + `RSX_TEX_SLOTS=1024` |
| order | `ab/seq_t155ab.sh`: Ar1, Br1, Ar2, Br2. Sequential, nothing else heavy on the host, fresh hash-manifested HDD copies, stop at race entry + 90 s |
| runner | `ab/run_t155ab.py` (from `tools/make_ab_t155.py`; derived from T154's runner, same route, controller and race) |

The one-exe design isolates the switch. A second exe (T154 `e8386a74`) would also differ by the counters and the SRV-region offsets.

## Measurements (all by guest race-frame index, never host-time windows)

- `t154/tools/phase_match_t154.py`:
  - light (race frames 40–499) and heavy (600 to the common end) FPS;
  - RSX wall, drain, expand, record, and idle per guest frame;
  - draw count.
- `t155/tools/ana_texrec_t155.py`, per guest frame and per pass:
  - texture lookups, slots in use (`bound`), binds with no slot;
  - evictions, refetches, re-creations, SRVs, decode MB;
  - create / decode / copy / total µs.
- `t154/tools/phase_sites_t154.py`: Wws spin `0x50C818`, Havok wait `0x30B710`, ref throttle, Wws job ms per frame and per module.
- Frame dumps (`CELLMARK_DUMP`): the first race frames, which are light-scene only.

## Pass criteria

- 4 valid runs (race reached, no crash, hang or validation error).
- B: `noslot` 0 and `bound` below 1024 in the heavy scene. B's heavy-scene texture ms well below A's (A expected about 200 ms).
- Light-scene FPS of B within run-to-run variation of A. Draw counts per race frame equal across arms.
- Visuals: B may legitimately differ from A only where A dropped textures.

## Not covered

- The dumps do not reach the heavy scene, and the controller gives no input.
- Heavy-scene visuals beyond the counters need a separate authorised capture (RSXI at race entry + 40 s).
