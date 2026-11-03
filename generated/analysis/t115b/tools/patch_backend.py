#!/usr/bin/env python3
"""T115B: apply the RSX_TEX_CACHE changes to rsx_d3d12_backend.c (CRLF kept).

  python generated/analysis/t115b/tools/patch_backend.py ps3recomp-t115b
"""
import sys
from pathlib import Path

tree = Path(sys.argv[1])
p = tree / 'libs/video/rsx_d3d12_backend.c'
raw = p.read_bytes().decode('utf-8')
assert raw.count('\r\n') == raw.count('\n')
t = raw.replace('\r\n', '\n')


def rep(old, new, count=1):
    global t
    n = t.count(old)
    assert n == count, (n, old[:80])
    t = t.replace(old, new)


rep('#include "rsx_d3d12_texmips.h" /* guest mip chains (RSX_TEX_MIPS) */\n',
    '#include "rsx_d3d12_texmips.h" /* guest mip chains (RSX_TEX_MIPS) */\n'
    '#include "rsx_tex_cache.h"     /* exact cache validation, CONTROL3 pitch (RSX_TEX_CACHE) */\n')

rep('''    u32 levels;         /* mip levels in res (1 unless RSX_TEX_MIPS=1) */
} VPTexSlot;''', '''    u32 levels;         /* mip levels in res (1 unless RSX_TEX_MIPS=1) */
    u32 pitch;          /* CONTROL3 row pitch the upload honoured (0 unless RSX_TEX_CACHE) */
    u32 nsub;           /* entries of sub_hash that describe res (RSX_TEX_CACHE) */
    u64 bytes;          /* upload buffer bytes, the resident estimate (RSX_TEX_CACHE) */
    u64 sub_hash[RSX_TEXCACHE_MAX_SUB];   /* rsx_texcache_hash per face x level */
} VPTexSlot;''')

