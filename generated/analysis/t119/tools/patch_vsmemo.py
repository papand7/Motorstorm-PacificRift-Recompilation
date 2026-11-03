"""T119 commit 3: remember the last vertex-program lookup in vp_get_vs (rsx_d3d12_backend.c, CRLF).

  py -3 patch_vsmemo.py <worktree>
"""
import pathlib, sys

p = pathlib.Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
raw = p.read_bytes().decode('utf-8')
assert raw.count('\r\n') == raw.count('\n')
t = raw.replace('\r\n', '\n')


def rep(a, b, n=1):
    global t
    assert t.count(a) == n, (t.count(a), a[:80])
    t = t.replace(a, b)


rep('#include "ps3emu/draw_split.h"        /* RSX_DRAW_SPLIT: the draw callbacks by stage */\n',
    '#include "ps3emu/draw_split.h"        /* RSX_DRAW_SPLIT: the draw callbacks by stage */\n'
    '#include "ps3emu/vp_vs_memo.h"        /* vp_get_vs: the last lookup, remembered */\n')
rep('''static int vp_get_vs(const rsx_state* st)
{''', '''/* RSX_VS_MEMO=0 turns off vp_get_vs's memo of its last lookup (ps3emu/vp_vs_memo.h);
 * on by default: it returns what the scan, hash and cache search would. */
static int vs_memo_on(void)
{
    static int on = -1;
    if (on < 0) { const char* e = getenv("RSX_VS_MEMO"); on = (e && e[0] == '0' && !e[1]) ? 0 : 1; }
    return on;
}
static vsm_memo s_vsm = { .len = 0, .slot = -1 };

static int vp_get_vs(const rsx_state* st)
{''')
rep('''    const u8* vuc = st->vp_ucode + vstart;
    u32 vlen = st->vp_ucode_bytes - vstart;
    /* Hash the program's own bytes, up to its end bit, not everything behind it in the store (as the Metal
     * backend does). A title that keeps several programs resident and uploads another one behind the program it
     * draws with changed that hash on every upload, so nearly every draw missed the cache and ran D3DCompile. */
    { extern u32 rsx_vp_program_size_instrs(const u8*, u32);
      const u32 instrs = rsx_vp_program_size_instrs(vuc, vlen);
      if (instrs) vlen = instrs * 16u; }
    u32 hash = vp_hash_ucode(vuc, vlen);
    for (int i = 0; i < s_d3d.vp_vs_n; i++)
        if (s_d3d.vp_vs[i].hash == hash) return i;
''', '''    const u8* vuc = st->vp_ucode + vstart;
    u32 vlen = st->vp_ucode_bytes - vstart;
    const int memo = vs_memo_on();
    if (memo) {   /* the same program as the last lookup: its slot, if the cache still holds it there */
        const int ms = s_vsm.slot;
        const int hit = vsm_lookup(&s_vsm, vuc, vlen, vstart,
                                   (ms >= 0 && ms < s_d3d.vp_vs_n) ? s_d3d.vp_vs[ms].hash : ~s_vsm.hash);
        if (hit >= 0) return hit;
    }
    /* Hash the program's own bytes, up to its end bit, not everything behind it in the store (as the Metal
     * backend does). A title that keeps several programs resident and uploads another one behind the program it
     * draws with changed that hash on every upload, so nearly every draw missed the cache and ran D3DCompile. */
    u32 ended = 0;
    { extern u32 rsx_vp_program_size_instrs(const u8*, u32);
      const u32 instrs = rsx_vp_program_size_instrs(vuc, vlen);
      if (instrs) { vlen = instrs * 16u; ended = 1; } }
    u32 hash = vp_hash_ucode(vuc, vlen);
    for (int i = 0; i < s_d3d.vp_vs_n; i++)
        if (s_d3d.vp_vs[i].hash == hash) {
            if (memo) vsm_store(&s_vsm, vuc, ended ? vlen : 0, vstart, hash, i);
            return i;
        }
''')
rep('''        compile_vp();
        s_d3d.current_rsx_state = prev;
    }
    return slot;
}''', '''        compile_vp();
        s_d3d.current_rsx_state = prev;
    }
    if (memo) vsm_store(&s_vsm, vuc, ended ? vlen : 0, vstart, hash, slot);
    return slot;
}''')

p.write_bytes(t.replace('\n', '\r\n').encode('utf-8'))
print('patched', p)
