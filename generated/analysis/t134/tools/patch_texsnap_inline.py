"""T134: move the TEXSNAP span into vp_record_tex_snap's body (no new lines next to its header, which
T115B/T133 insert above). One-shot patch of a ps3recomp tree."""
from pathlib import Path
import sys

p = Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
raw = p.read_text(encoding='utf-8')
crlf = '\r\n' in raw
t = raw.replace('\r\n', '\n')

old = '''static void vp_record_tex_snap_units(D3D12DrawRecord* dr);
static void vp_record_tex_snap(D3D12DrawRecord* dr)
{
    /* PS3_FTRACE / PS3_CRITICAL_PATH_TRACE (T134): one span per draw whose
     * captures took at least PS3_FTRACE_MIN_US; a = KB hashed, b = copies. */
    const uint64_t ft_t0 = PS3_FT_ON() ? ps3_ft_now() : 0;
    const uint64_t h0 = s_texsnap.hashed, c0 = s_texsnap.copies;
    vp_record_tex_snap_units(dr);
    if (ft_t0) {
        const uint64_t t1 = ps3_ft_now();
        if (t1 - ft_t0 >= ps3_ft_min_ns())
            ps3_ft_span(PS3_FT_TEXSNAP, 0, (uint32_t)((s_texsnap.hashed - h0) >> 10),
                        (uint32_t)(s_texsnap.copies - c0), ft_t0, t1);
    }
}

static void vp_record_tex_snap_units(D3D12DrawRecord* dr)
{
    extern uint8_t* vm_base;
    const int mode = tex_snapshot_mode();
'''
new = '''static void vp_record_tex_snap(D3D12DrawRecord* dr)
{
    extern uint8_t* vm_base;
    const int mode = tex_snapshot_mode();
    /* PS3_FTRACE / PS3_CRITICAL_PATH_TRACE (T134): one span per draw whose
     * captures took at least PS3_FTRACE_MIN_US; a = KB hashed, b = copies. */
    const uint64_t ft_t0 = PS3_FT_ON() ? ps3_ft_now() : 0;
    const uint64_t ft_h0 = s_texsnap.hashed, ft_c0 = s_texsnap.copies;
'''
assert t.count(old) == 1
t = t.replace(old, new)

old2 = '''        if (s_texsnap.torn != torn0 && vstat_on()) g_vstat.torn++;
    }
}
'''
new2 = '''        if (s_texsnap.torn != torn0 && vstat_on()) g_vstat.torn++;
    }
    if (ft_t0) {
        const uint64_t t1 = ps3_ft_now();
        if (t1 - ft_t0 >= ps3_ft_min_ns())
            ps3_ft_span(PS3_FT_TEXSNAP, 0, (uint32_t)((s_texsnap.hashed - ft_h0) >> 10),
                        (uint32_t)(s_texsnap.copies - ft_c0), ft_t0, t1);
    }
}
'''
assert t.count(old2) == 1
t = t.replace(old2, new2)
if crlf:
    t = t.replace('\n', '\r\n')
p.write_text(t, encoding='utf-8', newline='')
print('patched', p)