# --- mode, counters, report --------------------------------------------------
rep('''/* Guest bytes of face 0 that an upload of this texture reads: level 0, or
 * the whole chain under RSX_TEX_MIPS. The draw-time snapshot covers the same
 * span so every level comes from the same instant. */
static u32 tex_src_span(u32 fmt, u32 w, u32 h, u32 mips, u32 off)
{
    rsx_texmip_plan p;
    return rsx_texmip_plan_make(fmt, w, h, mips, 0, off, texmip_mode(), &p) ? p.src_bytes : 0u;
}''', '''/* RSX_TEX_CACHE (rsx_tex_cache.h): 1 = a kept texture is re-uploaded when any
 * byte its upload reads changed (exact per-subresource hashes instead of
 * tex_csum's sparse face-0 sample) and linear textures honour their CONTROL3
 * row pitch; 2 = as 1, re-decoding and copying only the changed subresources.
 * Unset = the T115 behaviour. Read once. */
static int texcache_mode(void)
{
    static int m = -1;
    if (m < 0) {
        m = rsx_texcache_mode_parse(getenv("RSX_TEX_CACHE"));
        if (m) fprintf(stderr, "[tex-cache] RSX_TEX_CACHE=%d: exact validation, CONTROL3 pitch%s%c", m,
                       m == 2 ? ", changed subresources only" : "", 10);
    }
    return m;
}
/* Process totals under RSX_TEX_CACHE; printed at the 256th, 512th, 1024th ...
 * lookup. Times are QueryPerformanceCounter microseconds on the RSX thread. */
static struct {
    u64 lookups, reuse_frame, hits, miss_new, miss_changed, miss_shape;
    u64 creates, evicts, up_allocs, resident_bytes, peak_bytes;
    u64 hash_bytes, decode_bytes, sub_copied, sub_skipped;
    double hash_us, decode_us;
} s_texc;
static double texc_now_us(void)
{
    static double inv = 0.0;
    LARGE_INTEGER c;
    if (inv == 0.0) { LARGE_INTEGER f; QueryPerformanceFrequency(&f); inv = 1e6 / (double)f.QuadPart; }
    QueryPerformanceCounter(&c);
    return (double)c.QuadPart * inv;
}
static void texc_report(void)
{
    const u64 n = s_texc.lookups;
    if (n < 256 || (n & (n - 1))) return;
    fprintf(stderr, "[tex-cache] lookups=%llu frame_reuse=%llu hits=%llu miss new=%llu changed=%llu shape=%llu"
                    " creates=%llu evicts=%llu up_allocs=%llu resident_mb=%.1f peak_mb=%.1f hash_mb=%.1f"
                    " hash_ms=%.2f decode_mb=%.1f decode_ms=%.2f sub copied=%llu skipped=%llu%c",
            (unsigned long long)n, (unsigned long long)s_texc.reuse_frame, (unsigned long long)s_texc.hits,
            (unsigned long long)s_texc.miss_new, (unsigned long long)s_texc.miss_changed,
            (unsigned long long)s_texc.miss_shape, (unsigned long long)s_texc.creates,
            (unsigned long long)s_texc.evicts, (unsigned long long)s_texc.up_allocs,
            s_texc.resident_bytes / 1048576.0, s_texc.peak_bytes / 1048576.0, s_texc.hash_bytes / 1048576.0,
            s_texc.hash_us / 1000.0, s_texc.decode_bytes / 1048576.0, s_texc.decode_us / 1000.0,
            (unsigned long long)s_texc.sub_copied, (unsigned long long)s_texc.sub_skipped, 10);
}
/* Guest bytes of face 0 that an upload of this texture reads: level 0, or
 * the whole chain under RSX_TEX_MIPS. The draw-time snapshot covers the same
 * span so every level comes from the same instant. `pitch` is CONTROL3's,
 * honoured under RSX_TEX_CACHE only, as in vp_upload_tex_slot. */
static u32 tex_src_span(u32 fmt, u32 w, u32 h, u32 mips, u32 off, u32 pitch)
{
    rsx_texmip_plan p;
    return rsx_texmip_plan_make_pitched(fmt, w, h, mips, 0, off, texmip_mode(),
                                        texcache_mode() ? pitch : 0u, &p) ? p.src_bytes : 0u;
}''')

rep('''                                              tex_src_span(fmt, dr->tex[u].w, dr->tex[u].h,
                                                           dr->tex[u].mips, dr->tex[u].off));''',
    '''                                              tex_src_span(fmt, dr->tex[u].w, dr->tex[u].h,
                                                           dr->tex[u].mips, dr->tex[u].off,
                                                           dr->tex[u].pitch));''')
rep('''                                                             tex_src_span(dr->tex[_u].fmt, dr->tex[_u].w,
                                                                          dr->tex[_u].h, dr->tex[_u].mips,
                                                                          dr->tex[_u].off));''',
    '''                                                             tex_src_span(dr->tex[_u].fmt, dr->tex[_u].w,
                                                                          dr->tex[_u].h, dr->tex[_u].mips,
                                                                          dr->tex[_u].off, dr->tex[_u].pitch));''')
rep('''                    int ts = vp_upload_tex_slot(dr->tex[_u].off, dr->tex[_u].w,
                                                dr->tex[_u].h, dr->tex[_u].fmt,
                                                _cube, dr->tex[_u].mips);''',
    '''                    int ts = vp_upload_tex_slot(dr->tex[_u].off, dr->tex[_u].w,
                                                dr->tex[_u].h, dr->tex[_u].fmt,
                                                _cube, dr->tex[_u].mips, dr->tex[_u].pitch);''')
