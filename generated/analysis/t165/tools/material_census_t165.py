"""T165: read-only census of RSXI draw events: colour transfers, alpha, blend, depth, cull and texture
resolution of the draws on the main scene target, per capture.
usage: python material_census_t165.py <rsxi_dir> [...]   (--show-one prints one event)"""
import collections, glob, json, os, sys


def walk(d):
    for p in sorted(glob.glob(os.path.join(d, 'frames', '*', 'events.jsonl'))):
        for line in open(p, encoding='utf-8', errors='replace'):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get('e') == 'draw':
                yield e


def main(args):
    if args[0] == '--show-one':
        for e in walk(args[1]):
            if len(e.get('tex', [])) >= 3:
                print(json.dumps(e)[:6000])
                return
    for d in args:
        c = collections.Counter()
        exp = collections.Counter()
        gam = collections.Counter()
        src = collections.Counter()
        n = 0
        for e in walk(d):
            g = e.get('guest', {})
            n += 1
            for k in ('srgb_output', 'host_xfer', 'alpha_test', 'alpha_func', 'blend', 'blend_enable', 'cull_face', 'cull_enable',
                      'depth_test', 'depth_func', 'depth_write', 'stencil_test'):
                if k in g:
                    c[(k, str(g[k]))] += 1
                elif k in e:
                    c[(k, str(e[k]))] += 1
            for t in e.get('tex', []):
                r = t.get('req', {})
                exp[(t.get('unit'), r.get('fmt'), str(r.get('expand_mask')))] += 1
                gam[(t.get('unit'), str(r.get('gamma_mask')))] += 1
                src[str(t.get('src', t.get('resolved')))] += 1
        print('==', d, 'draws', n)
        for k, v in sorted(c.items()):
            print('  %6d %s=%s' % (v, *k))
        print('  expand nonzero:', [(k, v) for k, v in exp.most_common() if k[2] not in ('0', 'None')][:20])
        print('  gamma:', gam.most_common(14))
        print('  tex src:', src.most_common(12))


if __name__ == '__main__':
    main(sys.argv[1:])
