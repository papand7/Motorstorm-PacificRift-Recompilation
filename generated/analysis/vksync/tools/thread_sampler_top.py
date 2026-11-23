# vksync copy of t187 thread_sampler.py: 80 entries per thread instead of 15.
#!/usr/bin/env python3
"""Sampling profiler for a running native port (Windows x64, no debugger).

Suspends the busiest threads of a process, reads their instruction pointer
with GetThreadContext, resumes them, and histograms the samples by function.
Symbols come from a link map (lld-link /MAP or link.exe /MAP), so a Release
build needs no debug info:

  python tools/thread_sampler.py --pid 1234 --map game.map [--seconds 20] [--hz 200]
                                 [--threads 6] [--json out.json]

Each sample stops one thread for a few microseconds. That is negligible for
throughput but not free; profile a separate run from the one you time.
"""
from __future__ import annotations

import argparse
import bisect
import ctypes
import ctypes.wintypes as wt
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

k32 = ctypes.windll.kernel32 if sys.platform == 'win32' else None
THREAD_ALL = 0x0002 | 0x0008 | 0x0040 | 0x0800   # SUSPEND_RESUME | GET_CONTEXT | QUERY_INFORMATION | LIMITED
CONTEXT_CONTROL = 0x00100001
CTX_SIZE, CTX_FLAGS, CTX_RSP, CTX_RIP = 1232, 0x30, 0x98, 0xF8
STACK_SCAN = 1024   # bytes scanned for the first in-image return address


class _FT(ctypes.Structure):
    _fields_ = [('lo', wt.DWORD), ('hi', wt.DWORD)]


class _TE32(ctypes.Structure):
    _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD), ('th32ThreadID', wt.DWORD),
                ('th32OwnerProcessID', wt.DWORD), ('tpBasePri', ctypes.c_long),
                ('tpDeltaPri', ctypes.c_long), ('dwFlags', wt.DWORD)]


def thread_ids(pid: int) -> list[int]:
    snap = k32.CreateToolhelp32Snapshot(0x4, 0)
    te = _TE32(); te.dwSize = ctypes.sizeof(te)
    out = []
    ok = k32.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid:
            out.append(te.th32ThreadID)
        ok = k32.Thread32Next(snap, ctypes.byref(te))
    k32.CloseHandle(snap)
    return out


def thread_cpu(h) -> float:
    c, e, k, u = _FT(), _FT(), _FT(), _FT()
    if not k32.GetThreadTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
        return 0.0
    return (((k.hi << 32) | k.lo) + ((u.hi << 32) | u.lo)) / 1e7


def main_module_base(pid: int) -> int:
    k32.OpenProcess.restype = wt.HANDLE
    hp = k32.OpenProcess(0x0400 | 0x0010, False, pid)
    mods = (wt.HMODULE * 1)()
    need = wt.DWORD()
    ctypes.windll.psapi.EnumProcessModulesEx(hp, mods, ctypes.sizeof(mods), ctypes.byref(need), 0x03)
    k32.CloseHandle(hp)
    return mods[0] or 0


class SymbolMap:
    """RVA -> symbol from a link map ('0001:000abc  name  0000000140abc  f  obj' lines,
    or lld's 'Address Size Align Out In Symbol' layout)."""

    def __init__(self, path: Path | None, image_base: int = 0x140000000):
        self.addrs: list[int] = []
        self.names: list[str] = []
        if not path:
            return
        rx_msvc = re.compile(r'^\s*[0-9a-fA-F]{4}:[0-9a-fA-F]{8}\s+(\S+)\s+([0-9a-fA-F]{8,16})\s')
        rx_lld = re.compile(r'^\s*([0-9a-fA-F]{8,16})\s+([0-9a-fA-F]+)\s+\d+\s+(\S.*)$')
        pairs = []
        for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
            m = rx_msvc.match(line)
            if m:
                pairs.append((int(m.group(2), 16) - image_base, m.group(1)))
                continue
            m = rx_lld.match(line)
            if m:
                name = m.group(3).strip()
                if name and not name.startswith(('.', '<', '*')) and ':(' not in name and '.obj' not in name \
                        and '.lib(' not in name:
                    pairs.append((int(m.group(1), 16) - image_base, name))
        pairs.sort()
        self.addrs = [a for a, _ in pairs]
        self.names = [n for _, n in pairs]

    def lookup(self, rva: int) -> str:
        i = bisect.bisect_right(self.addrs, rva) - 1
        if i < 0:
            return f'rva+0x{rva:X}'
        return self.names[i]