rep('''static int fpf_vp_upload_tex_slot(u32 off, u32 w, u32 h, u32 fmt, int cube, u32 mips)
{
    if (!s_fpf_on) return vp_upload_tex_slot(off, w, h, fmt, cube, mips);
    const u64 t0 = fpf_now_us();
    const int r = vp_upload_tex_slot(off, w, h, fmt, cube, mips);''',
    '''static int fpf_vp_upload_tex_slot(u32 off, u32 w, u32 h, u32 fmt, int cube, u32 mips, u32 gpitch)
{
    if (!s_fpf_on) return vp_upload_tex_slot(off, w, h, fmt, cube, mips, gpitch);
    const u64 t0 = fpf_now_us();
    const int r = vp_upload_tex_slot(off, w, h, fmt, cube, mips, gpitch);''')

# --- the uploader ------------------------------------------------------------
rep('static int vp_upload_tex_slot(u32 off, u32 w, u32 h, u32 fmt, int cube, u32 mips)\n{',
    '''/* `gpitch` is SET_TEXTURE_CONTROL3's row pitch; honoured under RSX_TEX_CACHE. */
static int vp_upload_tex_slot(u32 off, u32 w, u32 h, u32 fmt, int cube, u32 mips, u32 gpitch)
{''')
rep('''    rsx_tex_layout tl;
    rsx_texture_layout(fmt, w, h, &tl);
    u32 basef = fmt & 0x9F;              /* still needed for the SRV remap */''',
    '''    /* RSX_TEX_CACHE: a linear texture's rows are CONTROL3's pitch apart in
     * guest memory (rsx_texture_layout_pitched); the decode reads them at that
     * stride and writes them tightly packed, so the padding never reaches the
     * host image. Off: pitch 0, the layout this function always used. */
    const int tcm = texcache_mode();
    const u32 tpitch = tcm ? gpitch : 0u;
    rsx_tex_layout tl;
    rsx_texture_layout_pitched(fmt, w, h, tpitch, &tl);
    u32 basef = fmt & 0x9F;              /* still needed for the SRV remap */''')
rep('''    rsx_texmip_plan mp;
    rsx_texmip_plan_make(fmt, w, h, mips, cube, off, texmip_mode(), &mp);''',
    '''    rsx_texmip_plan mp;
    rsx_texmip_plan_make_pitched(fmt, w, h, mips, cube, off, texmip_mode(), tpitch, &mp);
    /* RSX_TEX_CACHE: this call's per-subresource hashes (s_tch over s_tcs),
     * which source they were taken from, and which subresources differ from
     * the kept slot's (s_tcd; valid when tc_dirty_ok). One RSX thread. */
    static rsx_texcache_spans s_tcs;
    static u64 s_tch[RSX_TEXCACHE_MAX_SUB];
    static u8 s_tcd[RSX_TEXCACHE_MAX_SUB];
    const u8* tch_f0 = NULL; const u8* tch_g = NULL; u32 tch_n = 0; int tc_dirty_ok = 0;
    if (tcm) { s_texc.lookups++; texc_report(); }''')
rep('''        if (c->res && c->key == key_off && c->w == w && c->h == h && c->fmt == fmt
            && c->cube == cube) {
            if (c->used) return i;                /* already bound this frame */''',
    '''        if (c->res && c->key == key_off && c->w == w && c->h == h && c->fmt == fmt
            && c->cube == cube && c->pitch == tpitch) {
            if (c->used) { if (tcm) s_texc.reuse_frame++; return i; }   /* already bound this frame */
            if (tcm && c->levels != mp.levels) s_texc.miss_shape++;''')
rep('''            const u8* csrc = (s_tex_src_override && c->off == s_tex_src_override_off)
                           ? s_tex_src_override : vm_base + c->off;
            u32 cs = TEX_CSUM(csrc, nb);''',
    '''            const u8* csrc = (s_tex_src_override && c->off == s_tex_src_override_off)
                           ? s_tex_src_override : vm_base + c->off;
            if (tcm) {   /* RSX_TEX_CACHE: every byte of every face and level */
                const double _h0 = texc_now_us();
                rsx_texcache_spans_make(&mp, &s_tcs);
                rsx_texcache_hash_spans(csrc, vm_base + c->off, &s_tcs, mp.levels, s_tch);
                tch_f0 = csrc; tch_g = vm_base + c->off; tch_n = s_tcs.n;
                for (u32 _s = 0; _s < s_tcs.n; _s++) s_texc.hash_bytes += s_tcs.len[_s];
                s_texc.hash_us += texc_now_us() - _h0;
                tc_dirty_ok = c->nsub == s_tcs.n;
                if (tc_dirty_ok && !rsx_texcache_diff(s_tch, c->sub_hash, s_tcs.n, s_tcd)) {
                    c->used = 1; s_texc.hits++;
                    if (vstat_on()) vstat_texture(key_off, csrc, nb, 1);
                    return i;
                }
                s_texc.miss_changed++;
                slot = i; break;
            }
            u32 cs = TEX_CSUM(csrc, nb);''')
