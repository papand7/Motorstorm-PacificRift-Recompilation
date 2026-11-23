import pickle,sys,collections
e,sc=pickle.load(open('cg.pkl','rb'))
rev=collections.defaultdict(set)
for a,bs in e.items():
    for b in bs: rev[b].add(a)
def up(t,depth=6,seen=None,ind=0):
    seen=seen or set()
    for c in sorted(rev.get(t,())):
        print(' '*ind+c, sorted(sc.get(c,()))[:4] if c in sc else '')
        if c in seen or ind>=depth*2: continue
        seen.add(c); up(c,depth,seen,ind+2)
if __name__=='__main__':
    for t in sys.argv[1:]:
        print('==',t); up(t,3)
