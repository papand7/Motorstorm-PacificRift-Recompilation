# T168: RSX pass reconstruction

Static guest pipeline: T85 (`t85/RSX_PUSH_BUFFER_PIPELINE.md`), verified there by disassembly. Source audit here: ps3recomp `69489f2` plus `800287c`.

```
RenderableProxy::Render 0x482680, kinds 0-5 (T84D)
 -> ExecutePushBuffer 0x50D868: slot = atomic++ [rs+0x24E8]
      chunk = pool[[rs+0x454]&1] + slot<<14; pb[0] = RET; kick SPU job; CALL chunk|2 in main FIFO
 -> SPU renderablejob: writes chunk, JUMP to a new chunk on overflow, RET, atomic++ [rs+0x2560]
 -> frame end 0x50C818: spin until completions == jobs; reset counters; parity++
 -> host walker -> rsx_process_method -> draw callback -> record
 -> render_frame: one command list, one ExecuteCommandLists, then record count = 0
```

## What "pass" means

**An RSX "pass" here is one backend replay (`render_frame`), not a rendering pass and not a game frame.**

| Counter | Counts |
|---|---|
| `[rsx-hb] frames`, `frame_count` | Every `render_frame`, including early replays and offscreen-only batches (T101) |
| `gframe` in `[rsx-frame-perf]` | Guest flips |
| `passes` | Replays within that guest frame |

**The four passes are a record limit, not four renderings.** The backend holds `MAX_DRAWS` = 2,048 records and replays early when full. In the T161 runs CC1 and CC2 (10,801 frame lines), `passes == ceil(records / 2048)` held in all but one line per run. The exceptions are 2 replays with 4 records, around frame 1,920, before the race. The log prints `early replay (records): 2048 records`. Each replay resets the count, so a record is replayed once.

| Scene | Records/frame | Passes |
|---|---|---|
| Light | about 2,004 | 1 |
| Heavy | 6,473-6,803 | 4 |
| One outlier, CC2 frame 5,261 | 12,972 | 7 |

The outlier has about twice a heavy frame's records and fits the same rule. HYPOTHESIS: two guest frames counted as one, because a flip boundary was missed. It isn't a replay: the following frames are normal. Records differ from `draw_calls` (6,791 against 7,090) because adjacent TRIANGLES batches merge into one record.

## Replay mechanisms checked

| Mechanism | Finding | Status |
|---|---|---|
| CALL target run twice | Each return site is entered once in all 21 passes. Two different sites calling one chunk is legal and tested | VERIFIED for captures |
| RET handling | One return slot, like the RSX. A nested CALL's outer RET would go to IO 0 and re-walk the ring: **latent hazard**, pinned in a test. No trace shows it (0 repeats) | Not triggered in captures |
| Replayed chunks, duplicate job completion | 0 identical call sites. Completion only moves a counter; the host never re-dispatches | VERIFIED for captures |
| Push-buffer slot reuse | Slots are atomically allocated and reset only after the completion wait (T85). A reused slot runs only new content (test) | VERIFIED guest code, test |
| Frame parity | A guest pool selector, no walker role. Host parity selects vertex buffer halves only | VERIFIED source |
| Walker exits | The only early exits are unmapped data, a held semaphore (retried without re-dispatch) and flip. `get` advances past each packet | VERIFIED source |
| Resync | `gcm_fifo_resync_why` can land on the **start** of an SPU block, which could re-walk it. **0 resyncs in CC1 and CC2** | Latent, not triggered |
| Ring recycle | Only for titles that overrun; no such log line in CC1 or CC2 | Not triggered |
| Backend replay | `render_frame` has no return before the count reset. One `DrawInstanced` per record in the VP loop | VERIFIED source |
| Early replay ordering | T101 and T97 models, unchanged | Earlier evidence |
| Frame accounting | See above: counters measure different things, and misreading them produces apparent duplication | VERIFIED |

## Captured pass structure (T113, T145 builds)

Passes alternate between two shapes, with targets disjoint apart from `0x07B78D80`:

| Shape | Records | Main targets | Call sites |
|---|---|---|---|
| Shadow and depth | 917-962 | `0x0B030000`, `0x00ED0000`, `0x07B78D80` | 15 |
| Main colour and post | 485-665 | `0x00750000`, `0x0B830000`, `0x07B78D80`, small chain | 6 |

So 21 call sites across the two shapes, matching the 19-21 `0x50D868` calls per frame in T85 (PARTIAL: different builds and frames). Different targets also rule out one pass being a re-run of the other. These builds split frames differently from T161's single light pass, and no capture holds a whole guest frame.