def pe_exports(path: str) -> list[tuple[int, str]]:
    """Sorted (rva, name) of a PE file's named exports; [] if unreadable."""
    import struct
    try:
        b = Path(path).read_bytes()
        pe = struct.unpack_from('<I', b, 0x3C)[0]
        nsec, optsz = struct.unpack_from('<H', b, pe + 6)[0], struct.unpack_from('<H', b, pe + 20)[0]
        opt = pe + 24
        exp_rva = struct.unpack_from('<I', b, opt + 112)[0]
        secs = [struct.unpack_from('<8sIIII', b, opt + optsz + 40 * i) for i in range(nsec)]

        def off(rva):
            for _, vs, va, rs, ro in secs:
                if va <= rva < va + max(vs, rs):
                    return rva - va + ro
            raise ValueError(rva)
        e = off(exp_rva)
        nfun, nnam, af, an, ao = struct.unpack_from('<IIIII', b, e + 20)
        out = []
        for i in range(nnam):
            s = off(struct.unpack_from('<I', b, off(an) + 4 * i)[0])
            o = struct.unpack_from('<H', b, off(ao) + 2 * i)[0]
            out.append((struct.unpack_from('<I', b, off(af) + 4 * o)[0],
                        b[s:b.index(b'\0', s)].decode('latin1')))
        return sorted(out)
    except (OSError, ValueError, struct.error):
        return []


class ModuleMap:
    """Absolute address -> 'module+0xRVA (near export+0xOFF)' for samples outside
    the main image. System DLL bases are fixed per boot, not per process, so a
    saved module list also resolves addresses from an earlier run of the same
    boot. The export is only the nearest NAMED one at or below the address: a
    non-exported internal function shows as an offset past its predecessor."""

    def __init__(self, modules: list[dict]):
        self.mods = sorted(modules, key=lambda m: m['base'])
        self._exports: dict[str, list] = {}

    def label(self, addr: int) -> str:
        i = bisect.bisect_right([m['base'] for m in self.mods], addr) - 1
        if i < 0 or addr >= self.mods[i]['base'] + self.mods[i]['size']:
            return f'outside image 0x{addr:X}'
        m = self.mods[i]
        rva = addr - m['base']
        ex = self._exports.get(m['path'])
        if ex is None:
            ex = self._exports[m['path']] = pe_exports(m['path']) if m.get('path') else []
        j = bisect.bisect_right([a for a, _ in ex], rva) - 1
        near = f' (near {ex[j][1]}+0x{rva - ex[j][0]:X})' if j >= 0 else ''
        return f"{m['name']}+0x{rva:X}{near}"


