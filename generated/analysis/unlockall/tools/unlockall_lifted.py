"""Cheats: guards at the entry of unlock predicates in the lifted code (private, not shipped).

Each predicate is a thin dispatch wrapper (the callee comes from a TOC-slot object), so the guard returns
before any call is made when its switch is on (port-vkgame pc_menu.cpp, settings.ini / environment). Off by
default: without the switch the guard falls through to the original code and the behaviour is unchanged.

  vehicles (unlockvehicles, MSPR_UNLOCK_VEHICLES; mspr_unlock_vehicles_on)
    0x0024C140  the vehicle-class unlock test (index, table): returns 1. Every vehicle-class query goes
                through it: IsVehicleClassUnLocked (impl 0x00017F38), AllVehicleClassesLocked (impl 0x0002E648, 8 calls),
                TicketClassSelectable (impl 0x000359D0), func_0024C300 (8 calls). The game's own test returns 1 early when a
                global byte (*(TOC+0xCDC)+8) is set; this is the same answer, from the switch.
    0x0077DE00  TicketIsUnlocked(ticket) binding wrapper: returns 1.
  tracks (unlocktracks, MSPR_UNLOCK_TRACKS; mspr_unlock_tracks_on)
    0x0024BD10  keyed unlock query (table, category, key), only for the call from the Free Play track-list
                builder func_002791A0 (return address 0x00279674): returns 1, so every track passes that filter.
                Other callers (categories 0 and 1 at 0x0005AEA0 / 0x0005B208) are untouched. PARTIAL: the Festival
                and Time Trial track lists were not traced.

Names: the GUI binding table (0x01098xxx), whose records are {OPD, name}: each name goes with the OPD
BEFORE it. generated/analysis/frontend_commands.txt pairs each name with the OPD after it, one row off:
the address it lists for a name belongs to the NEXT row's name. Checked by the wrappers' signatures
(UnLockVehicleClass(class) void, IsVehicleClassUnLocked(class) bool, AllVehicleClassesLocked() bool,
SetSelectedVehicleClass(class) void) and by FreePlayNextTrack/PreviousTrack stepping the index +1/-1.
The first version guarded the listed (wrong) addresses 0x0076F238 and 0x0077DE70, and a second version the
binding wrappers 0x0076F160 / 0x0076F1D0; those guards are removed. Save data is not read or written here.
The guard goes on the header line, before the trace macro. Idempotent; a guard from the first version
(mspr_unlock_all_on) is upgraded in place. Each header must be found exactly once across the lifted files.
Usage: py -3 unlockall_lifted.py <lifted dir, e.g. D:/motorstorm/ppucc2/ppu-v100-ppucc2>"""
import os
import pathlib
import re
import shutil
import sys

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
ST = pathlib.Path(sys.argv[1])
SWITCHES = {
    'mspr_unlock_vehicles_on': 'unlockvehicles',
    'mspr_unlock_tracks_on': 'unlocktracks',
}
DECLS = [f'extern "C" int {fn}(void);   /* port pc_menu.cpp: settings.ini {key} */' for fn, key in SWITCHES.items()]
OLD_DECL = re.compile(r'^extern "C" int mspr_unlock_all_on\(void\);.*$')
GUARD_RE = re.compile(r' if \([^{}]*mspr_unlock_\w+_on\(\)\) \{ ctx->gpr\[3\] = \d+; return; \}   /\* \w+: \w+ \*/')
# (function, switch function, extra condition ('' = always), value returned, name)
EDITS = [
    ('func_0024C140', 'mspr_unlock_vehicles_on', '', 1, 'VehicleClassUnlocked'),
    ('func_0077DE00', 'mspr_unlock_vehicles_on', '', 1, 'TicketIsUnlocked'),
    ('func_0024BD10', 'mspr_unlock_tracks_on', 'ctx->lr == 0x00279674u && ', 1, 'FreePlayTrackFilter'),
]
# functions that must carry no guard (earlier versions' targets)
CLEAN = ['func_0076F238', 'func_0077DE70', 'func_0076F160', 'func_0076F1D0']
FILES = sorted(ST.glob('ppu_recomp_*.cpp'))


def header(fn):
    return f'void {fn}(ppu_context* ctx) {{'


def guard(sw, cond, val, name):
    return f' if ({cond}{sw}()) {{ ctx->gpr[3] = {val}; return; }}   /* {SWITCHES[sw]}: {name} */'


def relink_copy(path):
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.unlockall-tmp')
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
        print(f'{path.name}: hard link replaced by a copy')


where = {}
for path in FILES:
    text = path.read_bytes().decode('latin-1')
    for fn, *_ in EDITS:
        if '\n' + header(fn) in text:
            where.setdefault(fn, []).append(path)
for fn, *_ in EDITS:
    assert len(where.get(fn, [])) == 1, f'{fn}: found in {where.get(fn)}, want exactly one file'
for path in FILES:
    text = path.read_bytes().decode('latin-1')
    for fn in CLEAN:
        if '\n' + header(fn) in text:
            where.setdefault(fn, []).append(path)

for path in sorted({p for ps in where.values() for p in ps}):
    relink_copy(path)
    lines = path.read_bytes().decode('latin-1').split('\n')
    done = 0
    for fn, sw, cond, val, name in EDITS:
        if path not in where[fn]:
            continue
        hdr = header(fn)
        idx = [i for i, l in enumerate(lines) if l.startswith(hdr)]
        assert len(idx) == 1, f'{path.name}: {fn} header matched {len(idx)}'
        i = idx[0]
        eol = '\r' if lines[i].endswith('\r') else ''
        body = lines[i][len(hdr):].rstrip('\r')
        want = guard(sw, cond, val, name)
        if body.startswith(want):
            continue
        body = GUARD_RE.sub('', body, count=1)   # an older guard on this function, replaced
        lines[i] = hdr + want + body + eol
        done += 1
    for fn in CLEAN:
        hdr = header(fn)
        for i, l in enumerate(lines):
            if l.startswith(hdr) and GUARD_RE.search(l):
                lines[i] = GUARD_RE.sub('', l, count=1)
                done += 1
    # declarations: the first version's is removed, each switch declared once after the include
    lines = [l for l in lines if not OLD_DECL.match(l.rstrip('\r'))]
    assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
    eol = '\r' if lines[1].endswith('\r') else ''
    for d in reversed(DECLS):
        if not any(l.rstrip('\r') == d for l in lines[:12]):
            lines.insert(2, d + eol)
    path.write_bytes('\n'.join(lines).encode('latin-1'))
    print(f'{path.name}: {done} guard(s) added or upgraded')
print('done')