rep('''    if (slot < 0) slot = freeslot;
    VPTexSlot* t = &s_d3d.vp_tex[slot];''',
    '''    if (slot < 0) { slot = freeslot; if (tcm) s_texc.miss_new++; }
    VPTexSlot* t = &s_d3d.vp_tex[slot];
    /* Until this upload completes the slot's hashes describe nothing: an upload
     * abandoned below (Map failure) must not validate next frame. */
    if (tcm) t->nsub = 0;''')
rep('''    if (t->res && (t->w != w || t->h != h || t->fmt != fmt || t->cube != cube ||
                   t->levels != mp.levels)) {
        t->res->lpVtbl->Release(t->res); t->res = NULL;
        if (t->up) { t->up->lpVtbl->Release(t->up); t->up = NULL; }
    }''',
    '''    if (t->res && (t->w != w || t->h != h || t->fmt != fmt || t->cube != cube ||
                   t->levels != mp.levels)) {
        t->res->lpVtbl->Release(t->res); t->res = NULL;
        if (t->up) { t->up->lpVtbl->Release(t->up); t->up = NULL; }
        if (tcm) { s_texc.evicts++; s_texc.resident_bytes -= t->bytes; t->bytes = 0; }
    }''')
rep('''        if (t->res && t->levels != 1) {
            t->res->lpVtbl->Release(t->res); t->res = NULL;
            if (t->up) { t->up->lpVtbl->Release(t->up); t->up = NULL; }
        }''',
    '''        if (t->res && t->levels != 1) {
            t->res->lpVtbl->Release(t->res); t->res = NULL;
            if (t->up) { t->up->lpVtbl->Release(t->up); t->up = NULL; }
            if (tcm) { s_texc.evicts++; s_texc.resident_bytes -= t->bytes; t->bytes = 0; }
        }''')
# Level-0 fallbacks keep the pitched level-0 span.
rep('mp.levels = 1; mp.src_bytes = mp.lv[0].tl.face_bytes; td.MipLevels = 1;',
    'mp.levels = 1; mp.src_bytes = rsx_texmip_level_read_bytes(&mp.lv[0]); td.MipLevels = 1;', 2)
rep('''            t->res->lpVtbl->Release(t->res); t->res = NULL; return -1;
        }
        fresh = 1;''',
    '''            t->res->lpVtbl->Release(t->res); t->res = NULL; return -1;
        }
        fresh = 1;
        if (tcm) {
            t->bytes = bd.Width; s_texc.creates++; s_texc.up_allocs++;
            s_texc.resident_bytes += bd.Width;
            if (s_texc.resident_bytes > s_texc.peak_bytes) s_texc.peak_bytes = s_texc.resident_bytes;
        }''')
