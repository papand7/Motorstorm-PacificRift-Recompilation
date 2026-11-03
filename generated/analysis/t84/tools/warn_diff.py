"""T84: compare the warning/error multisets of two compile logs written by compile_tu.py.
Locations (file(line,col)) are reduced to the file's base name; tree names are masked.
Usage: py -3 -I warn_diff.py <base log> <new log>"""
import collections, re, sys

LOC = re.compile(r'([^\\/(\s]+\.[ch])\(\d+,\d+\): (warning|error): (.*)')


def load(path):
    c = collections.Counter()
    for line in open(path, encoding='utf-8', errors='replace'):
        m = LOC.search(line)
        if m:
            c[(m.group(1), m.group(2), re.sub(r'ps3recomp-t\d+[a-z]*', 'TREE', m.group(3)))] += 1
    return c


a, b = load(sys.argv[1]), load(sys.argv[2])
errs = sum(v for k, v in b.items() if k[1] == 'error')
print(f'{sys.argv[2]}: base {sum(a.values())} diagnostics, new {sum(b.values())}, errors {errs}')
for k in sorted(b - a):
    print('  new :', k, (b - a)[k])
for k in sorted(a - b):
    print('  gone:', k, (a - b)[k])
