# T173: the unresolved indirect call to 0x00CB7FA8

**Status: root cause VERIFIED offline; fix implemented and verified offline; not yet run in the game.** The failure is a static-recompiler gap, not guest memory corruption and not a T170 regression. No game was launched.

| item | value |
|---|---|
| lifter baseline | ps3recomp `fda8c9b` (T170 head, on T169 `542420e`) |
| lifter fix | ps3recomp `b6f53f8`, branch `agent/t173-ppu-jump-table` (`tools/ppu_lifter.py`, `tools/test_ppu_jump_spill.py`) |
| reports | branch `agent/t173-jump-table-report` on `a3fc2d1` |
| input | `generated/decrypted/EBOOT.elf`, SHA-256 `bbb7fe2545e54847483439f59cda54e907db23a111d7afe9a1b655624886b287` |
| lift command | `docs/BUILD.md`: `ppu_lifter.py EBOOT.elf --functions EBOOT.functions.json --hle-stubs EBOOT.imports.json --jobs 6 --trace-hooks` |

## 1. What the original code does (VERIFIED from the ELF, decoded with the lifter's own `ppu_disasm`)

`func_00CB7D80` (`0x00CB7D80`-`0x00CB9458`, about 5.8 KB) is a loop that switches on a byte read through `r12` (`addi r12,r5,3` in the prologue); it reads like a small command interpreter, which is a guess. The frame is allocated by `stdu r1,-0x2A0(r1)`.

The sequence, in order (addresses in brackets; the listing itself stays in the private ELF):

1. **Spill** `[0x00CB7E34, 0x00CB7E3C]`: `lwz r10,0x65D8(r2)` loads the table address from the TOC; `std r10,0x1F0(r1)` stores it to the frame. This is the **only** store to that slot in the function.
2. **Fetch** `[0x00CB7E48-0x00CB7E50]`, the loop head and also the "default" target: `lbz r0` through `r12`, then `extsb r0,r0`.
3. **Bounds** `[0x00CB7E54, 0x00CB7E58]`: `cmplwi cr7,r0,0x1C` and `bgt cr7` back to the loop head. The compare is unsigned, so a negative byte fails it too.
4. **Dispatch** `[0x00CB7E5C-0x00CB7E74]`: `ld r11,0x1F0(r1)` reloads the base from the spill slot; `rldic r9,r0,2,30` makes `r9 = selector * 4`; `lwzx r0,r9,r11` and `extsw r0,r0` read a signed 32-bit offset; `add r11,r0,r11` adds the base; `mtctr r11`; `bctr`.
5. **Table** `[0x00CB7E78]`: 29 inline offsets directly after the `bctr`.

