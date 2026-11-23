"""Remove the PS3_MAIN_PRIO experiment from port-vkgame/main.cpp (Kk37 -0.4 ms, Kk38 +2.6 ms: no win).
CRLF-safe; asserts every block it removes."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[4] / 'port-vkgame' / 'main.cpp'
s = p.read_bytes().decode('utf-8')
assert '\r\n' in s
s = s.replace('\r\n', '\n')


def cut(start, end_incl):
    global s
    a = s.index(start)
    b = s.index(end_incl, a) + len(end_incl)
    s = s[:a] + s[b:]


cut('#ifdef _WIN32\n/* PS3_MAIN_PRIO=1|ab', 'static DWORD s_main_tid;\n#endif\n\n')
cut('#ifdef _WIN32\n    const char* mp_env = getenv("PS3_MAIN_PRIO");', '    int mp_on = -1;\n#endif\n')
cut('#ifdef _WIN32\n        if (mp_thread) {', '                mp_on = want;\n            }\n        }\n#endif\n')
cut('#ifdef _WIN32\n    s_main_tid = GetCurrentThreadId();', '#endif\n')
assert 'MAIN_PRIO' not in s and 'mp_thread' not in s and 'mp_on' not in s and 's_main_tid' not in s
p.write_bytes(s.replace('\n', '\r\n').encode('utf-8'))
print('ok')
