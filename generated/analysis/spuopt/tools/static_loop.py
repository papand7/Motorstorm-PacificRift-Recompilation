"""Conservative generation-time evaluation of bounded scalar store-only loops.

No guest execution is added at runtime: constants become guarded AOT store tables.
Unsupported instructions, loads, symbolic control flow or mixed bases refuse.
"""
import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Address:
    reg: int
    offset: int = 0

class Refuse(Exception): pass
MASK=0xffffffff
def signed(v): return v if v<0x80000000 else v-0x100000000
def add(a,b):
    if isinstance(a,Address) and isinstance(b,int): return Address(a.reg,a.offset+signed(b))
    if isinstance(b,Address) and isinstance(a,int): return add(b,a)
    if isinstance(a,int) and isinstance(b,int): return (a+b)&MASK
    raise Refuse()

def operation(op,a):
    if op=='spu_il': return a[0]&MASK
    if op=='spu_a': return add(*a)
    if op=='spu_ai': return add(*a)
    if op in ('spu_shlqbyi','spu_rotqbyi','spu_shlqbii','spu_rotqbii') and a[1]==0: return a[0]
    if not all(isinstance(v,int) for v in a): raise Refuse()
    if op=='spu_cgti': return MASK if signed(a[0])>signed(a[1]&MASK) else 0
    if op=='spu_ceq' or op=='spu_ceqi': return MASK if a[0]==(a[1]&MASK) else 0
    if op=='spu_selb': return ((a[0]&~a[2])|(a[1]&a[2]))&MASK
    if op=='spu_shli': return 0 if (a[1]&63)>31 else (a[0]<<(a[1]&63))&MASK
    if op=='spu_ori': return a[0]|(a[1]&MASK)
    raise Refuse()

def specialize(stmts,idiom,skip,slice_idx,carried,maybe,check,back,head,constants,cond_re):
    env={r:Address(r) for r in range(128)}
    env.update(constants)
    initial=env.copy()
    read_inputs=set()
    defined=set()
    changed=set()
    memory={}
    steps=0
    labels={s['lab']:i for i,s in enumerate(stmts) if s['kind']=='label'}
    def get(arg,values):
        m=re.fullmatch(r'R\[(\d+)\]',arg)
        if m:
            r=int(m[1])
            if r not in defined: read_inputs.add(r)
            return values[r]
        return int(arg,0)&MASK
    def op(s,values): return operation(s['op'],[get(a,values) for a in s['args']])
    def condition(c,values):
        m=cond_re.fullmatch(c)
        if not m: raise Refuse()
        v=get('R['+m[1]+']',values)
        if not isinstance(v,int): raise Refuse()
        if m[2]=='u16':v&=65535
        return (v==0) if m[3]=='==' else (v!=0)
    def addr(text):
        value=0
        for term in text.split(' + '):
            term=term.replace('._u32[0]','')
            value=add(value,get(term,env))
        return value
    try:
        for iteration in range(4096):
            test=env.copy()
            for j in sorted(slice_idx):test[stmts[j]['dst']]=op(stmts[j],test)
            if not condition(back['cond'],test): break
            i=0; pending={}
            while i<len(stmts)-1:
                s=stmts[i]; k=s['kind']
                if i in skip:
                    for w,(jr,jm,j) in idiom.items():
                        p=pending.setdefault(w,[None,None,None])
                        if i==jr:p[0]=addr(s['addr'])
                        elif i==jm:p[1]=add(get(s['args'][0],env),int(s['args'][1],0))
                        elif i==j:p[2]=get(s['args'][0],env)
                elif k=='op':
                    env[s['dst']]=op(s,env);defined.add(s['dst']);changed.add(s['dst'])
                elif k=='edge':
                    if s['cond'] is None or condition(s['cond'],env):
                        steps+=int(s['chain']);i=labels[s['lab']];continue
                elif k=='write':
                    if i not in idiom:raise Refuse()
                    a,m,v=pending[i]
                    if not isinstance(a,Address) or not isinstance(m,Address) or a.reg!=m.reg or not isinstance(v,int): raise Refuse()
                    jm=idiom[i][1]
                    size={'spu_cbd':1,'spu_chd':2,'spu_cwd':4}[stmts[jm]['op']]
                    off=(a.offset&~15)+(m.offset&(16-size))
                    for j,b in enumerate((v&((1<<(8*size))-1)).to_bytes(size,'big')):
                        memory[(a.reg,off+j)]=b
                elif k!='label':raise Refuse()
                i+=1
            steps+=int(back['chain'])
        else:raise Refuse()
        if iteration<8 or not memory:raise Refuse()
        bases={r for r,o in memory}
        if len(bases)!=1:raise Refuse()
        base=bases.pop();offsets=sorted(o for r,o in memory)
        if min(offsets)<0 or max(offsets)>=0x40000:raise Refuse()
        restore=(carried|maybe)&changed
        if any(not isinstance(env[r],int) for r in restore):raise Refuse()
        guards=['_ck',f'(R[{base}]._u32[0] & 15u) == 0',f'R[{base}]._u32[0] <= SPU_LS_MASK - {max(offsets)}u']
        for r in sorted(read_inputs):
            if isinstance(initial[r],int):guards.append(f'R[{r}]._u32[0] == {initial[r]}u')
        for r in sorted(check):
            guards += [f'R[{r}]._u32[0] == R[{r}]._u32[{lane}]' for lane in (1,2,3)]
        out=['/* AOT constant loop: exact last iteration retained. */','if ('+' && '.join(guards)+') {']
        groups=[]
        for off in offsets:
            if not groups or off!=groups[-1][-1]+1:groups.append([])
            groups[-1].append(off)
        for n,group in enumerate(groups):
            data=[memory[(base,o)] for o in group]
            if len(set(data))==1:
                out.append(f'    memset(ls + R[{base}]._u32[0] + {group[0]}u, {data[0]}, {len(data)});')
            else:
                out.append(f'    static const unsigned char table_{head}_{n}[] = {{'+','.join(map(str,data))+'};')
                out.append(f'    memcpy(ls + R[{base}]._u32[0] + {group[0]}u, table_{head}_{n}, {len(data)});')
        out += [f'    R[{r}] = spu_splat_u32({env[r]}u);' for r in sorted(restore)]
        out += [f'    nst += {steps}u;',f'    goto {head};','}']
        return out
    except (Refuse,KeyError,ValueError,TypeError):return []
