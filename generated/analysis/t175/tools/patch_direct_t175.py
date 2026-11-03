"""T175: adds RSX_VP_DIRECT to the tree. usage: py -3 patch_direct_t175.py <tree>"""
import sys
T = sys.argv[1]


def edit(F, pairs):
    s = open(F, encoding='utf-8', errors='surrogateescape', newline='').read()
    crlf = '\r\n' in s
    s = s.replace('\r\n', '\n')
    for a, b in pairs:
        assert s.count(a) == 1, a
        s = s.replace(a, b)
    if crlf:
        s = s.replace('\n', '\r\n')
    open(F, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(s)


edit(T + '/include/ps3emu/vp_expand.h', [('''/* Write guest vertex vi's 256 bytes at dst. */
''', '''/* RSX_VP_DIRECT: guest vertex vi's active slots straight into a compact vertex at d (16 bytes per
 * slot, in act order), with no cache slot in between. Reads no destination byte. */
static inline void vpx_vertex_direct(vpx_cache* c, uint32_t vi, uint8_t* d)
{
    for (int k = 0; k < c->nact; k++) c->fetch(c->st, c->act[k], vi, (float*)(void*)(d + (size_t)k * 16u));
}

/* Write guest vertex vi's 256 bytes at dst. */
''')])
edit(T + '/include/ps3emu/vp_fetch_plan.h', [('''#ifdef __cplusplus
}
#endif
#endif''', '''/* vpx_vertex_direct through the plan; the plan keeps vpx's slot order. */
static inline void vfp_vertex_direct(const vpx_cache* c, vfp_plan* p, uint32_t vi, uint8_t* d)
{
    for (int k = 0; k < p->nact; k++) {
        vfp_attr* a = &p->a[k];
        vfp_fetch(p, a, vi, c->tmpl[a->slot], (float*)(void*)(d + (size_t)k * 16u));
    }
}

#ifdef __cplusplus
}
#endif
#endif''')])
edit(T + '/libs/video/rsx_d3d12_backend.c', [('''static void vpi_draw(ID3D12GraphicsCommandList* cl, D3D12_GPU_VIRTUAL_ADDRESS half, const D3D12DrawRecord* dr)
''', '''/* RSX_VP_DIRECT=1 (off by default, read once; only with RSX_VP_INDEXED): a new vertex of an indexed record converts straight
 * into the record. vpi_find already keeps each vertex to one write, so the cache slot in between only adds a 16-byte
 * read of what was just stored in 4-byte pieces, which cannot be forwarded from the store queue. Same bytes. */
static int vpd_mode(void)
{
    static int m = -1;
    if (m < 0) {
        const char* e = getenv("RSX_VP_DIRECT");
        m = (e && e[0] == '1' && !e[1] && vpi_mode()) ? 1 : 0;
        if (m) fprintf(stderr, "[vp-direct] on%c", 10);
    }
    return m;
}
static void vpi_draw(ID3D12GraphicsCommandList* cl, D3D12_GPU_VIRTUAL_ADDRESS half, const D3D12DrawRecord* dr)
'''), ('''        u32 nv = 0;
        vpi_begin(&s_vpi);
''', '''        u32 nv = 0;
        const int direct = vpd_mode();
        vpi_begin(&s_vpi);
'''), ('''                    const u32 vi = tri[c];
                    vpc_put_vertex((u8*)out, nv, cs, ff ? vfp_vertex(&s_vpx, &s_vfp, vi, 0) : vpx_vertex(&s_vpx, vi), cact, cn);
''', '''                    const u32 vi = tri[c];
                    if (direct) {
                        u8* vd = (u8*)out + VPC_UNIT + (size_t)nv * cs;
                        if (ff) vfp_vertex_direct(&s_vpx, &s_vfp, vi, vd); else vpx_vertex_direct(&s_vpx, vi, vd);
                    } else
                    vpc_put_vertex((u8*)out, nv, cs, ff ? vfp_vertex(&s_vpx, &s_vfp, vi, 0) : vpx_vertex(&s_vpx, vi), cact, cn);
''')])
