"""T162: tally texture bindings in RSXI events.jsonl (enabled units only: control0 bit 31).
Groups by (fmt, cube, mips>1, src, remap) and lists the fragment programs that fetch cube maps.
usage: python tex_tally_t162.py <rsxi_dir> [...]"""
import collections, glob, json, os, sys


def events(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                pass


def main(dirs):
    by_fmt = collections.Counter()
    cube_fp = collections.defaultdict(collections.Counter)
    remap = collections.Counter()
    draws = 0
    for d in dirs:
        for p in glob.glob(os.path.join(d, 'frames', '*', 'events.jsonl')):
            for e in events(p):
                if e.get('e') != 'draw':
                    continue
                draws += 1
                fp = e.get('guest', {}).get('fp')
                for t in e.get('tex', []):
                    r = t.get('req', {})
                    if 'control0' in r and not int(r['control0'], 16) >> 31:
                        continue
                    fmt = r.get('fmt')
                    key = (fmt, 'cube' if r.get('cube') else '2d', 'mips' if r.get('mips', 1) > 1 else '1',
                           t.get('src'))
                    by_fmt[key] += 1
                    remap[(fmt, r.get('remap'))] += 1
                    if r.get('cube'):
                        cube_fp[(fmt, r.get('w'), r.get('mips'))][fp] += 1
    print('draws', draws)
    for k, v in sorted(by_fmt.items(), key=lambda kv: -kv[1]):
        print('%-6s %-4s %-4s %-14s %d' % (k + (v,)))
    print('-- remaps')
    for k, v in sorted(remap.items(), key=lambda kv: -kv[1]):
        print(k, v)
    print('-- cube maps (fmt, size, mips) -> fp programs')
    for k, c in sorted(cube_fp.items()):
        print(k, dict(c.most_common(8)))


if __name__ == '__main__':
    main(sys.argv[1:])
