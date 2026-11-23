#!/usr/bin/env python3
"""Inclusive sampling profiler (vksync; Windows x64, no debugger), built on thread_sampler_top.py.

Like thread_sampler_top.py it suspends the busiest threads, reads RIP/RSP and resumes them. In
addition it reads the thread's live stack (RSP up to the TEB's StackBase, at most 512 KB) and walks
it frame by frame with the exe's x64 unwind tables (.pdata/.xdata), so stale return addresses left in
a frame are not counted. A leaf in a system DLL starts the walk at the first return into the image (a
value whose preceding bytes are a call instruction). Lifted PPU functions call each other as host
functions, so the frames are the guest call chain.

Per thread it reports, over the samples whose leaf is not a wait (ntdll/KernelBase waits, delays,
QueryPerformanceCounter spins, sys_timer_usleep), and separately over the waiting samples
('incl_wait', 'self_wait': where in the guest call chain the thread waits):
  incl  the fraction of running samples with the function anywhere on the stack (counted once a sample)
  self  the fraction with the function as the leaf
A PC inside an epilog is unwound as if past it (a small error). Run it on a separate launch from the
one you time.

  py -3 thread_sampler_incl.py --pid N --map game.map [--seconds 30] [--hz 150] [--threads 3] [--json out.json]
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import struct
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from thread_sampler_top import (CONTEXT_CONTROL, CTX_FLAGS, CTX_RIP, CTX_RSP, CTX_SIZE,  # noqa: E402
                                THREAD_ALL, ModuleMap, SymbolMap, image_size, k32, main_module_base,
                                process_modules, thread_cpu, thread_ids)

STACK_MAX = 512 * 1024
WAIT_WORDS = ('Wait', 'Delay', 'Sleep', 'QueryPerformance', 'Yield', 'SwitchToThread', 'AlertByThreadId',
              'sys_timer_usleep')


class CallCheck:
    """Is the instruction before an image RVA a call? (the exe file's executable sections)"""

    def __init__(self, exe: Path):
        b = exe.read_bytes()[:4096]
        pe = struct.unpack_from('<I', b, 0x3C)[0]
        n = struct.unpack_from('<H', b, pe + 6)[0]
        o = pe + 24 + struct.unpack_from('<H', b, pe + 20)[0]
        self.secs = []
        for _ in range(n):
            vs, va, rs, rp, ch = (*struct.unpack_from('<IIII', b, o + 8), struct.unpack_from('<I', b, o + 36)[0])
            if ch & 0x20000000:
                self.secs.append((va, min(vs, rs), rp))
            o += 40
        self.mm = np.memmap(exe, dtype=np.uint8, mode='r')

    def mask(self, rva: np.ndarray) -> np.ndarray:
        ok = np.zeros(rva.shape, bool)
        for va, size, rp in self.secs:
            inn = (rva >= va + 8) & (rva < va + size)
            if not inn.any():
                continue
            off = (rva[inn] - va + rp).astype(np.int64)
            m = self.mm
            b1, b2, b3, b5, b6 = m[off - 1], m[off - 2], m[off - 3], m[off - 5], m[off - 6]
            e8 = b5 == 0xE8
            ff_reg = (b2 == 0xFF) & ((b1 & 0xF8) == 0xD0)                        # call r
            ff_d8 = (b3 == 0xFF) & ((b2 & 0xF8) == 0x50) & ((b2 & 7) != 4)        # call [r+d8]
            ff_d32 = (b6 == 0xFF) & ((b5 == 0x15) | (((b5 & 0xF8) == 0x90) & ((b5 & 7) != 4)))  # [rip+d32] [r+d32]
            ok[inn] = e8 | ff_reg | ff_d8 | ff_d32
        return ok


class Unwinder:
    """x64 frame unwinding from the exe file's .pdata/.xdata (unwind info version 1, as LLVM writes it):
    PUSH_NONVOL, ALLOC_LARGE/SMALL, SET_FPREG, SAVE_NONVOL(_FAR), XMM saves (skipped), chained info.
    Partial prologs are honoured for the leaf frame; a PC inside an epilog is unwound as if past it."""

    def __init__(self, exe: Path):
        b = exe.read_bytes()[:4096]
        pe = struct.unpack_from('<I', b, 0x3C)[0]
        n = struct.unpack_from('<H', b, pe + 6)[0]
        opt = pe + 24
        o = opt + struct.unpack_from('<H', b, pe + 20)[0]
        exc_rva, exc_size = struct.unpack_from('<II', b, opt + 112 + 3 * 8)   # PE32+ data directory 3
        self.secs = []
        for _ in range(n):
            vs, va, rs, rp = struct.unpack_from('<IIII', b, o + 8)
            self.secs.append((va, max(vs, rs), rp))
            o += 40
        self.mm = np.memmap(exe, dtype=np.uint8, mode='r')
        p = np.frombuffer(self.mm, dtype=np.uint32, count=exc_size // 4, offset=self.off(exc_rva)).reshape(-1, 3)
        self.begin, self.end, self.uw = p[:, 0].copy(), p[:, 1].copy(), p[:, 2].copy()
        self.cache: dict[int, tuple] = {}
        self.bad = 0

    def off(self, rva: int) -> int:
        for va, size, rp in self.secs:
            if va <= rva < va + size:
                return rp + rva - va
        raise ValueError(rva)

    def info(self, uw: int):
        """[(prolog offset, op, a, b)] in unwind order, frame register, frame offset."""
        hit = self.cache.get(uw)
        if hit is not None:
            return hit
        o = self.off(uw & ~1)
        m = self.mm
        vf, _, cnt, fr = int(m[o]), int(m[o + 1]), int(m[o + 2]), int(m[o + 3])
        if vf & 7 != 1:
            self.cache[uw] = None
            return None
        slots = [int(m[o + 4 + 2 * i]) | int(m[o + 5 + 2 * i]) << 8 for i in range(cnt)]
        ops, i = [], 0
        while i < cnt:
            co, op, inf = slots[i] & 0xFF, (slots[i] >> 8) & 0xF, slots[i] >> 12
            if op == 0:
                ops.append((co, 'push', inf, 0)); i += 1
            elif op == 1:
                if inf == 0:
                    ops.append((co, 'alloc', slots[i + 1] * 8, 0)); i += 2
                else:
                    ops.append((co, 'alloc', slots[i + 1] | slots[i + 2] << 16, 0)); i += 3
            elif op == 2:
                ops.append((co, 'alloc', inf * 8 + 8, 0)); i += 1
            elif op == 3:
                ops.append((co, 'setfp', 0, 0)); i += 1
            elif op == 4:
                ops.append((co, 'save', inf, slots[i + 1] * 8)); i += 2
            elif op == 5:
                ops.append((co, 'save', inf, slots[i + 1] | slots[i + 2] << 16)); i += 3
            elif op in (6, 8):
                i += 2
            elif op in (7, 9):
                i += 3
            elif op == 10:
                ops.append((co, 'mach', inf, 0)); i += 1
            else:
                self.cache[uw] = None
                return None
        if (vf >> 3) & 4:   # chained: the parent's codes follow, all of them executed
            co = o + 4 + 2 * ((cnt + 1) & ~1)
            parent = int(np.frombuffer(m, dtype=np.uint32, count=3, offset=co)[2])
            pi = self.info(parent)
            if pi is None:
                self.cache[uw] = None
                return None
            ops += [(0, k, a, b2) for _, k, a, b2 in pi[0]]
        res = (ops, fr & 0xF, fr >> 4)
        self.cache[uw] = res
        return res

    def step(self, rva: int, rsp: int, regs: dict, read, leaf: bool):
        """Caller's (return address, rsp) for a frame at image RVA rva, or None."""
        i = int(np.searchsorted(self.begin, rva, side='right')) - 1
        if i < 0 or rva >= self.end[i]:
            ra = read(rsp)                     # leaf function without unwind data
            return None if ra is None else (ra, rsp + 8)
        inf = self.info(int(self.uw[i]))
        if inf is None:
            self.bad += 1
            return None
        ops, fpreg, fpoff = inf
        pc_off = rva - int(self.begin[i])
        est = rsp
        if any(k == 'setfp' and (not leaf or co <= pc_off) for co, k, _, _ in ops):
            if fpreg not in regs:
                return None
            est = regs[fpreg] - fpoff * 16
        for co, k, a, b2 in ops:
            if leaf and co > pc_off:
                continue                       # not yet executed in a partial prolog
            if k == 'push':
                v = read(rsp)
                if v is None:
                    return None
                regs[a] = v
                rsp += 8
            elif k == 'alloc':
                rsp += a
            elif k == 'setfp':
                rsp = est
            elif k == 'save':
                v = read(est + b2)
                if v is not None:
                    regs[a] = v
            elif k == 'mach':
                ra = read(rsp + (16 if a else 8))
                nsp = read(rsp + (40 if a else 32))
                return None if ra is None or nsp is None else (ra, nsp)
        ra = read(rsp)
        return None if ra is None else (ra, rsp + 8)


class _TBI(ctypes.Structure):
    _fields_ = [('ExitStatus', ctypes.c_long), ('TebBaseAddress', ctypes.c_void_p),
                ('UniqueProcess', ctypes.c_void_p), ('UniqueThread', ctypes.c_void_p),
                ('AffinityMask', ctypes.c_size_t), ('Priority', ctypes.c_long), ('BasePriority', ctypes.c_long)]


def stack_base(hproc, hthread) -> int:
    tbi = _TBI()
    nt = ctypes.windll.ntdll
    if nt.NtQueryInformationThread(hthread, 0, ctypes.byref(tbi), ctypes.sizeof(tbi), None) != 0:
        return 0
    v = ctypes.c_uint64()
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(hproc, ctypes.c_void_p((tbi.TebBaseAddress or 0) + 8), ctypes.byref(v), 8,
                                 ctypes.byref(got)):
        return 0
    return v.value


def sample(pid: int, seconds: float, hz: float, nthreads: int, symbols: SymbolMap) -> dict:
    base = main_module_base(pid)
    k32.OpenProcess.restype = wt.HANDLE
    hproc = k32.OpenProcess(0x0410, False, pid)   # VM_READ | QUERY_INFORMATION
    isize = image_size(pid, base)
    modules = process_modules(pid)
    modmap = ModuleMap(modules)
    calls = CallCheck(Path(modules[0]['path']))
    unw = Unwinder(Path(modules[0]['path']))
    broken = Counter()
    buf = ctypes.create_string_buffer(STACK_MAX)
    k32.OpenThread.restype = wt.HANDLE
    handles = {}
    for tid in thread_ids(pid):
        h = k32.OpenThread(THREAD_ALL, False, tid)
        if h:
            handles[tid] = h
    cpu0 = {tid: thread_cpu(h) for tid, h in handles.items()}
    time.sleep(0.5)
    busy = sorted(handles, key=lambda t: -(thread_cpu(handles[t]) - cpu0[t]))[:nthreads]
    sbase = {t: stack_base(hproc, handles[t]) for t in busy}
    raw = (ctypes.c_char * (CTX_SIZE + 16))()
    addr = (ctypes.addressof(raw) + 15) & ~15
    incl = {t: Counter() for t in busy}
    # SAMPLE_FOCUS=<symbol substring>: the functions found below it on the stack (its runtime callees,
    # indirect calls included), counted once a sample, and how many samples had it at all.
    focus = os.environ.get('SAMPLE_FOCUS') or ''
    focus_below = {t: Counter() for t in busy}
    focus_above = {t: Counter() for t in busy}   # the 5 frames above it, as one call path
    focus_n = Counter()
    selfc = {t: Counter() for t in busy}
    riprva = {t: Counter() for t in busy}   # running leaf RVAs (instruction-level hot spots)
    nrun = Counter()
    nwait = Counter()
    inclw = {t: Counter() for t in busy}
    selfw = {t: Counter() for t in busy}
    nall = Counter()
    depth = Counter()
    sym_cache: dict[int, str] = {}

    def sym(rva: int) -> str:
        s = sym_cache.get(rva)
        if s is None:
            s = sym_cache[rva] = symbols.lookup(rva)
        return s

    t_end = time.perf_counter() + seconds
    cpu_a = {t: thread_cpu(handles[t]) for t in busy}
    t_a = time.perf_counter()
    got = ctypes.c_size_t()
    while time.perf_counter() < t_end:
        for t in busy:
            h = handles[t]
            if k32.SuspendThread(h) == 0xFFFFFFFF:
                continue
            ctypes.c_uint32.from_address(addr + CTX_FLAGS).value = CONTEXT_CONTROL | 2   # | CONTEXT_INTEGER
            ok = k32.GetThreadContext(h, ctypes.c_void_p(addr))
            rip = ctypes.c_uint64.from_address(addr + CTX_RIP).value if ok else 0
            rsp = ctypes.c_uint64.from_address(addr + CTX_RSP).value if ok else 0
            regs = {r: ctypes.c_uint64.from_address(addr + 0x78 + 8 * r).value for r in range(16) if r != 4}
            n = 0
            if rsp and sbase[t] > rsp:
                n = min(STACK_MAX, sbase[t] - rsp) & ~7
                if not k32.ReadProcessMemory(hproc, ctypes.c_void_p(rsp), buf, n, ctypes.byref(got)):
                    n = 0
            k32.ResumeThread(h)
            if not rip:
                continue
            nall[t] += 1
            rva = rip - base
            leaf = sym(rva) if 0 <= rva < isize else modmap.label(rip)
            waiting = any(w in leaf for w in WAIT_WORDS)
            if waiting:
                nwait[t] += 1
                selfw[t][leaf] += 1
            else:
                nrun[t] += 1
                selfc[t][leaf] += 1
                riprva[t][rva] += 1
            names = {leaf}
            chain = [leaf]
            if n:
                def read(a, rsp0=rsp, n=n):
                    k = a - rsp0
                    return struct.unpack_from('<Q', buf, k)[0] if 0 <= k <= n - 8 else None
                cur, csp, is_leaf = rva, rsp, True
                if not 0 <= rva < isize:
                    # leaf in a system DLL: [rsp] if it is a return into the image, else the first one on the stack
                    v = np.frombuffer(buf, dtype=np.uint64, count=n // 8)
                    j = np.nonzero((v >= base) & (v < base + isize))[0]
                    if j.size:
                        j = j[calls.mask((v[j] - np.uint64(base)).astype(np.int64))]
                    if j.size:
                        cur, csp, is_leaf = int(v[j[0]]) - base, rsp + 8 * int(j[0]) + 8, False
                    else:
                        cur = -1
                frames = 0
                while frames < 800 and 0 <= cur < isize:
                    s_ = sym(cur if is_leaf else cur - 1)
                    names.add(s_)
                    chain.append(s_)
                    r = unw.step(cur, csp, regs, read, is_leaf)
                    is_leaf = False
                    frames += 1
                    if r is None:
                        broken[t] += 1
                        break
                    cur, csp = r[0] - base, r[1]
                if not waiting:
                    depth[t] += frames
            if focus:
                k_ = next((j for j, s_ in enumerate(chain) if focus in s_), None)
                if k_ is not None:
                    focus_n[t] += 1
                    for s_ in set(chain[:k_]):
                        focus_below[t][s_] += 1
                    focus_above[t][' <- '.join(chain[k_:k_ + 6])] += 1
            for nm in names:
                (inclw if waiting else incl)[t][nm] += 1
        time.sleep(1.0 / hz)
    dt_ = time.perf_counter() - t_a
    out = {'pid': pid, 'seconds': round(dt_, 2), 'image_base': f'0x{base:X}',
           'threads': [{'tid': t, 'cpu_fraction': round((thread_cpu(handles[t]) - cpu_a[t]) / dt_, 3),
                        'samples': nall[t], 'running': nrun[t],
                        'mean_frames': round(depth[t] / max(1, nrun[t]), 1),
                        'broken_walks': broken[t], 'bad_unwind_info': unw.bad,
                        'incl': [[nm, c, round(c / max(1, nrun[t]), 4)] for nm, c in incl[t].most_common(200)],
                        'self': [[nm, c, round(c / max(1, nrun[t]), 4)] for nm, c in selfc[t].most_common(80)],
                        'waiting': nwait[t],
                        'incl_wait': [[nm, c, round(c / max(1, nwait[t]), 4)] for nm, c in inclw[t].most_common(200)],
                        'self_wait': [[nm, c, round(c / max(1, nwait[t]), 4)] for nm, c in selfw[t].most_common(40)],
                        # every function seen while running, for a link order file (tools/make_order.py)
                        'incl_all': dict(incl[t]), 'self_all': dict(selfc[t]), 'rip_rva': [[r, c] for r, c in riprva[t].most_common(3000)],
                        'focus': focus, 'focus_samples': focus_n[t],
                        'focus_below': [[nm, c] for nm, c in focus_below[t].most_common(300)],
                        'focus_above': [[nm, c] for nm, c in focus_above[t].most_common(20)]}
                       for t in busy]}
    for h in handles.values():
        k32.CloseHandle(h)
    k32.CloseHandle(hproc)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--map', type=Path)
    ap.add_argument('--seconds', type=float, default=30)
    ap.add_argument('--hz', type=float, default=150)
    ap.add_argument('--threads', type=int, default=3)
    ap.add_argument('--json', type=Path)
    a = ap.parse_args(argv)
    res = sample(a.pid, a.seconds, a.hz, a.threads, SymbolMap(a.map))
    if a.json:
        a.json.write_text(json.dumps(res, indent=1))
    for t in res['threads']:
        print(f"thread {t['tid']}: {t['cpu_fraction']:.0%} CPU, {t['samples']} samples, {t['running']} running, "
              f"{t['mean_frames']} frames a sample, {t['broken_walks']} broken walks")
        for nm, c, f in t['incl'][:25]:
            print(f'    {f:6.1%}  {nm}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
