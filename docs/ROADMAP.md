# Roadmap

Milestones in order of dependency. No dates are promised; a milestone is complete only when a controlled run
verifies its exit criterion and `docs/STATUS.md` records it.

| # | Milestone | State | Exit criterion |
|---|---|---|---|
| P0 | Decrypted executable, static translation, native link | ✅ complete | Verified standalone ELF; lifted PPU and 26 embedded SPU images link and run original startup. |
| P1 | Original startup, intro, frontend | ✅ reached | Splash, Bink intro, garage and main menu render from original code. |
| 1 | Stable race execution | 🟡 active | A full race completes from the menu without hangs, repeatably. |
| 2 | Accurate RSX image quality | 🟡 active | Race frames match reference hardware captures for the known faults (surf band, right-edge window, MSAA, samplers, mips). |
| 3 | Faster PPU/SPU execution | 🟡 active | All SPURS lanes the game requests, AOT for every hot SPU workload, no host spin waits; measured in a controlled race run. |
| 4 | Correct simulation timing | ⚪ not started | Simulation steps per second and handling match the console at the achieved frame rate. |
| 5 | Audio and input completion | 🟡 partial | All in-game audio streams in sync; full controller mapping, including the sixaxis sensor if used. |
| 6 | Graphics enhancements (optional) | 🔵 planned | Opt-in only, after 2 is verified; never the default. |
| 7 | Modding support | 🔵 planned | Data-only mods loaded from a user folder without changing original code. |
| 8 | Broader hardware compatibility | 🔵 planned | 720p/60 FPS on Radeon 890M-class integrated graphics (long-term target); other GPUs and Windows versions tested. |
| 9 | Packaging and installation | 🔵 planned | A source-only build that guides users through supplying their own data; no game code or assets in any package. |
| P2 | Native networking (optional) | 🔵 planned | Compare network calls with the [MSPR private server](https://github.com/ZoniBoy00/MSPR-Server); validate lobbies before any crossplay claim. |

Current blockers and the latest per-task findings: [STATUS.md](STATUS.md). P3/P4 (mods, enhancements) start only
after the original offline race works and fidelity can be measured ([AGENTS.md](../AGENTS.md)).
