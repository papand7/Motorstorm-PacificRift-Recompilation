"""Guarded AOT traces through constant-controlled native CFGs.

Only generation-time control decisions are folded. Vector instructions and the
original exit remain exact; scalar stores replace dead quad-insertion results.
"""
import re
from scalarize import R_ASSIGN,R_READ,R_WRITE,R_CHAIN,R_GOTO,R_LABEL,R_REG,R_COND,split_args,OPS,COPY0,MASKS
from static_loop import operation,Refuse,Address,add
PURE_OPS=set(OPS)|COPY0|set(MASKS)|{'spu_shufb','spu_cgt'}

def evaluate(op,args):
    if any(a is None for a in args):return None
    if op=='spu_cgt':
        signed=lambda x:x if x<0x80000000 else x-0x100000000
        return 0xffffffff if signed(args[0])>signed(args[1]) else 0
    if op=='spu_fsmbi' and args==[0]:return 0
    try:return operation(op,args)
    except (Refuse,TypeError,ValueError):return None

def definition(line):
    m=R_ASSIGN.fullmatch(line.strip())
    if not m:return None
    return int(m[1]),m[2],split_args(m[3])

def constant_args(args,values):
    out=[]
    for a in args:
        m=re.fullmatch(r'R\[(\d+)\]',a)
        try:out.append(values.get(int(m[1])) if m else int(a,0)&0xffffffff)
        except ValueError:out.append(None)
    return out

def address_plan(trace,hints):
    values={r:(hints[r] if isinstance(hints.get(r),int) else Address(r)) for r in range(128)}
    memory={};masks={}
    def argument(t):
        m=re.fullmatch(r'R\[(\d+)\]',t)
        return values[int(m[1])] if m else int(t,0)&0xffffffff
    def address(t):
        result=0
        for part in t.split(' + '):result=add(result,argument(part.replace('._u32[0]','')))
        return result
    try:
        for i,line in enumerate(trace):
            read=R_READ.fullmatch(line);write=R_WRITE.fullmatch(line);d=definition(line)
            if read or write:
                raw=read[2] if read else write[1]
                value=address(raw)
                if not isinstance(value,Address):return None
                memory[i]=(value,raw)
            if d:
                if d[1]=='spu_cwd':masks[i]=add(argument(d[2][0]),int(d[2][1],0))
                try:values[d[0]]=operation(d[1],[argument(a) for a in d[2]])
                except (Refuse,TypeError,ValueError,AttributeError):values[d[0]]=None
        bases={v.reg for v,raw in memory.values()}
        if len(bases)!=1:return None
        low=min(v.offset for v,raw in memory.values());high=max(v.offset for v,raw in memory.values())+15
        if low<0 or high>=0x40000:return None
        return bases.pop(),high,memory,masks
    except (Refuse,TypeError,ValueError,KeyError,AttributeError):return None

def lower_dead_insertions(trace,plan=None):
    # The full final architectural register state is observable.
    live=set(range(128));after=[]
    for line in reversed(trace):
        after.append(set(live))
        d=definition(line)
        if d:live.discard(d[0])
        live.update(map(int,R_REG.findall(line)))
        if d:live.discard(d[0]);live.update(map(int,R_REG.findall(','.join(d[2]))))
    after=list(reversed(after));out=[];defs={};captures={}
    for i,line in enumerate(trace):
        w=R_WRITE.fullmatch(line.strip())
        if w:
            src=int(w[2]);shuffle=defs.get(src)
            if src not in after[i] and shuffle and shuffle[1]=='spu_shufb':
                args=shuffle[2]
                if all(re.fullmatch(r'R\[\d+\]',a) for a in args):
                    v,x,m=[int(a[2:-1]) for a in args]
                    load=defs.get(x);mask=defs.get(m)
                    if load and load[1]=='load' and mask and mask[1]=='spu_cwd' and load[2]==w[1] and load[3]<shuffle[3] and mask[3]<shuffle[3]:
                        p,offset=mask[2]
                        # Operand/address definitions must remain unchanged.
                        involved=set(map(int,R_REG.findall(w[1]+p)))
                        start=min(load[3],mask[3],shuffle[3])
                        changed=set()
                        for middle in trace[start+1:i]:
                            d=definition(middle)
                            if d:changed.add(d[0])
                        if not (involved&changed) and not any(R_WRITE.fullmatch(t.strip()) for t in trace[load[3]+1:i]):
                            pos=f'((({w[1]}) & SPU_LS_MASK & ~15u) + (({p}._u32[0] + ({offset})) & 12u))'
                            if plan:
                                base,high,memory,masks=plan
                                load_address=memory[load[3]][0];mask_address=masks.get(mask[3])
                                if isinstance(mask_address,Address) and mask_address.reg==base:
                                    pos=f'R[{base}]._u32[0] + {(load_address.offset&~15)+(mask_address.offset&12)}u'
                            captures.setdefault(shuffle[3],[]).append(f'const uint32_t trace_word_{i}=R[{v}]._u32[0];')
                            out.append(f'{{ uint32_t word=__builtin_bswap32(trace_word_{i}); memcpy(ls + {pos}, &word, 4); }}')
                            continue
        out.append(line)
        read=R_READ.fullmatch(line.strip())
        d=definition(line)
        if read:defs[int(read[1])]=(int(read[1]),'load',read[2],i)
        elif d:defs[d[0]]=(*d,i)
    # Remove now-dead pure definitions. Keep every memory read until proven dead;
    # probe/diagnostic switches are checked by the trace guard.
    if plan:
        base,high,memory,masks=plan
        for i,(value,raw) in memory.items():
            out[i]=out[i].replace(raw,f'R[{base}]._u32[0] + {value.offset}u')
    out=[statement for i,line in enumerate(out) for statement in [line,*captures.get(i,[])]]
    live=set(range(128));kept=[]
    for line in reversed(out):
        d=definition(line);read=R_READ.fullmatch(line.strip())
        dst=d[0] if d else (int(read[1]) if read else None)
        if dst is not None:
            if dst not in live:continue
            live.discard(dst)
            operands=','.join(d[2]) if d else read[2]
            live.update(map(int,R_REG.findall(operands)))
        else:live.update(map(int,R_REG.findall(line)))
        kept.append(line)
    return list(reversed(kept))

