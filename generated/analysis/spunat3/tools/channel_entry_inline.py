"""Reusable AOT channel-entry inlining; callbacks and real fallbacks are preserved."""
from pathlib import Path
import argparse,re

PRELUDE = r'''
#include "spu_taskrec.h"
extern void spu_wrch(spu_context*, uint32_t, u128);
extern u128 spu_rdch(spu_context*, uint32_t);
extern uint32_t spu_rchcnt(spu_context*, uint32_t);
static __attribute__((always_inline)) inline void spu_inline_wrch(spu_context* ctx, uint32_t channel, u128 value) {
    const spu_rt_hooks* hooks=g_spu_rt_hooks;
    if (__builtin_expect(hooks!=0,0)) { hooks->wrch(ctx,channel,&value); return; }
    spu_wrch(ctx,channel,value);
}
static __attribute__((always_inline)) inline u128 spu_inline_rdch(spu_context* ctx, uint32_t channel) {
    const spu_rt_hooks* hooks=g_spu_rt_hooks;
    if (__builtin_expect(hooks!=0,0)) { u128 value; hooks->rdch(ctx,channel,&value); return value; }
    return spu_rdch(ctx,channel);
}
static __attribute__((always_inline)) inline uint32_t spu_inline_rchcnt(spu_context* ctx, uint32_t channel) {
    const spu_rt_hooks* hooks=g_spu_rt_hooks;
    if (__builtin_expect(hooks!=0,0)) return hooks->rchcnt(ctx,channel);
    return spu_rchcnt(ctx,channel);
}
'''

def rewrite_calls(source):
    for name in ('wrch','rdch','rchcnt'):
        source=source.replace('spu_'+name+'(ctx,','spu_inline_'+name+'(ctx,')
    return source

def transform(source):
    if 'inline void spu_inline_wrch(' in source:
        raise ValueError('channel entry already inlined')
    marker='#include "spu_helpers.h"'
    if source.count(marker)!=1:raise ValueError('expected one spu_helpers include')
    return rewrite_calls(source).replace(marker,marker+'\n'+PRELUDE,1)

def rewrite_file(source,output):
    source=Path(source).resolve();output=Path(output).resolve()
    if source==output:raise ValueError('use a separate output path')
    text=source.read_text();output.parent.mkdir(parents=True,exist_ok=True)
    pattern=r'(#include ")([^"]+\.c)("\s*/\* SPU_NATIVE_FILE src=)'
    includes=list(re.finditer(pattern,text))
    for index,match in reversed(list(enumerate(includes))):
        native=Path(match[2])
        if not native.is_absolute():native=source.parent/native
        replacement=output.with_name(output.stem+f'_native_{index}.c')
        replacement.write_text(rewrite_calls(native.read_text()))
        text=text[:match.start(2)]+replacement.as_posix()+text[match.end(2):]
    output.write_text(transform(text))
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('output')
    args=parser.parse_args();print(rewrite_file(args.source,args.output))
