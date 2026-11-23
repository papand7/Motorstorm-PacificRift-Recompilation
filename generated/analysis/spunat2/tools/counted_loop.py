"""AOT lowering for a counted quad-store loop, including nonuniform lanes."""
import re
from static_loop import Address,operation,Refuse

def counted_loop(body, head, uid, prefix=()):
    if len(body)!=5 or body[0]!=head+':':return None
    store=re.fullmatch(r'spu_ls_write128_ls\(ctx, ls, 0, R\[(\d+)\]\._u32\[0\] \+ (-?0x[0-9a-fA-F]+|-?\d+), R\[(\d+)\]\);',body[1])
    inc=re.fullmatch(r'R\[(\d+)\] = spu_ai\(R\[(\d+)\], (\d+)\);',body[2])
    compare=re.fullmatch(r'R\[(\d+)\] = spu_ceq\(R\[(\d+)\], R\[(\d+)\]\);',body[3])
    branch=re.fullmatch(r'if \(R\[(\d+)\]\._u32\[0\] == 0\) goto '+head+r';',body[4])
    if not all((store,inc,compare,branch)):return None
    counter=int(inc[1]);stride=int(inc[3]);cond=int(compare[1]);a,b=map(int,(compare[2],compare[3]))
    if counter!=int(inc[2]) or counter!=int(store[1]) or counter not in (a,b) or cond!=int(branch[1]):return None
    bound=b if a==counter else a;source=int(store[3])
    if stride==0 or stride>0x7fffffff or len({counter,bound,cond,source})!=4:return None
    offset=int(store[2],0)
    # A hint chooses a small unrolled branch; its runtime equality guard makes
    # correctness independent of path-sensitive constant inference.
    values={r:Address(r) for r in range(128)}
    for line in prefix:
        m=re.fullmatch(r'R\[(\d+)\] = (spu_\w+)\((.*)\);',line.strip())
        if not m:continue
        args=[]
        try:
            for term in m[3].split(','):
                term=term.strip();reg=re.fullmatch(r'R\[(\d+)\]',term)
                args.append(values[int(reg[1])] if reg else int(term,0))
            values[int(m[1])]=operation(m[2],args)
        except (ValueError,TypeError,KeyError,Refuse):values[int(m[1])]=None
    hint=None
    x,y=values[bound],values[counter]
    if isinstance(x,Address) and isinstance(y,Address) and x.reg==y.reg:
        hint=(x.offset-y.offset)&0xffffffff
    unrolled=[]
    if hint and hint%stride==0 and 1<hint//stride<=32:
        count=hint//stride-1
        unrolled=[f'    if (_ck && delta == {hint}u) {{']
        unrolled += [f'        spu_ls_write128_ls(ctx, ls, 0, R[{counter}]._u32[0] + (uint32_t)({offset+i*stride}), R[{source}]);' for i in range(count)]
        unrolled += [f'        R[{counter}] = spu_ai(R[{counter}], {count*stride});',f'        goto {head};','    }']
    return [head+f'_fast{uid}:',
        '{',f'    const uint32_t delta = R[{bound}]._u32[0] - R[{counter}]._u32[0];',
        *unrolled,
        f'    if (_ck && delta >= {stride}u && delta % {stride}u == 0 && delta / {stride}u <= 4096u) {{',
        f'        const uint32_t count = delta / {stride}u - 1u;',
        f'        uint32_t address = R[{counter}]._u32[0] + (uint32_t)({offset});',
        '        for (uint32_t i=0; i<count; ++i) {',
        f'            spu_ls_write128_ls(ctx, ls, 0, address, R[{source}]);',
        f'            address += {stride}u;',
        '        }',
        f'        R[{counter}] = spu_ai(R[{counter}], count * {stride}u);',
        f'        goto {head};',
        '    }','}']