def constant_trace(lines,log):
    labels={m[1]:i for i,l in enumerate(lines) if (m:=R_LABEL.fullmatch(l.strip()))}
    hints={}
    for head,start in labels.items():
        hints.clear()
        for previous in lines[:start]:
            d=definition(previous)
            if d:hints[d[0]]=evaluate(d[1],constant_args(d[2],hints))
        values=hints.copy();defined=set();inputs=set();trace=[];edges=0;index=start+1
        for count in range(2048):
            if index>=len(lines):break
            t=lines[index].strip();index+=1
            if R_LABEL.fullmatch(t):continue
            edge=R_CHAIN.fullmatch(t) or R_GOTO.fullmatch(t)
            if edge:
                cond=edge.group('cond');take=True
                if cond:
                    c=R_COND.fullmatch(cond)
                    if not c:break
                    r=int(c[1]);v=values.get(r)
                    if r not in defined:inputs.add(r)
                    if not isinstance(v,int):break
                    if c[2]=='u16':v&=65535
                    take=(v==0) if c[3]=='==' else (v!=0)
                if take:
                    if R_CHAIN.fullmatch(t):edges+=1
                    if edges>128:break
                    target=edge.group('lab')
                    if target not in labels:break
                    index=labels[target]+1
                continue
            if 'return 1;' in t:
                if edges<8 or 'spu_halt(' in t or 'spu_stop(' in t or 'spu_unsupported(' in t:break
                guard=['_ck','g_spu_ls_probe == 0','g_spu_wws_probe == 0']
                guard += [f'R[{r}]._u32[0] == {hints[r]}u' for r in sorted(inputs) if isinstance(hints.get(r),int)]
                plan=address_plan(trace,hints)
                if plan:
                    base,high,memory,masks=plan
                    guard += [f'(R[{base}]._u32[0] & 15u) == 0',f'R[{base}]._u32[0] <= SPU_LS_MASK - {high}u']
                lowered=lower_dead_insertions(trace,plan)
                block=[head+'_trace:', 'if ('+' && '.join(guard)+') {',*lowered,f'nst += {edges}u;',t,'}']
                result=list(lines)
                for i,line in enumerate(result):result[i]=line.replace('goto '+head+';','goto '+head+'_trace;')
                result[start:start]=block
                log(f'  trace {head}: {edges} edges, {len(trace)} instructions -> {len(lowered)} statements')
                return result
            read=R_READ.fullmatch(t);d=definition(t)
            if d:
                if not read and d[1] not in PURE_OPS:break
                for r in map(int,R_REG.findall(','.join(d[2]))):
                    if r not in defined:inputs.add(r)
                values[d[0]]=evaluate(d[1],constant_args(d[2],values));defined.add(d[0])
            elif read:
                for r in map(int,R_REG.findall(read[2])):
                    if r not in defined:inputs.add(r)
                values[int(read[1])]=None;defined.add(int(read[1]))
            elif R_WRITE.fullmatch(t):
                for r in map(int,R_REG.findall(t)):
                    if r not in defined:inputs.add(r)
            else:break
            trace.append(t)
    return lines