- **Table:** `r2 = 0x010CE894` (the second of the lifter's four TOC candidates; also the value in the crash dumps). The slot at `r2 + 0x65D8 = 0x010D4E6C` holds `0x00CB7E78`, directly after the `bctr`. 29 entries (selectors `0x00`-`0x1C`), the word after is code at `0x00CB7EEC`. The table ends where the lowest forward target begins.
- **Entries:** 29 offsets give 23 distinct targets, all word-aligned and inside the function. Selectors 4 and 25 point back at the loop head `0x00CB7E48`; some pairs share a block (6/7, 17/18, 19/20, 5/15/16). Every target decodes as an ordinary instruction.
- **Selector 1:** entry `0x130`, target `0x00CB7E78 + 0x130 = 0x00CB7FA8`, an `rldicl` that starts a case block. In the crash dumps `r9 = 4`, `r0 = 0x130`, `r11 = 0x00CB7FA8`: **the guest computed a correct target.**
- **Verdict (the Phase 1 question):** this is an intra-function computed jump, not an indirect function call. All 23 targets lie inside the function's lifted bounds and the table is inline.

Reproduce: `tools/table_t173.py` (decodes the table straight from the ELF) and `tools/dump_func_t173.py`.

## 2. Why the lifter missed it (VERIFIED)

`discover_jump_tables` finds the table base by walking back from the `bctr` to the nearest definition of the base register and accepting it only if that definition is `lwz/ld rX,d(r2)`. `JT_DEBUG=0xCB7E74` showed the walk for `r11` going `mtctr r11`, then `add r11,r0,r11`, then `ld r11,0x1F0(r1)`, ending with `bases=[]`. Three separate gaps:

1. `mtctr r11` **reads** r11, but was taken as its definition, so the walk stopped at once. (Before this, even a plain `lwz r11,d(r2); ...; add r11,r0,r11; mtctr r11` form failed. The new test fails on the old lifter for this form too.)
2. `add r11,r0,r11` **accumulates** onto the base, so r11 still held the base before it.
3. The reload `ld r11,0x1F0(r1)` is a frame load, not a TOC load. The base is only recoverable through the slot's one store, `std r10,0x1F0(r1)`, and that store's source `lwz r10,0x65D8(r2)`.

With no table, the `bctr` lifted to `ps3_indirect_call(ctx); return;`. Case labels are not function entries, so the dispatcher cannot find `0x00CB7FA8` and reports `unresolved indirect call`.

## 3. Why only now (INFERRED)

Both crashes (T170 arm A at race + 54 s, T169 baseline at race + 36 s) have identical `r3`, `r0`, `r8`, `r9`, `r11`, LR, `r3` object contents and guest call chain; only the time differs. Opcode 1 of this interpreter is evidently not reached until some in-game event, whose timing varies between runs. Why it is reached is **not known**: earlier runs that reached race + 45 s (T169) and + 62 s (TT3) never did. Selector values are decided by data the lifter does not see, so this was never testable statically. `r3` (`0x16217950`) holds floats; the `vtable=3F800000` line in the crash dump is a generic chain dump of `r3`, not evidence of corruption (the earlier hypothesis of a corrupted object was wrong; the corrected T170 results file is the uncommitted copy in `root-t170`, because `a3fc2d1` still carries the old wording).

The null-page reads and dropped writes that follow the failed dispatch (`func_00BB9800`, `NULL+0x12C`) are consistent with the guest continuing from a dispatch that never happened. That link is INFERRED, not traced.

## 4. The fix (ps3recomp `b6f53f8`)

In `discover_jump_tables`: `mtctr`, `mtlr`, `mtspr` and `add rB,x,rB` no longer count as definitions of the base register; and a base reloaded from `d(r1)` is resolved through the frame slot. `_spilled_toc_load` accepts the reload only when **all** of these hold, and otherwise leaves the dispatcher exactly as before:

- exactly one store overlaps the slot in the whole function (to the next function entry; up to the `bctr` when entries are unknown);
- it precedes the dispatcher and writes at least the reloaded width with `std`/`stw`;
- no indexed or multi-register store through `r1` exists (it might alias the slot);
- the frame is not resized (`addi r1`, `stdu/stwu r1`) between the store and the reload; the prologue's own `stdu` is fine;
- the stored register's nearest earlier definition is `lwz/ld rS,d(r2)`.

Nothing is hardcoded to this function, address or game. The decoded table is still validated against the text range as before, so a wrong guess yields no dispatcher rather than a wrong one. Original semantics are kept: CTR gets the same value, `switch (ctr)` arms are `goto` labels in the same function, and the `default:` arm keeps `ps3_indirect_call(ctx); return;` for any other target. LR is untouched by the fix.

`JT_UNRESOLVED=<file>` (off by default) lists every table-less `bctr` with its instruction shape. It only reads.

## 5. Effect on the MotorStorm lift (VERIFIED by relifting twice into private scratch trees)

| | T170 lifter | T173 lifter |
|---|---|---|
| jump-table dispatchers | 790 | **791** |
| case targets | 6,456 | **6,479** (+23) |
| lifted files | 79 | 79; **2 differ**, 77 byte-identical |

- The two files are `ppu_recomp_026.cpp` (`func_00CB7D80`) and `ppu_recomp_006.cpp` (`func_00CB7D7C`, a duplicate lift of the same code that starts 4 bytes earlier, from the function list; a pre-existing artefact, fixed the same way).
- In each: **1 line replaced** (`ps3_indirect_call(ctx); return;` became a `switch ((uint32_t)ctx->ctr)` with 23 `goto` arms and the original default) and **22 `loc_X: PPU_TR_BB(...)` labels added** (the 23rd target already had its label). Nothing else moved.
- `tools/verify_arms_t173.py`: the 23 arms equal the targets decoded from the ELF independently of the lifter; each has exactly one label in its function; the default and the `mtctr` are unchanged.
- A second relift with the audit switch on is byte-identical to the first (deterministic), and a third after a small refactor produced the same SHA-256 for both chunks.

New chunk SHA-256: `ppu_recomp_026.cpp` `33de8d1a3d288265c349758924cb1bccf929f8e38592c740c59f407e2b6f11cf`, `ppu_recomp_006.cpp` `8959fbe922e67205ef719cea74ca9c8946ac8c93173c1db5121158713e25b7bf`. Staging before: `c0838882…469a20` and `8da88655…ff8e4`.

**Lifter drift:** the existing `generated/ppu-hooked-staging` (lifted 2026-10-21) does not equal a fresh T170-lifter output: 21 other chunks and the header differ, from ps3recomp's raw-store coherence change (`VM_COH_RAW`, opt-in at runtime). Chunks 006 and 026 are identical in both. T173 therefore does **not** replace the staging wholesale; the validation tree is the old staging with just those two chunks swapped (`generated/ppu-t173-staging`), so the executable differs from T170 arm A in the jump table and nothing else.

## 6. Other occurrences of the same pattern (Phase 2 scan)

- **Modified output:** the relift above changed exactly one dispatcher. No other function in the 53,278 lifted ones changed, so the three base-search changes did not alter any other result. No other dispatcher was dropped by the old rules in this binary.
- **Still without a table:** 386 `bctr`. `tools/classify_bctr_t173.py` reads each from the ELF: **all 386** take `mtctr` from an `lwz` out of a function descriptor (`lwz r12,d(r12); lwz r0,0(r12); lwz r2,4(r12); mtctr r0; bctr`), the import-stub and virtual-tail-call shape. None has an indexed load (`lwzx`/`lwax`) within 120 instructions. Classified as legitimate indirect tail calls; **no change made.**
- **Limits:** a switch whose indexed load sits more than 120 instructions before its `bctr`, one with no `lwzx`/`lwax` (for example `lwz` through a computed address), or a table in a form that is neither absolute nor base-relative would not show up. The scan cannot prove a negative.

## 7. Unresolved risks

1. **New code runs for the first time.** Until now this port always died on the first `case`, so the 22 case bodies behind the switch have never executed. They may hit other unlifted targets, other gaps, or data that the port mishandles. A pass past race + 70 s is the only test.
2. **Trigger unknown.** Because the time to the first opcode 1 varies, one clean run proves less than one failed run did.
3. **Faithful spin.** An out-of-range selector byte makes the original loop forever on `0x00CB7E48` (`r12` is unchanged). The lifted code does the same. It is unlikely, but if the game ever feeds such a byte the host thread will spin, not crash.
4. **Public lifter change:** the fix is a general change to jump-table discovery. In this binary only one dispatcher changed; other titles were not relifted. The lifter's own test files pass (see `REGRESSION_VALIDATION.md`).
