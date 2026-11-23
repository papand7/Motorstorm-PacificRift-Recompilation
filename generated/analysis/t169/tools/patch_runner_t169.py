MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T169 continuation: one-shot edit of make_runner_t169.py: no RSXI in D2/F2, active counters, smaller diag bound, clean import edit."""
p = (MS_ROOT + r'\generated\analysis\t169\tools\make_runner_t169.py')
s = open(p, encoding='utf-8').read()


def sub(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)


i0, i1 = s.index('src = src.replace("import ", "import ctypes'), s.index('sub("RSXI_AT_S = 10.0')
s = s[:i0] + 'sub("import hashlib, json, os,", "import ctypes, hashlib, json, os,")\n' + s[i1:]
sub('''sub("'RSXI_COUNT': '3', 'RSXI_STRIDE': '120',", "'RSXI_COUNT': '1', 'RSXI_STRIDE': '120',")\n''',
    '''# D2/F2: no RSXI. It tripped the 4 s Present timeout in D1 and F1, and that timeout now cancels the sequence.
j0, j1 = src.index("        'RSXI': '1', 'RSXI_DIR'"), src.index("        'RSX_XFER_LOG': '48'")
src = src[:j0] + src[j1:]\n''')
sub("""'RSX_VISUAL_DIAG_MAX': '3000',\\n")""", """'RSX_VISUAL_DIAG_MAX': '2000', 'RSX_VISUAL_ACTIVE': '1',\\n")""")
sub('self.now() > 60 and not', 'self.now() > 90 and not')
sub('within 60 s', 'within 90 s')
sub('RSX_VISUAL_PROFILE per arm', 'explicit switches per arm (D2/F2), stop conditions on log lines')
sub('one RSXI frame last (race entry + 25 s, or host 190 s', 'no RSXI; RSX_VISUAL_DIAG lines from race entry + 25 s (or host 190 s')
open(p, 'w', encoding='utf-8').write(s)