rep('''    const u32 _csum0 = cube ? 0u : TEX_CSUM(_gsrc, _nb0);''',
    '''    const u32 _csum0 = (cube || tcm) ? 0u : TEX_CSUM(_gsrc, _nb0);
    /* RSX_TEX_CACHE: the hashes this upload is kept under, taken before the
     * decode for the same reason. The lookup's are reused when they cover the
     * same source and plan (a level-0 fallback or TEX_OFF_BIAS changes them).
     * With mode 2 and a kept resource, only the subresources whose hash
     * changed are converted and copied; the others already hold these bytes. */
    const u8* _dirty = NULL;
    double _d0 = 0.0;
    if (tcm) {
        const u8* f0 = cube ? vm_base + off : _gsrc;
        rsx_texcache_spans_make(&mp, &s_tcs);
        if (tch_f0 != f0 || tch_g != vm_base + off || tch_n != s_tcs.n) {
            const double _h0 = texc_now_us();
            rsx_texcache_hash_spans(f0, vm_base + off, &s_tcs, mp.levels, s_tch);
            for (u32 _s = 0; _s < s_tcs.n; _s++) s_texc.hash_bytes += s_tcs.len[_s];
            s_texc.hash_us += texc_now_us() - _h0;
            tc_dirty_ok = 0;
        }
        if (tcm == 2 && tc_dirty_ok && !fresh) _dirty = s_tcd;
        _d0 = texc_now_us();
    }''')
rep('''    if (mp.levels > 1)
        rsx_d3d12_texmip_fill(_map0, &s_tml, &mp, cube ? vm_base + off : _gsrc, vm_base + off,
                              rsx_texture_argb_is_rgba());
    for (u32 _f = 0; _f < (mp.levels > 1 ? 0u : _nfaces); _f++) {
    off    = _off0 + _f * _face_bytes;''',
    '''    if (mp.levels > 1)
        rsx_d3d12_texmip_fill_ex(_map0, &s_tml, &mp, cube ? vm_base + off : _gsrc, vm_base + off,
                                 rsx_texture_argb_is_rgba(), _dirty);
    for (u32 _f = 0; _f < (mp.levels > 1 ? 0u : _nfaces); _f++) {
    if (_dirty && !_dirty[_f]) continue;   /* RSX_TEX_CACHE=2: this face is unchanged */
    off    = _off0 + _f * _face_bytes;''')
rep('''    off = _off0; mapped = _map0;
    t->up->lpVtbl->Unmap(t->up, 0, NULL);''',
    '''    off = _off0; mapped = _map0;
    t->up->lpVtbl->Unmap(t->up, 0, NULL);
    if (tcm) {
        s_texc.decode_us += texc_now_us() - _d0;
        for (u32 _s = 0; _s < s_tcs.n; _s++) {
            if (_dirty && !_dirty[_s]) { s_texc.sub_skipped++; continue; }
            s_texc.sub_copied++;
            s_texc.decode_bytes += mp.levels > 1 ? (u64)s_tml.fp[_s].Footprint.RowPitch * s_tml.rows[_s]
                                                 : (u64)pitch * _face_rows;
        }
    }''')
rep('''    if (mp.levels > 1) rsx_d3d12_texmip_copy(s_d3d.cmd_list, t->res, t->up, &s_tml);
    else for (u32 _f = 0; _f < _nfaces; _f++) {
        dst.SubresourceIndex        = _f;      /* cube face = array slice */''',
    '''    if (mp.levels > 1) rsx_d3d12_texmip_copy_ex(s_d3d.cmd_list, t->res, t->up, &s_tml, _dirty);
    else for (u32 _f = 0; _f < _nfaces; _f++) {
        if (_dirty && !_dirty[_f]) continue;   /* RSX_TEX_CACHE=2: unchanged face */
        dst.SubresourceIndex        = _f;      /* cube face = array slice */''')
rep('''    { u32 nb = mp.src_bytes;
      t->csum = cube ? TEX_CSUM(vm_base + off, nb) : _csum0;''',
    '''    t->pitch = tpitch;
    if (tcm) { memcpy(t->sub_hash, s_tch, sizeof(u64) * s_tcs.n); t->nsub = s_tcs.n; }
    { u32 nb = mp.src_bytes;
      t->csum = tcm ? 0u : cube ? TEX_CSUM(vm_base + off, nb) : _csum0;''')

p.write_bytes(t.replace('\n', '\r\n').encode('utf-8'))
print('patched', p)
