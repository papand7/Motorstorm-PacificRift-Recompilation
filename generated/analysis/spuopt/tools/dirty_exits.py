"""Limit pure native exit flushes to registers modified on an incoming path."""
import re
LABEL=re.compile(r'^(loc_[0-9A-Fa-f]{8}):$')
GOTO=re.compile(r'goto (loc_[0-9A-Fa-f]{8});')
DEF=re.compile(r'R\[(\d+)\] = ')

def dirty_exits(lines):
    # Calls can observe/modify context state. Keep the established pass there.
    if any(re.search(r'spu_(?:rdch|wrch|rchcnt)\(',s) for s in lines):return lines
    incoming={}
    def walk(emit):
        dirty=set();out=[];changed=False
        for text in lines:
            s=text.strip();label=LABEL.fullmatch(s)
            if label:dirty |= incoming.get(label[1],set())
            dirty |= {int(n) for n in DEF.findall(s)}
            for target in GOTO.findall(s):
                known=incoming.setdefault(target,set())
                if not dirty<=known:known.update(dirty);changed=True
            if emit and 'STORE_ALL();' in text and not re.search(r'spu_(?:halt|stop|unsupported)\(',text):
                stores=' '.join(f'ctx->gpr[{r}] = R[{r}];' for r in sorted(dirty))
                text=text.replace('STORE_ALL();',stores)
            out.append(text)
            if (s.startswith('{') or s.startswith('goto ')) and ('return 1;' in s or 'goto ' in s):dirty=set()
        return out,changed
    while walk(False)[1]:pass
    return walk(True)[0]
