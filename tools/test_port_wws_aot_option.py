#!/usr/bin/env python3
"""T152: port/CMakeLists.txt carries the MSPR_WWS_AOT block (from port-t70 / T106), off by default.

Pins: the option defaults OFF; it refuses to configure without the runtime's spu_reloc.h or
the lifted register TU; the lifted modules join SPU_SOURCES only inside the option; the
block sits after the SPU source list is complete and before SPU_SOURCES is consumed.
The run-time gate (PS3_SPU_WWS_AOT=1) lives in the ps3recomp runtime, not here.

  python tools/test_port_wws_aot_option.py
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


check('option(MSPR_WWS_AOT "Compile the relocatable Wws job-module AOT (opt-in at run time)" OFF)' in src,
      'MSPR_WWS_AOT is an option, default OFF')
blk = re.search(r'\nif\(MSPR_WWS_AOT\)\n(.*?)\nendif\(\)\n', src, re.S)
blk = blk.group(1) if blk else ''
check('runtime/spu/spu_reloc.h' in blk and 'wws_reloc_register.c' in blk and blk.count('FATAL_ERROR') == 2,
      'configure fails closed without spu_reloc.h or the lifted register TU')
check('list(APPEND SPU_SOURCES ${MSPR_WWS_AOT_SOURCES} "${MSPR_WWS_AOT_DIR}/wws_reloc_register.c")' in blk,
      'lifted modules are added to SPU_SOURCES only inside the option')
check(src.count('MSPR_WWS_AOT_SOURCES') == 3 and 'MSPR_WWS_AOT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../generated/spu_raw/wws_reloc"' in src,
      'nothing outside the block references the lifted modules; default dir is generated/spu_raw/wws_reloc')
first_use = min(m.start() for m in re.finditer(r'\$\{SPU_SOURCES\}', src))
check(src.index('if(MSPR_WWS_AOT)') < first_use, 'the block runs before SPU_SOURCES is consumed')
print(f'test_port_wws_aot_option: {fails} failure(s)')
raise SystemExit(1 if fails else 0)
