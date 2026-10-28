# Garage resource loading: analysis (offline, 2026-10-23)

No MotorStorm launch. Evidence: run `generated/runs/20261023-131454-skip-intro/` (exe
`2c1809c6…`, `FS_CALLER=1`), its watcher timeline `generated/introskip/skip_timeline.txt`, the
original `MS2.PSARC` (read-only), and the runtime source. Member map: `PSARC_GARAGE_RESOURCE_MAP.md`.

## Result

**The first garage request is a loose-file probe that fails as it should.** The game was already
reading garage data from the archive before that probe, and it kept reading archive members after
it. No defect was found in the loading path. One diagnostic defect was found and fixed: read
positions past 2 GiB were logged as -1.

## Request timeline (stderr line numbers; s = seconds since stderr.log appeared)

| Line | s | Event | Member (archive TOC) |
|---|---|---|---|
| 1223 | 30.726 | `[fs] close fd=6`: the intro movie closes after the Cross press | — |
| 1234 | | lseek fd 5 → 2,536,802,865 | `/gui/loadscreen-garage.gui` +0 |
| 1275 | | lseek fd 5 → 35,455,985 | `/gui/textureresources/guiloading.rpk` +0 |
| 1342–1351 | | seeks on fd 5, fd 4 (`cache.dat`) and fd 3 (`cache.idx`) | FIOS cache traffic |
| 1353 | | open FAIL `data/events/default.race` | not in the archive |
| 1355–1357 | | lseeks | `/ParticleEffects.pck`, `/ParticleEffectShaders.rpk` |
| 1358 | | lseek fd 5 → 1,917,461,852 | **`/worlds/track_garage.rpk` +0** |
| 1366, 1368 | | lseeks | `/env/Track0a_Garage_Sky1_driver.rpk` +0 and +4,793,637 |
| **1371** | **34.567** | **open FAIL `/dev_bdvd/PS3_GAME/USRDIR/worlds/track_garage_ain_objects.rpk`** | not in the archive |
| 1372–1374 | | open FAIL `…_cps_objects.rpk`, `…_gan_objects.rpk`, `track_garage.jump` | not in the archive |
| 1375–1376 | | lseeks | `/scripts/screenrush.xml`, `/post.rpk` |
| 1377–1380 | | open FAIL `track_garage.{bin,spvs,gvl}`, `data/events/default.gags` | not in the archive |
| 1381–1386 | | lseeks (last lines; the runner stopped 0.01 s after line 1371) | `/data/ai/assistedram.xml`, `/audio/VSBSamplesDB.smp`, `/audio/vsb.xml`, `/audio/Collisions.aes/.aeb` |

The first garage request:

| Field | Value |
|---|---|
| Resource | `track_garage_ain_objects.rpk` |
| Guest path | `/dev_bdvd/PS3_GAME/USRDIR/worlds/track_garage_ain_objects.rpk` |
| Host path | `original/game/PS3_GAME/USRDIR/worlds/track_garage_ain_objects.rpk` (does not exist) |
| API | `cellFsOpen`, flags 0x0 (`O_RDONLY`) |
| Kind | loose-file probe. The disc tree has no `worlds/` directory and the archive has no such member. |
| Return | `CELL_FS_ENOENT` (0x80010006). This is the only failure path in `cellFsOpen` for a missing file (`runtime/ppu/ppu_fs.cpp`). The return value itself was not logged. |
| Guest caller / thread | not logged by this build (FAIL lines carried no caller). Fixed in `2f6c7cf`. Every logged open, seek and close comes from one wrapper, `func_00667558`, the game's FIOS layer. |

## How a resource is found (VERIFIED from code and logs unless marked)

1. **Path mapping (runtime):** `host_path()` maps `/dev_bdvd/...` to `PS3_VFS_ROOT` (`original/game`)
   and `/dev_hdd1` to `PS3_HDD1_ROOT` (`generated/hdd1`). Failed opens return ENOENT.
2. **Loose file or archive (guest):** the runtime has no PSARC code (`psarc` appears nowhere in
   `ps3recomp-int/runtime`, `libs` or `include`). The game itself opens `/dev_bdvd/PS3_GAME/USRDIR/ms2.psarc`
   once (fd 5, through `func_00667558`) and reads its TOC.
   - **SUPPORTED HYPOTHESIS:** for some files it probes the loose path first, then the archive
     (the STATUS 2026-10-21 run shows the same pattern).
3. **Member lookup (guest):** every seek on fd 5 lands exactly at the start (+0) of a member,
   except for continuation seeks within a member. This is lifted guest code, and it works.
4. **Descriptors (runtime):** `fd_alloc_file` hands out the lowest free slot:
   - 3 = `cache.idx`;
   - 4 = `cache.dat`;
   - 5 = `ms2.psarc` (fd 5 in all six replayed runs);
   - 6 = the intro.
5. **Offsets and reads (runtime):** `cellFsLseek` uses `_fseeki64`/`_ftelli64`, and `cellFsRead`
   uses `fread` from the current position. Both are 64-bit and covered by
   `test_fs_large_file.cpp`, which reads at 5 GiB. The archive is 4.81 GB; the garage pages sit at
   2.5 GB.
6. **Decompression (guest):** FIOS hands 64 KiB zlib blocks to the SPU decompressor. That
   path is verified for earlier members (`STATUS.md` 2026-10-21; the LFQueue fix). All garage
   members decompress cleanly offline to their TOC sizes.
7. **Failures to the guest:** open → ENOENT, or EISDIR for a directory; read/seek on a bad fd →
   EIO. A short read reports the bytes actually read.
8. **Cache:** see `FIOS_CACHE_BEHAVIOR.md`.

## Pipeline status

| Stage | Implementation | Status |
|---|---|---|
| Loose-file probe (`cellFsOpen` → ENOENT) | runtime | **Verified implemented** (log + disc tree + archive manifest) |
| Archive lookup (TOC, name hash) | guest FIOS/PSARC code | **Verified at runtime**: seeks hit exact member starts, including `track_garage.rpk` |
| Archive seek/read past 2 GiB | runtime `cellFsLseek`/`cellFsRead` | **Verified implemented** (5 GiB test); garage-member reads **not runtime-verified** (only the first 50 reads are logged) |
| Decompression | guest FIOS → SPU zlib | **Implemented, not runtime-verified** for garage members (offline data valid) |
| FIOS cache read/write | guest FIOS on runtime `cellFs` | **Implemented, observed in use** (fd 3/4 seeks) |
| Resource parsing / object creation | guest | **Unknown** (not observed) |
| GPU upload | RSX → D3D12 backend | **Unknown** for the garage in current builds |
| Frontend loading state | guest GUI (`loadscreen-garage`) | **Verified**: the page's member was sought right after the intro closed |

**First concrete defect:** none in the load path. The diagnostic defect (`[fsread] pos=-1` past
2 GiB) is fixed in `2f6c7cf`.

**Earlier evidence beyond this point (STATUS.md, 2026-10-21, older build, no skip):** after the
intro the game loaded `track_garage`, compiled cube-map shaders and showed an emblem artwork
screen, which then brightened to white and went black.
- **HYPOTHESIS:** an auto-exposure readback.
- The emblem screen may be `loadscreen-garage` (HYPOTHESIS).
- That is the last known blocker downstream of loading, and it is outside this investigation.
