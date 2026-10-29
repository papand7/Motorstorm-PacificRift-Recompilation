#!/usr/bin/env python3
"""T152: port/CMakeLists.txt option MSPR_PPU_INLINE_STORES, off by default.

Pins: the option defaults OFF; it refuses a ppu_recomp.h without the T152 page gates; it adds
PPU_INLINE_STORES to the lifted sources only (appended, so the warning/bigobj options stay).
The run-time gate (PS3_VM_STORE_INLINE=1) lives in the ps3recomp runtime.

  python tools/test_port_inline_stores_option.py
"""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = (root / 'port/CMakeLists.txt').read_text(encoding='utf-8').replace('\r\n', '\n')
fails = 0


def check(ok, what):
    global fails
    print(f"[{'PASS' if ok else 'FAIL'}] {what}")
    fails += not ok


check('option(MSPR_PPU_INLINE_STORES "Compile the lifted PPU code with inline guest stores (opt-in at run time)" OFF)' in src,
      'MSPR_PPU_INLINE_STORES is an option, default OFF')
blk = re.search(r'\nif\(MSPR_PPU_INLINE_STORES\)\n(.*?)\nendif\(\)\n', src, re.S)
blk = blk.group(1) if blk else ''
check('REGEX "vm_write8_inl"' in blk and 'FATAL_ERROR' in blk, 'configure fails closed on a header without the page gates')
check('set_property(SOURCE ${RECOMP_SOURCES} APPEND PROPERTY COMPILE_DEFINITIONS PPU_INLINE_STORES)' in blk,
      'PPU_INLINE_STORES is appended to the lifted sources only')
check(src.count('PPU_INLINE_STORES') - src.count('MSPR_PPU_INLINE_STORES') == 2 and   # the define + the status line
      src.index('if(MSPR_PPU_INLINE_STORES)') > src.index('COMPILE_OPTIONS "/w;/bigobj"'),
      'nothing else defines it; the block follows the lifted sources\' own options')
print(f'test_port_inline_stores_option: {fails} failure(s)')
raise SystemExit(1 if fails else 0)