def process_modules(pid: int) -> list[dict]:
    """Every module loaded in the process: name, path, base, size."""
    class _MI(ctypes.Structure):
        _fields_ = [('base', ctypes.c_void_p), ('size', wt.DWORD), ('entry', ctypes.c_void_p)]
    psapi = ctypes.windll.psapi
    k32.OpenProcess.restype = wt.HANDLE
    hp = k32.OpenProcess(0x0400 | 0x0010, False, pid)
    mods = (wt.HMODULE * 1024)()
    need = wt.DWORD()
    out = []
    if psapi.EnumProcessModulesEx(hp, mods, ctypes.sizeof(mods), ctypes.byref(need), 0x03):
        for h in mods[:min(1024, need.value // ctypes.sizeof(wt.HMODULE))]:
            mi, buf = _MI(), ctypes.create_unicode_buffer(520)
            if not psapi.GetModuleInformation(hp, wt.HMODULE(h), ctypes.byref(mi), ctypes.sizeof(mi)):
                continue
            psapi.GetModuleFileNameExW(hp, wt.HMODULE(h), buf, 520)
            out.append(dict(name=Path(buf.value).name, path=buf.value,
                            base=mi.base or 0, size=mi.size))
    k32.CloseHandle(hp)
    return out


def image_size(pid: int, base: int) -> int:
    hp = k32.OpenProcess(0x0400 | 0x0010, False, pid)
    hdr = (ctypes.c_char * 0x400)()
    n = ctypes.c_size_t()
    k32.ReadProcessMemory(hp, ctypes.c_void_p(base), hdr, 0x400, ctypes.byref(n))
    k32.CloseHandle(hp)
    pe = int.from_bytes(hdr[0x3C:0x40], 'little')
    return int.from_bytes(hdr[pe + 0x50:pe + 0x54], 'little')


def sample(pid: int, seconds: float, hz: float, nthreads: int, symbols: SymbolMap) -> dict:
    """Outside-image samples (system DLLs) are also attributed to the first
    return address into the image found on the stack -- a heuristic scan, so
    'caller' names are likely, not certain."""
    base = main_module_base(pid)
    k32.OpenProcess.restype = wt.HANDLE
    hproc = k32.OpenProcess(0x0010, False, pid)
    isize = image_size(pid, base)
    modules = process_modules(pid)
    modmap = ModuleMap(modules)
    stk = (ctypes.c_uint64 * (STACK_SCAN // 8))()
    callers = Counter()
    k32.OpenThread.restype = wt.HANDLE
    handles = {}
    for tid in thread_ids(pid):
        h = k32.OpenThread(THREAD_ALL, False, tid)
        if h:
            handles[tid] = h
    cpu0 = {tid: thread_cpu(h) for tid, h in handles.items()}
    time.sleep(0.5)
    busy = sorted(handles, key=lambda t: -(thread_cpu(handles[t]) - cpu0[t]))[:nthreads]
    raw = (ctypes.c_char * (CTX_SIZE + 16))()
    addr = (ctypes.addressof(raw) + 15) & ~15
    per_thread: dict[int, Counter] = {t: Counter() for t in busy}
    total = Counter()
    n = 0
    t_end = time.perf_counter() + seconds
    cpu_a = {t: thread_cpu(handles[t]) for t in busy}
    t_a = time.perf_counter()
    while time.perf_counter() < t_end:
        for t in busy:
            h = handles[t]
            if k32.SuspendThread(h) == 0xFFFFFFFF:
                continue
            ctypes.c_uint32.from_address(addr + CTX_FLAGS).value = CONTEXT_CONTROL
            ok = k32.GetThreadContext(h, ctypes.c_void_p(addr))
            rip = ctypes.c_uint64.from_address(addr + CTX_RIP).value if ok else 0
            rsp = ctypes.c_uint64.from_address(addr + CTX_RSP).value if ok else 0
            rva = rip - base
            caller = None
            if rip and not 0 <= rva < isize and rsp:
                got = ctypes.c_size_t()
                if k32.ReadProcessMemory(hproc, ctypes.c_void_p(rsp), stk, STACK_SCAN, ctypes.byref(got)):
                    for v in stk:
                        if base <= v < base + isize:
                            caller = symbols.lookup(v - base)
                            break
            k32.ResumeThread(h)
            if not rip:
                continue
            name = symbols.lookup(rva) if 0 <= rva < isize else modmap.label(rip)
            if caller:
                callers[f'{name} <- {caller}'] += 1
                name = f'{name} <- {caller}'
            per_thread[t][name] += 1
            total[name] += 1
            n += 1
        time.sleep(1.0 / hz)
    dt_ = time.perf_counter() - t_a
    out = {'pid': pid, 'seconds': round(dt_, 2), 'samples': n, 'image_base': f'0x{base:X}',
           'modules': [dict(m, base=f"0x{m['base']:X}") for m in modules],
           'threads': [{'tid': t, 'cpu_fraction': round((thread_cpu(handles[t]) - cpu_a[t]) / dt_, 3),
                        'samples': sum(per_thread[t].values()),
                        'top': [[name, c, round(c / max(1, sum(per_thread[t].values())), 3)]
                                for name, c in per_thread[t].most_common(80)]} for t in busy],
           'top': [[name, c, round(c / max(1, n), 3)] for name, c in total.most_common(40)]}
    for h in handles.values():
        k32.CloseHandle(h)
    k32.CloseHandle(hproc)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--map', type=Path)
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--hz', type=float, default=200)
    ap.add_argument('--threads', type=int, default=6)
    ap.add_argument('--json', type=Path)
    a = ap.parse_args(argv)
    if sys.platform != 'win32':
        print('Windows only', file=sys.stderr)
        return 1
    res = sample(a.pid, a.seconds, a.hz, a.threads, SymbolMap(a.map))
    if a.json:
        a.json.write_text(json.dumps(res, indent=1))
    print(f"{res['samples']} samples over {res['seconds']} s")
    for t in res['threads']:
        print(f"thread {t['tid']}: {t['cpu_fraction']:.0%} CPU, {t['samples']} samples")
        for name, c, f in t['top'][:8]:
            print(f'    {f:6.1%}  {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
