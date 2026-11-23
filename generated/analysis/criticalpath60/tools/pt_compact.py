#!/usr/bin/env python3
"""Compact a [PT] trace (grep'd lines) into TSV: t tid ev fn lr dur r3 r4 extra(m[...] pairs).
usage: pt_compact.py pt_lines.txt out.tsv   (private: game-derived; keep under generated/ or D:)"""
import re, sys
rx = re.compile(r'\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=(\w+) lr=(\w+)(.*)')
kvx = re.compile(r'(\S+?)=(\S+)')
with open(sys.argv[1], encoding='latin-1') as f, open(sys.argv[2], 'w') as o:
    for l in f:
        m = rx.match(l)
        if not m: continue
        kv = dict(kvx.findall(m.group(6)))
        fn = kv.get('fn', m.group(4)).upper().lstrip('0')
        ex = ' '.join(f'{k}={v}' for k, v in kv.items() if k.startswith('m[') and v != '--')
        o.write(f"{m.group(1)}\t{m.group(2)}\t{m.group(3)}\t{fn}\t{m.group(5).upper().lstrip('0')}\t{kv.get('dur_us','')}\t{kv.get('r3','')}\t{kv.get('r4','')}\t{ex}\n")
