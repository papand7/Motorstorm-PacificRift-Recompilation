import sys,re,statistics as s
L=[l for l in open(sys.argv[1],errors='replace') if 'draw-split' in l][5:]
def m(k): return s.median(float(re.search(k+r'=([\d.]+)',l).group(1)) for l in L)
print(sys.argv[1], 'n=%d total %.2f emit %.2f count %.2f room %.2f rest %.2f' % (len(L), m('total_ms'), m('emit'), m('count'), m('room'), m('cb_rest')))
