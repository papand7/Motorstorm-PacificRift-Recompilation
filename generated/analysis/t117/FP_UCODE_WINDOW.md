# T117: FP 0x07200641, undeclared `_rsx_expand_input`

Worktree `ps3recomp-t117`, branch `agent/t117-fp-ucode-window`, based on T116 `30b817b`.

## Cause (VERIFIED)
- The helper exists and is named correctly. It is emitted when the scans `rsx_fp_texture_expand_units` / `rsx_fp_texture_bx2_units` find a fetch. Both scans return 0 if no `END` is found within `max_bytes`.
- The main decode loop did not need `END`: it emitted whatever fitted in the window and returned success.
- The D3D12 backend passed a 4096-byte window (256 slots) to every FP walker.
- 0x07200641 in T113 runtime F decoded 187 instructions + 69 inline constants = 256 slots = 4096 bytes exactly. It is the only one of the 152 captured FPs that fills the window. The next largest is 249 slots.
- Its only `_bx2` fetch is TEX unit 3 (dumped line 182).
- So the program was cut off, the scan saw no END, and the helper was never declared.
- Repro: `fxc /T ps_5_0` on `t113/runtime-F-20261027-180148/rsxi/shaders/fp_07200641.hlsl` (sha256 30c7c658...) gives `(182,28-105): error X3004: undeclared identifier '_rsx_expand_input'`. See `logs/repro.log`.
- The guest ucode bytes were never dumped, so the real program length is unknown (PARTIAL). It is more than 256 slots.

## Fix
- `rsx_fp_decompiler.c`: the decoder refuses a program with no `END` inside `max_bytes` (returns -1 and logs, at most 16 times). It no longer emits the head of a program.
- `rsx_d3d12_backend.c`: one constant, `D3D_FP_UCODE_BYTES` = 16384 (1024 slots), replaces 4096 in all 15 FP walks: size, code hash, units, transfers, decompile, fp_k and RSXI.

## Cache (T116)
- The negative cache and the bytecode cache are keyed on the HLSL text plus the compiler identity. The corrected text is a different key; failures are never written to disk.
- `vp_fp` keys on `uhash`, which now hashes the whole program. Its failure memory is in-process only.
- No format bump is needed. This is tested in `test_rsx_shader_cache.c` (`test_fp_long_program`).

## Output change (HYPOTHESIS until a run)
- 2 indexed draws per race frame (143 and 216 vertices) use this FP. Target: RT 0x00750000 + MRT 0x01650000, fmt 12616. Blend on, depth test on, depth write off.
- Before the fix they had no pipeline and were dropped. After it they draw, unless the program is longer than 16 KiB, in which case the log shows `no END within 16384 bytes`.
- What they look like is unverified without a launch.

## Not changed
- The Vulkan and Metal backends keep their 4096-byte windows. With the decompiler change, a program longer than that now fails there instead of rendering its truncated head.
- Possible follow-up (HYPOTHESIS): the main loop skips an inline-constant slot after a flow-control instruction whose address words have type bits == 2, but the helper scans do not. This is not triggered by this program, which has no branches.

## Tests
- `test_fp_decompiler.c`: 84 PASS. The old decompiler fails `long_window_refused` and `long_no_end_refused`.
- `test_d3d12_shader_cache.py`: 77 PASS, with the C test on WARP and real D3DCompile.
- Also pass: shader_trace, color_xfer, blend, depth, t110_pins (pin updated for the constant), fp_alias, fp_shadow_compare, rsxi_hooks, texture_source_order, zeta_pool.
- TU (`tools/tu_t117.cmd`): rc=0, 3030 warnings with the same kinds as T116.
