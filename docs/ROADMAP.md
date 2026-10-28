# Roadmap

1. **P0 — decrypted executable: complete.** The supplied ELF is hashed separately from the preserved retail SELF and ISO. Its OPD, imports, segments and entry are recorded in `docs/RESEARCH.md`.
2. **P0 — static translation: partial.** PPU code, 26 embedded SPU ELF images and the raw Wws_Job policy module are lifted. Review the PPU lifter's 26 missing-continuation warnings and identify any further dynamically loaded SPU programs.
3. **P0 — Windows x64 compile and link: complete for discovered code.** The native executable links and executes original startup; preserve the current build as a baseline.
4. **P1 — original startup: active.** Trace task 0 in taskset `0x40493480` and event flag `0x40494D80`; identify the exact producer of the missing signal or event, then implement the missing runtime behavior with a targeted regression test. Continue through original graphics, audio, menus and an offline race.
5. **P2 — native networking.** Compare this executable's network calls and version with the [MSPR private server](https://github.com/ZoniBoy00/MSPR-Server); validate lobbies and races before crossplay claims.
6. **P3/P4 — optional mods and graphics upgrades.** Begin after the original offline race works and fidelity can be measured.
