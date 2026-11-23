"""Bring a process's main window to the front and press keys (RPCS3's default keyboard pad: X = Cross,
C = Circle, Return = Start, arrows = d-pad).

usage: py -3 press.py <exe name> <key>[*count] [<key>[*count] ...] [--gap seconds] [--hold ms]
keys: x c v z return space up down left right, or a single letter."""
import ctypes, ctypes.wintypes as W, sys, time

u32 = ctypes.WinDLL('user32', use_last_error=True)
k32 = ctypes.WinDLL('kernel32')
VK = {'return': 0x0D, 'space': 0x20, 'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28, 'backspace': 0x08}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', W.WORD), ('wScan', W.WORD), ('dwFlags', W.DWORD), ('time', W.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('pad', ctypes.c_byte * 32)]
    _anonymous_ = ('u',)
    _fields_ = [('type', W.DWORD), ('u', _U)]


def window_of(exe):
    import subprocess, csv, io
    rows = csv.reader(io.StringIO(subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True,
                                                 text=True).stdout))
    pids = {int(r[1]) for r in rows if r and r[0].lower() == exe.lower()}
    found = []
    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(hwnd, _):
        p = W.DWORD(); u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value in pids and u32.IsWindowVisible(hwnd):
            b = ctypes.create_unicode_buffer(512); u32.GetWindowTextW(hwnd, b, 512)
            r = W.RECT(); u32.GetWindowRect(hwnd, ctypes.byref(r))
            found.append(((r.right - r.left) * (r.bottom - r.top), hwnd, b.value))
        return True
    u32.EnumWindows(cb, 0)
    return max(found)[1:] if found else (None, None)


def key(vk, hold):
    for flags in (0, 2):
        i = INPUT(type=1); i.ki = KEYBDINPUT(vk, u32.MapVirtualKeyW(vk, 0), flags | (1 if vk in (0x25, 0x26, 0x27, 0x28) else 0), 0, 0)
        u32.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))
        if not flags: time.sleep(hold / 1000)


def main():
    a = sys.argv[1:]; exe = a.pop(0); gap, hold = 1.5, 120
    if '--gap' in a: j = a.index('--gap'); gap = float(a[j + 1]); del a[j:j + 2]
    if '--hold' in a: j = a.index('--hold'); hold = float(a[j + 1]); del a[j:j + 2]
    hwnd, title = window_of(exe)
    if not hwnd: sys.exit('no window for ' + exe)
    u32.keybd_event(0x12, 0, 0, 0); u32.keybd_event(0x12, 0, 2, 0)   # Alt tap lets SetForegroundWindow work
    u32.SetForegroundWindow(hwnd); time.sleep(0.3)
    print('window:', title)
    for k in a:
        name, _, cnt = k.partition('*')
        vk = VK.get(name.lower(), ord(name.upper()) if len(name) == 1 else None)
        for _ in range(int(cnt or 1)):
            key(vk, hold); print('pressed', name); time.sleep(gap)


if __name__ == '__main__':
    main()
