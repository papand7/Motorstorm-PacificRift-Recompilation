# Next update: parked items

Items found before the 0.1.0 release and deliberately left for the next update.

- **Water too bright** (reported 2026-11-23): the sea and water surfaces get far too bright in race. Check with reflections (`RSX_FX_SSR`) on and off, and with Original vs Enhanced lighting, to find which pass over-brightens it.
- **Static shadow layer** (`RSX_SHADOW_TILES_STATIC`): the bake target draws 0 texels (Kst7/Kst8 bake checks). Next step: bake into a second map with exactly the dynamic map's size and rows. See `generated/analysis/shadowtiles/RESULTS.md`.
- **Far sun shadows** beyond about 256 m with world-tile shadows (phase 1 limit; the game's far cascade reached about 800 m).
- **Tessellation / parallax occlusion mapping** on terrain: parallax first (height maps from the texture pack step).
- **Cheats**: parked; Free Play unlock is enough for now.
