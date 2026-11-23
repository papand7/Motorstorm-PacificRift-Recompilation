"""Per-thread CPU cycles of a running process, in windows, with the window title (RPCS3 puts its FPS there).

usage: py -3 thread_cycles.py <exe name> <seconds per window> <windows> <out.jsonl>
Each line: {"t": seconds, "title": window title, "threads": {"<tid> <name>": Mcycles in the window}}.
QueryThreadCycleTime counts only the cycles a thread ran (spinning included), as the port's [main-cyc]."""
import ctypes, ctypes.wintypes as W, json, sys, time

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
u32 = ctypes.WinDLL('user32')


class THREADENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', W.DWORD), ('cntUsage', W.DWORD), ('th32ThreadID', W.DWORD),
                ('th32OwnerProcessID', W.DWORD), ('tpBasePri', W.LONG), ('tpDeltaPri', W.LONG),
                ('dwFlags', W.DWORD)]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', W.DWORD), ('cntUsage', W.DWORD), ('th32ProcessID', W.DWORD),
                ('th32DefaultHeapID', ctypes.c_void_p), ('th32ModuleID', W.DWORD), ('cntThreads', W.DWORD),
                ('th32ParentProcessID', W.DWORD), ('pcPriClassBase', W.LONG), ('dwFlags', W.DWORD),
                ('szExeFile', W.WCHAR * 260)]


k32.CreateToolhelp32Snapshot.restype = W.HANDLE
k32.OpenThread.restype = W.HANDLE
k32.GetThreadDescription.argtypes = [W.HANDLE, ctypes.POINTER(W.LPWSTR)]
k32.QueryThreadCycleTime.argtypes = [W.HANDLE, ctypes.POINTER(ctypes.c_uint64)]


def find_pid(exe):
    snap = k32.CreateToolhelp32Snapshot(2, 0)
    e = PROCESSENTRY32W(); e.dwSize = ctypes.sizeof(e)
    ok = k32.Process32FirstW(snap, ctypes.byref(e)); pid = None
    while ok:
        if e.szExeFile.lower() == exe.lower(): pid = e.th32ProcessID
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return pid


handles = {}


def sample(pid):
    snap = k32.CreateToolhelp32Snapshot(4, 0)
    e = THREADENTRY32(); e.dwSize = ctypes.sizeof(e)
    ok = k32.Thread32First(snap, ctypes.byref(e)); out = {}
    while ok:
        if e.th32OwnerProcessID == pid:
            tid = e.th32ThreadID
            if tid not in handles:
                h = k32.OpenThread(0x0800, False, tid)
                if h: handles[tid] = h
            h = handles.get(tid)
            if h:
                c = ctypes.c_uint64(); k32.QueryThreadCycleTime(h, ctypes.byref(c))
                d = W.LPWSTR(); name = ''
                if k32.GetThreadDescription(h, ctypes.byref(d)) >= 0 and d.value:
                    name = d.value; k32.LocalFree(d)
                out['%d %s' % (tid, name)] = c.value
        ok = k32.Thread32Next(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return out


def title(pid):
    titles = []
    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(hwnd, _):
        p = W.DWORD(); u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(hwnd):
            b = ctypes.create_unicode_buffer(512); u32.GetWindowTextW(hwnd, b, 512)
            if b.value: titles.append(b.value)
        return True
    u32.EnumWindows(cb, 0)
    return ' || '.join(titles)


def main():
    exe, win, n, path = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    pid = find_pid(exe)
    if not pid: sys.exit('no process ' + exe)
    t0 = time.time(); prev = sample(pid)
    with open(path, 'a', encoding='utf-8') as f:
        for _ in range(n):
            time.sleep(win)
            cur = sample(pid)
            d = {k: round((v - prev.get(k, v)) / 1e6, 1) for k, v in cur.items()}
            d = {k: v for k, v in sorted(d.items(), key=lambda kv: -kv[1]) if v >= 1}
            f.write(json.dumps({'t': round(time.time() - t0, 1), 'title': title(pid), 'threads': d}) + '\n'); f.flush()
            prev = cur


if __name__ == '__main__':
    main()
