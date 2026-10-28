# FIOS cache behaviour (offline, 2026-10-23)

Live cache: `generated/hdd1/cache/BLES00000/fios/{cache.idx,cache.dat}`. Pre-run copy:
`generated/cache-snapshots/20261023-131453/` (hash-verified, read-only). Nothing was deleted,
restored or replaced.

## Findings

| Question | Answer | Label |
|---|---|---|
| Is 480 MB → 30 MB expected? | Yes. Every boot the runtime clears the cache: `SysCacheMount` (a new id in this process → cleared), then the game calls `SysCacheClear` (stdout lines 105–110 of the skip run). The game then rebuilds it from empty, so its size tracks how far the run got: 480 MB after the 139 s full intro, 30 MB after the 35 s skip run. | VERIFIED (log + `cellSysutil.c`) |
| Recreated or truncated? | Recreated. Clear deletes the directory's contents (`syscache_clear_host`, commit `d51122c`); FIOS reopens and recreates both files. | VERIFIED |
| Does the intro skip affect it? | Only through run length. Mount/Clear happen at boot, long before the intro. | VERIFIED |
| Do archive reads populate it? | Seeks on fd 4 (`cache.dat`) and fd 3 (`cache.idx`) are interleaved with archive reads (lines 1342–1351). The writes are not logged (`cellFsWrite` has no log), so what is written is not shown. | PARTIAL |
| Are metadata and sizes consistent? | Both files have the same layout: `cache.idx` is fixed at 1,043,456 B with its first 512 B zero (old: 9,998 non-zero bytes, live: 616); `cache.dat` = 512 + N × 65,536 (old: N = 7,328; live: N = 464), whole 64 KiB blocks. | VERIFIED (structure only; the format is not decoded) |
| Does a cold cache change lookups? | Every run since `d51122c` is cold, including the successful `av2`, `beat`, `fcw-audio` and skip runs. A warm cache cannot occur with the current semantics (no cross-boot retention). The pre-fix warm-cache reopen loop (`av`, 2026-10-22) is gone. | VERIFIED (runs) |

The snapshot is not needed for the next boot: the game clears the cache anyway. It is kept as
evidence and was not deleted.
- Each `--snapshot-cache` run adds ~0.5 GB under `generated/cache-snapshots/`.
- Current snapshots: `20261023-131453/` (481.7 MB).

**Not implemented (unchanged):** RPCS3-style cross-boot retention. On a PS3 the cache usually
survives. A retained cache would only change load speed, not which data is loaded (HYPOTHESIS).
