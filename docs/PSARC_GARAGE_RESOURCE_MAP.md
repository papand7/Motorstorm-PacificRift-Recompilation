# MS2.PSARC: garage resource map (offline, 2026-10-23)

Source: the original `original/game/PS3_GAME/USRDIR/MS2.PSARC` (4,811,608,561 B), read-only.
Tools (private): `generated/analysis/garage_seek_map.py` (TOC, seek → member),
`generated/analysis/psarc_member_verify.py` (decompresses named members **in memory**, nothing
written). The archive is unchanged.

## Archive format (VERIFIED, header and TOC)

- `PSAR` v1.3, compression `zlib`, TOC 536,696 B, entry 30 B, 5,005 entries (entry 0 = name
  manifest, 5,004 names), block 65,536 B, flags 0x3.
- Entry: MD5 of the name (16 B), first block index (4 B), uncompressed size (5 B), offset (5 B).
  A block-length table follows the TOC. A block length of 0 means a full 64 KiB block; a block
  that does not start with a zlib header is stored raw.
- MD5 name hashes match for every member checked below (`name_md5_ok`).

## Garage members (VERIFIED: TOC values; decompressed in memory to the TOC size)

| Member | Offset | Compressed span | Uncompressed | Blocks | Compression | SHA-256 (uncompressed) |
|---|---|---|---|---|---|---|
| `/worlds/track_garage.rpk` | 1,917,461,852 | 23,207,184 | 50,030,033 | 764 | zlib ×764 | `8b5ecd9f…a7b42` |
| `/gui/loadscreen-garage.gui` | 2,536,802,865 | 588,359 | 1,974,530 | 31 | zlib ×31 | `4bd28780…95765` |
| `/gui/textureresources/guiloading.rpk` | 35,455,985 | 32,296,983 | 91,251,230 | 1,393 | zlib ×1393 | `8369c00c…aa6e` |
| `/env/Track0a_Garage_Sky1_driver.rpk` | 244,169,081 | 8,650,343 | 13,377,606 | 205 | zlib ×205 | `0aa9ef06…dae5a` |
| `/data/track_garage/track_garage.def` | 2,510,307,332 | 25 | 25 | 1 | stored | `2b759050…2201c` |
| `/data/track_garage/track_garage.trg` | 215,876,968 | 107 | 125 | 1 | zlib | `3dda6ba8…754c` |
| `/data/track_garage/track_garage.audioNode` | 215,876,576 | 392 | 1,364 | 1 | zlib | `a3c9eafc…27f4` |
| `/audio/track_garage.aeb` | 2,456,386,328 | 2,409,012 | 2,580,396 | 40 | zlib ×40 | `2895a972…11f8` |
| `/audio/track_garage.aes` | 73,528,374 | 148 | 468 | 1 | zlib | `96e5303a…749f` |
| `/audio/track_garage.nam` | 2,458,795,340 | 152 | 295 | 1 | zlib | `e69cdffa…1032` |
| `/data/profile/garage.xml` | 2,494,736,072 | 3,490 | 41,704 | 1 | zlib | `a95c2b31…de44` |

Full hashes: `psarc_member_verify.py` output (re-runnable). Other garage members: the
`/env/Track0a_Garage_Sky1_Morning.rpk`, `Sky2_vehicle.rpk` sky packages, four
`/EffectMaps/worlds/track_garage_*_FX.csv`, and the `/gui/garage-*.gui` pages (garage menus).

- `.rpk`, `.gui` and `.aes` members start with `EVOS` (the game's resource-pack container).
- `track_garage.rpk` names its own Havok world (`track_garage.hkx`) and about 25 source textures
  (`/art/worlds/track_garage/...dds`). They are packed inside it, not separate members.

## Requested but not in the archive (VERIFIED absent)

The loose-file probes in the run (below) name files that exist **neither** on the disc tree nor in
the archive manifest:

- `worlds/track_garage_{ain,cps,gan}_objects.rpk`. Every race track has these three members
  (e.g. `/worlds/track_edge_ain_objects.rpk`); the garage has none.
- `data/track_garage/track_garage.{jump,bin,spvs,gvl}`. The garage has only `.def`, `.trg` and
  `.audioNode`.
- `data/events/default.gags`.

**SUPPORTED HYPOTHESIS:** these are optional per-track files the loader probes for every world.
The game continued straight after the misses (next section), so a miss is not fatal.

## Dependencies supported by the data

- `loadscreen-garage` page (enter handler: `GotoGarage`, `PrepareLoadingScreen`,
  `FirstGarageVisit`; see `ORIGINAL_INTRO_SKIP_ANALYSIS.md`) → `guiloading.rpk` textures.
- `GotoGarage` → `track_garage.rpk` + `Track0a_Garage_Sky1_driver.rpk` (sky) → optional probes →
  `screenrush.xml`, `post.rpk`, particle and audio packages.

This order is the observed seek order (next doc). The causal links are HYPOTHESIS; the code
was not traced.
