"""Private: MSPR_COCKPIT_TUNE hooks in the PPUCC lift (1.00), for port-vkgame/main.cpp mspr_cock_*.

  func_0037D640 (camera-list line parser), FORWARD branch, after the position/orientation stores (before the
    0x0037D894 call): mspr_cock_parsed(r1, r25 vehicle name, r27 camera slot) records CAMERA 2 / CAMERA 3 and
    applies saved cockpit values; a non-zero return is the lens, whose projection is rebuilt (func_004302A8).
  func_00376394 / func_00376398 (camera update; the MSPR_CAM rate copy at 0x003764F0), after that copy:
    mspr_cock_tick(r30 = the camera manager) reads the free-flight keys while the manager's current camera is the
    cockpit one and writes the cockpit camera; non-zero = lens to rebuild.
The lens rebuild runs on a copy of the registers, restored after it, so the lifted code sees no change.
Idempotent; counts are asserted. A hook or declaration line from an older version of this script (marked with
MSPR_COCKPIT_TUNE) is replaced in place. Run after cam_patch_ppucc.py (it anchors on that patch's rate line).
usage: py -3 cockpit_tune_patch_ppucc.py <lift dir, e.g. D:/motorstorm/ppucc2/ppu-v100-ppucc2>"""
import os
import pathlib
import re
import shutil
import sys

ST = pathlib.Path(sys.argv[1])
MARK = 'MSPR_COCKPIT_TUNE */'
DECL = ('extern "C" uint64_t mspr_cock_parsed(uint64_t r1, uint64_t name, uint64_t slot, uint64_t site); '
        'extern "C" uint64_t mspr_cock_tick(uint64_t mgr);   /* port main.cpp: MSPR_COCKPIT_TUNE */')


def rebuild(call, lr):
    return (f'{{ const uint64_t _cl = {call}; if (_cl) {{ ppu_context _cs = *ctx; ctx->gpr[3] = _cl; '
            f'ctx->lr = 0x{lr:08X}; func_004302A8(ctx); DRAIN_TRAMPOLINE(ctx); *ctx = _cs; }} }}')


PARSE_AT = ('ctx->lr = 0x0037D898; func_00751EF8(ctx); DRAIN_TRAMPOLINE(ctx); '
            'PPU_TR_RET(ctx, 0x0037D898u, 0x00751EF8u);')
PARSE_HOOK = (rebuild('mspr_cock_parsed(ctx->gpr[1], ctx->gpr[25], ctx->gpr[27], 0)', 0x0037D894)
              + '   /* 0x0037D894 cockpit camera parsed; MSPR_COCKPIT_TUNE */')
# A slot without a view yet (the first load of a list: [slot+8] == 0) takes 0x0037DC98, which builds the view from
# the same sscanf values (func_0037D1D0), stores it at slot+8 / slot+4 (0x0037DCF8..0x0037DD08) and joins the
# side-view code at 0x0037DBBC, so it never passes 0x0037D894. The host checks the line's type (FORWARD only).
NEWVIEW_AT = 'vm_write32(ctx->gpr[27] + 0x4, ctx->gpr[7]);'
NEWVIEW_HOOK = (rebuild('mspr_cock_parsed(ctx->gpr[1], ctx->gpr[25], ctx->gpr[27], 1)', 0x0037DD0C)
                + '   /* 0x0037DD0C new cockpit view parsed; MSPR_COCKPIT_TUNE */')
RATE = ('{ float ftmp = mspr_cam_rate((float)ctx->fpr[13]); uint32_t tmp; memcpy(&tmp, &ftmp, 4); '
        'vm_write32(ctx->gpr[31] + 0x10, tmp); }   /* 0x003764F0 camera rate; MSPR_CAM */')
TICK_HOOK = (rebuild('mspr_cock_tick(ctx->gpr[30])', 0x003764F4)
             + '   /* 0x003764F0 cockpit free-flight keys; MSPR_COCKPIT_TUNE */')

# (file, function, anchor line, hook line before (-1) or after (+1) it, expected count)
EDITS = [
    ('ppu_recomp_009.cpp', 'func_0037D640', PARSE_AT, PARSE_HOOK, -1, 1),
    ('ppu_recomp_009.cpp', 'func_0037D640', NEWVIEW_AT, NEWVIEW_HOOK, +1, 1),
    ('ppu_recomp_001.cpp', 'func_00376394', RATE, TICK_HOOK, +1, 2),
    ('ppu_recomp_009.cpp', 'func_00376398', RATE, TICK_HOOK, +1, 2),
]
FUNC = re.compile(r'void (func_[0-9A-F]{8})\(ppu_context\* ctx\) \{')


def patch(name, edits):
    path = ST / name
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.cock-tmp')
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
        print(f'{name}: hard link replaced by a copy')
    lines = path.read_bytes().decode('latin-1').split('\n')
    # first drop this script's old hook lines next to an anchor (they are re-added below in their current form)
    keep, fn = [], None
    for i, raw in enumerate(lines):
        m = FUNC.match(raw)
        if m:
            fn = m.group(1)
        body = raw.strip()
        if body.endswith(MARK) and 'mspr_cock_' in body and i > 8:
            near = [lines[j].strip() for j in (i - 1, i + 1) if 0 <= j < len(lines)]
            if any(fn == e[1] and e[2] in near for e in edits):
                continue
        keep.append(raw)
    removed = len(lines) - len(keep)
    out, fn, n = [], None, [0] * len(edits)
    for raw in keep:
        text = raw.rstrip('\r')
        m = FUNC.match(text)
        if m:
            fn = m.group(1)
        eol = '\r' if raw.endswith('\r') else ''
        indent = text[:len(text) - len(text.lstrip())]
        post = []
        for k, (_, f, anchor, hook, where, _c) in enumerate(edits):
            if fn == f and text.strip() == anchor:
                (out.append if where < 0 else post.append)(indent + hook + eol)
                n[k] += 1
        out.append(raw)
        out.extend(post)
    for k, e in enumerate(edits):
        assert n[k] == e[5], f'{name} {e[1]}: matched {n[k]}, want {e[5]}'
    head = [i for i in range(1, 8) if 'port main.cpp: MSPR_COCKPIT_TUNE' in out[i]]
    if head:
        out[head[0]] = DECL + ('\r' if out[head[0]].endswith('\r') else '')
    else:
        assert out[1].startswith('#include "ppu_recomp.h"'), out[1]
        out.insert(2, DECL + ('\r' if out[1].endswith('\r') else ''))
    data = '\n'.join(out).encode('latin-1')
    if data != path.read_bytes():
        path.write_bytes(data)
        print(f'{name}: {sum(n)} hooks written ({removed} older hook lines replaced)')
    else:
        print(f'{name}: already current ({sum(n)} hooks)')


for f in sorted({e[0] for e in EDITS}):
    patch(f, [e for e in EDITS if e[0] == f])
