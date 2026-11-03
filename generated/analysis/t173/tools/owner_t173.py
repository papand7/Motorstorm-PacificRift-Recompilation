"""Print the enclosing function header of given 1-based line numbers. usage: owner_t173.py <file> <line>..."""
import re, sys

want = sorted(int(x) for x in sys.argv[2:])
hdr = re.compile(r'^void (?:__attribute__\(\(weak\)\) )?(\w+)\(ppu_context\* ctx\) \{')
cur, k = None, 0
with open(sys.argv[1], 'r', encoding='utf-8', errors='replace') as f:
    for n, l in enumerate(f, 1):
        m = hdr.match(l)
        if m:
            cur = (n, m.group(1))
        while k < len(want) and want[k] == n:
            print(want[k], '->', cur)
            k += 1
        if k >= len(want):
            break
