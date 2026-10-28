# Third-party licenses

This repository distributes original project source and uses external tools. It does not distribute game or firmware files, lifted game or firmware code, or a linked game executable.

| Component | Use | License and attribution | Distribution status |
|---|---|---|---|
| [ps3recomp](https://github.com/sp00nznet/ps3recomp), commit `0fe7dbf5db9a467aca268865fb26170ea113c541` | Static recompiler and compatibility runtime | MIT; copyright 2026 Ned Heller / sp00nznet, except separately licensed components. Preserve `ps3recomp/LICENSE`. | Source included in the audited source staging tree. |
| `ps3recomp/third_party/at3_standalone` | ATRAC decoder source vendored by ps3recomp from PPSSPP/FFmpeg | LGPL-2.1-or-later, per `ps3recomp/third_party/at3_standalone/README.txt`; preserve `COPYING.LGPLv2.1`, source and notices. | Included as source; no linked binaries distributed. |
| Python standard library | Local preparation and audit scripts | Python Software Foundation License | Runtime dependency; not bundled. |
| CMake, Ninja, Clang, Visual Studio toolchain, Windows SDK | Local build tools | Their respective licenses | Not bundled by this project. |
| [RPCS3](https://github.com/RPCS3/rpcs3) | Local firmware decryption/export diagnostic only | GPL-2.0-only for most source; preserve its own notices when obtaining the tool. No RPCS3 implementation code is copied into this project. | Not bundled, linked, or used as the native game's execution backend. |
| [ps3dev ps3toolchain](https://github.com/ps3dev/ps3toolchain), commit `de85d7d5d11dc0a99d823ece3d440eea46c34d0f` | Local PPU/SPU compiler toolchain build | BSD-2-Clause; copyright 2019 ps3dev members, per its local `LICENSE`. Toolchain components retain their own licenses. | Installed in private WSL home; not bundled. |
| [PSL1GHT](https://github.com/ps3dev/PSL1GHT), commit `f649a08fd536a9e27c08c7db2d93a2d7ee4c3bbe` | Local PS3 fixture headers, import stubs and sample Makefile | MIT; copyright 2011 PSL1GHT Development Team, per its local `LICENSE`. | Installed in private WSL home; not bundled. Public fixture source is independently authored. |

The ps3recomp license text is in [`ps3recomp/LICENSE`](ps3recomp/LICENSE); the ATRAC decoder license is in [`ps3recomp/third_party/at3_standalone/COPYING.LGPLv2.1`](ps3recomp/third_party/at3_standalone/COPYING.LGPLv2.1). Python package requirements (`pycryptodome`, `capstone`, `construct`, `tabulate`, `tomli`, `tqdm`) and optional system libraries are installed locally, not bundled in this source stage. Any future vendored dependency must be reviewed and added here before release. The audit cannot establish license provenance by itself.
