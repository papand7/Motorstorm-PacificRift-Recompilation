"""T119 commit 4: RSX_VP_COMPACT=1 -- indexed strip/fan records written compact (ps3emu/vp_compact.h).

  py -3 patch_compact.py <worktree>
"""
import pathlib, sys

p = pathlib.Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
raw = p.read_bytes().decode('utf-8')
assert raw.count('\r\n') == raw.count('\n')
t = raw.replace('\r\n', '\n')


def rep(a, b, n=1):
    global t
    assert t.count(a) == n, (t.count(a), a[:90])
    t = t.replace(a, b)


rep('#include "ps3emu/vp_vs_memo.h"        /* vp_get_vs: the last lookup, remembered */\n',
    '#include "ps3emu/vp_vs_memo.h"        /* vp_get_vs: the last lookup, remembered */\n'
    '#include "ps3emu/vp_compact.h"        /* RSX_VP_COMPACT: vertices without the constant slots */\n'
    'static int vp_compact_mode(void);\n')

# 1. Record fields.
rep('''    int is_vp;          /* 1 = real VP path: vb_byte_offset indexes vp_vb (float4) */
''', '''    int is_vp;          /* 1 = real VP path: vb_byte_offset indexes vp_vb (float4) */
    u32 vp_cstride;     /* RSX_VP_COMPACT: 0 = 256-byte vertices; else a compact record (template, then
                         * vertex_count vertices of this stride), vp_amask = its active slots */
    u32 vp_amask;
''')

# 2. The switch, the expander's hand-off to the record, and the view binding.
rep('''static int vp_get_vs(const rsx_state* st)
{''', '''/* RSX_VP_COMPACT=1 (off by default): indexed strip/fan draws write only the
 * attributes fetched per vertex, after a one-unit template of the 16 slots,
 * and every VP PSO takes ATTRi from input slot i (ps3emu/vp_compact.h). Read
 * once: the input layout is fixed at PSO creation. */
static int vp_compact_mode(void)
{
    static int m = -1;
    if (m < 0) { const char* e = getenv("RSX_VP_COMPACT"); m = (e && e[0] == '1' && !e[1]) ? 1 : 0; }
    return m;
}
static u32 s_vpc_rec_stride = 0, s_vpc_rec_mask = 0;   /* the expander's last compact record, for the draw body */
static int s_vpc_fat_bound = 1;                         /* replay: the fat views are the ones bound */
/* Bind the 16 per-slot views: the fat layout over the buffer half, or one compact record. */
static void vpc_bind(ID3D12GraphicsCommandList* cl, D3D12_GPU_VIRTUAL_ADDRESS half, UINT half_bytes,
                     const D3D12DrawRecord* dr)
{
    vpc_view v[VPC_SLOTS];
    D3D12_VERTEX_BUFFER_VIEW d[VPC_SLOTS];
    if (dr) vpc_views_compact((u64)half, dr->vb_byte_offset, dr->vertex_count, dr->vp_amask, v);
    else vpc_views_fat((u64)half, (u32)half_bytes, v);
    for (int i = 0; i < VPC_SLOTS; i++) {
        d[i].BufferLocation = (D3D12_GPU_VIRTUAL_ADDRESS)v[i].loc;
        d[i].SizeInBytes = v[i].size;
        d[i].StrideInBytes = v[i].stride;
    }
    cl->lpVtbl->IASetVertexBuffers(cl, 0, VPC_SLOTS, d);
    s_vpc_fat_bound = dr ? 0 : 1;
}

static int vp_get_vs(const rsx_state* st)
{''')

# 3. Input layouts (both VP PSO builders).
rep('''        il[_e].InputSlot = 0;''', '''        il[_e].InputSlot = vp_compact_mode() ? (UINT)_e : 0;''')
rep('''        il[_e].AlignedByteOffset = (UINT)(_e * 16);''',
    '''        il[_e].AlignedByteOffset = vp_compact_mode() ? 0 : (UINT)(_e * 16);''')
rep('''        il[_i].Format = DXGI_FORMAT_R32G32B32A32_FLOAT; il[_i].InputSlot = 0;
        il[_i].AlignedByteOffset = (UINT)(_i * 16);''',
    '''        il[_i].Format = DXGI_FORMAT_R32G32B32A32_FLOAT; il[_i].InputSlot = vp_compact_mode() ? (UINT)_i : 0;
        il[_i].AlignedByteOffset = vp_compact_mode() ? 0 : (UINT)(_i * 16);''')

# 4. Replay: bind, rebind after a zeta conversion, the debug triangle, the draw.
rep('''            vbv.StrideInBytes  = 256;   /* 16 float4 attrib slots */
            s_d3d.cmd_list->lpVtbl->IASetVertexBuffers(s_d3d.cmd_list, 0, 1, &vbv);''',
    '''            vbv.StrideInBytes  = 256;   /* 16 float4 attrib slots */
            if (vp_compact_mode()) vpc_bind(s_d3d.cmd_list, vbv.BufferLocation, vbv.SizeInBytes, NULL);
            else s_d3d.cmd_list->lpVtbl->IASetVertexBuffers(s_d3d.cmd_list, 0, 1, &vbv);''')
rep('''                        cl->lpVtbl->IASetVertexBuffers(cl, 0, 1, &vbv);''',
    '''                        if (vp_compact_mode()) vpc_bind(cl, vbv.BufferLocation, vbv.SizeInBytes, NULL);
                        else cl->lpVtbl->IASetVertexBuffers(cl, 0, 1, &vbv);''')
rep('''                          s_d3d.cmd_list->lpVtbl->DrawInstanced(s_d3d.cmd_list, 3, 1, 1000, 0);''',
    '''                          if (vp_compact_mode() && !s_vpc_fat_bound)
                              vpc_bind(s_d3d.cmd_list, vbv.BufferLocation, vbv.SizeInBytes, NULL);
                          s_d3d.cmd_list->lpVtbl->DrawInstanced(s_d3d.cmd_list, 3, 1, 1000, 0);''')
rep('''                s_d3d.cmd_list->lpVtbl->DrawInstanced(s_d3d.cmd_list,
                    dr->vertex_count, 1, dr->vb_byte_offset / 256, 0);''',
    '''                if (dr->vp_cstride) {   /* RSX_VP_COMPACT record: its own views, from vertex 0 */
                    vpc_bind(s_d3d.cmd_list, vbv.BufferLocation, vbv.SizeInBytes, dr);
                    s_d3d.cmd_list->lpVtbl->DrawInstanced(s_d3d.cmd_list, dr->vertex_count, 1, 0, 0);
                } else {
                    if (vp_compact_mode() && !s_vpc_fat_bound)
                        vpc_bind(s_d3d.cmd_list, vbv.BufferLocation, vbv.SizeInBytes, NULL);
                    s_d3d.cmd_list->lpVtbl->DrawInstanced(s_d3d.cmd_list,
                        dr->vertex_count, 1, dr->vb_byte_offset / 256, 0);
                }''')

# 5. Inspector reads of the vertex buffer: slot 0 of a compact record.
rep('''        rsxi_pos_stats ps;
        rsxi_geom_pos_stats(base, 256u, dr->vertex_count, &ps);''',
    '''        rsxi_pos_stats ps;
        size_t pstride = 256u;
        if (dr->vp_cstride) {   /* compact: attribute 0 is the first active slot, or the template */
            pstride = (dr->vp_amask & 1u) ? dr->vp_cstride : 0u;
            if (dr->vp_amask & 1u) base += VPC_UNIT;
        }
        rsxi_geom_pos_stats(base, pstride, dr->vertex_count, &ps);''')
rep('''            const float* p = (const float*)(base + (u64)v * 256u);
            fputs(v ? ",[" : "[", f);''', '''            const float* p = (const float*)(base + (u64)v * pstride);
            fputs(v ? ",[" : "[", f);''')
rep('''                      if (s_d3d.vp_vb_mapped && shown <= 2) {''',
    '''                      if (s_d3d.vp_vb_mapped && shown <= 2 && !dr->vp_cstride) {''')

# 6. Space: what a compact indexed strip/fan reserves, in 256-byte units.
rep('''static u32 vp_draw_want(const rsx_state* st, u32 prim, u32 first, u32 count, int indexed)
{''', '''static int vp_compact_active(const rsx_state* st, int act_list[VPC_SLOTS], u32* mask);
static u32 vp_draw_want(const rsx_state* st, u32 prim, u32 first, u32 count, int indexed)
{''')
rep('''        ps3_prim_stream_batch(&s, st->begin_epoch, st->primitive_type, prim == RSX_PRIMITIVE_TRIANGLE_FAN, indexed);
        return vp_strip_verts(&s, st, first, count, indexed);
    }
    return 0;
}''', '''        ps3_prim_stream_batch(&s, st->begin_epoch, st->primitive_type, prim == RSX_PRIMITIVE_TRIANGLE_FAN, indexed);
        const u32 v = vp_strip_verts(&s, st, first, count, indexed);
        int al[VPC_SLOTS]; u32 m = 0;
        const int cn = indexed ? vp_compact_active(st, al, &m) : 0;
        return (cn && v && v != 0xFFFFFFFFu) ? vpc_units(v, vpc_stride(cn)) : v;
    }
    return 0;
}''')
rep('''        pv->fp_addr == st->shader_program && pv->begin_epoch == st->begin_epoch &&
        pv->vb_byte_offset + pv->vertex_count * VP_VERT_STRIDE == s_d3d.vp_vb_offset;''',
    '''        pv->fp_addr == st->shader_program && pv->begin_epoch == st->begin_epoch && !pv->vp_cstride &&
        pv->vb_byte_offset + pv->vertex_count * VP_VERT_STRIDE == s_d3d.vp_vb_offset;''')

# 7. The indexed strip/fan expander.
rep('''static u32 upload_strip_vp_indexed(const rsx_state* state, u32 first, u32 count, int fan)
{''', '''/* RSX_VP_COMPACT: the slots vpx fetches per vertex (vp_vx_begin's rule), when a
 * compact record is worth writing; 0 = write 256-byte vertices. */
static int vp_compact_active(const rsx_state* st, int act_list[VPC_SLOTS], u32* mask)
{
    extern uint8_t* vm_base;
    if (!vp_compact_mode() || !st) return 0;
    int act[VPC_SLOTS];
    for (int i = 0; i < VPC_SLOTS; i++)
        act[i] = st->vertex_attribs[i].enabled && st->vertex_attribs[i].stride != 0 && vm_base != NULL;
    const int n = vpc_active(act, act_list, mask);
    return vpc_worth(n) ? n : 0;
}

static u32 upload_strip_vp_indexed(const rsx_state* state, u32 first, u32 count, int fan)
{''')
rep('''    dspl_mark(DSPL_ENTRY);
    u32 maxv = vp_reserve(vp_strip_verts(&s_prim_stream, state, first, count, 1), state, fan ? "fan" : "strip", 1, first, count);
    dspl_mark(DSPL_COUNT);
    VPSlot* out = (VPSlot*)((u8*)s_d3d.vp_vb_mapped
        + (u64)s_d3d.vp_parity * s_vpvb.cap * VP_VERT_STRIDE + s_d3d.vp_vb_offset);
    u32 o = 0;
    const vp_idx_rd ir = vp_idx_begin(state);
    vp_vx_begin(state);''', '''    dspl_mark(DSPL_ENTRY);
    const u32 vwant = vp_strip_verts(&s_prim_stream, state, first, count, 1);
    int cact[VPC_SLOTS]; u32 cmask = 0;
    const int cn = vp_compact_active(state, cact, &cmask);   /* RSX_VP_COMPACT: 0 = 256-byte vertices */
    const u32 cs = vpc_stride(cn);
    u32 maxv;
    if (cn) maxv = vpc_max_verts(vp_reserve((vwant && vwant != 0xFFFFFFFFu) ? vpc_units(vwant, cs) : vwant,
                                            state, fan ? "fan" : "strip", 1, first, count), cs);
    else maxv = vp_reserve(vwant, state, fan ? "fan" : "strip", 1, first, count);
    dspl_mark(DSPL_COUNT);
    VPSlot* out = (VPSlot*)((u8*)s_d3d.vp_vb_mapped
        + (u64)s_d3d.vp_parity * s_vpvb.cap * VP_VERT_STRIDE + s_d3d.vp_vb_offset);
    u32 o = 0;
    const vp_idx_rd ir = vp_idx_begin(state);
    vp_vx_begin(state);
    if (cn && maxv) vpc_put_template((u8*)out, (const float (*)[4])s_vpx.tmpl);''')
rep('''        if (!ps3_prim_stream_push(&s_prim_stream, idx, tri)
            || o + 3 > maxv) continue;
        vpx_emit(&s_vpx, tri[0], &out[o*16]); o++;
        vpx_emit(&s_vpx, tri[1], &out[o*16]); o++;
        vpx_emit(&s_vpx, tri[2], &out[o*16]); o++;
    }
    dspl_mark(DSPL_EMIT);
    if (!o) return 0;   /* vp_reserve named it: too_few_vertices or vertex_buffer_full */
    s_d3d.vp_vb_offset += o * VP_VERT_STRIDE;
    return o;
}''', '''        if (!ps3_prim_stream_push(&s_prim_stream, idx, tri)
            || o + 3 > maxv) continue;
        if (cn) {
            vpc_put_vertex((u8*)out, o, cs, vpx_vertex(&s_vpx, tri[0]), cact, cn); o++;
            vpc_put_vertex((u8*)out, o, cs, vpx_vertex(&s_vpx, tri[1]), cact, cn); o++;
            vpc_put_vertex((u8*)out, o, cs, vpx_vertex(&s_vpx, tri[2]), cact, cn); o++;
            continue;
        }
        vpx_emit(&s_vpx, tri[0], &out[o*16]); o++;
        vpx_emit(&s_vpx, tri[1], &out[o*16]); o++;
        vpx_emit(&s_vpx, tri[2], &out[o*16]); o++;
    }
    dspl_mark(DSPL_EMIT);
    if (!o) return 0;   /* vp_reserve named it: too_few_vertices or vertex_buffer_full */
    if (cn) {
        s_d3d.vp_vb_offset += vpc_units(o, cs) * VPC_UNIT;
        s_vpc_rec_stride = cs; s_vpc_rec_mask = cmask;
    } else
        s_d3d.vp_vb_offset += o * VP_VERT_STRIDE;
    return o;
}''')

# 8. The indexed draw body: hand-off, merge guard, record fields.
rep('''    dspl_open();
    if (s_dspl_on) s_dspl.callbacks++;
    s_rec_indexed = 1;''', '''    dspl_open();
    if (s_dspl_on) s_dspl.callbacks++;
    s_vpc_rec_stride = s_vpc_rec_mask = 0;
    s_rec_indexed = 1;''')
rep('''        if (pv->is_vp && pv->topology == RSX_TOPOLOGY_TRIANGLES &&
            pv->fp_addr == fpnow &&
            pv->begin_epoch == (s_d3d.current_rsx_state
                                ? s_d3d.current_rsx_state->begin_epoch : 0) &&
            pv->vb_byte_offset + pv->vertex_count * VP_VERT_STRIDE == rec) {
            pv->vertex_count += emitted;
            s_d3d.merge_first_end = first + count;
            s_da_merged = 1;
            dspl_mark(DSPL_POST);''', '''        if (pv->is_vp && pv->topology == RSX_TOPOLOGY_TRIANGLES &&
            pv->fp_addr == fpnow && !pv->vp_cstride && !s_vpc_rec_stride &&
            pv->begin_epoch == (s_d3d.current_rsx_state
                                ? s_d3d.current_rsx_state->begin_epoch : 0) &&
            pv->vb_byte_offset + pv->vertex_count * VP_VERT_STRIDE == rec) {
            pv->vertex_count += emitted;
            s_d3d.merge_first_end = first + count;
            s_da_merged = 1;
            dspl_mark(DSPL_POST);''')
rep('''        if (s_dspl_on) s_dspl.records++;
        dr->vb_byte_offset = rec;''', '''        if (s_dspl_on) s_dspl.records++;
        dr->vp_cstride = s_vpc_rec_stride; dr->vp_amask = s_vpc_rec_mask;
        dr->vb_byte_offset = rec;''')

# 9. Every other record site starts fat (records are reused slots).
rep('''                D3D12DrawRecord* dr = &s_d3d.draws[s_d3d.draw_count];
''', '''                D3D12DrawRecord* dr = &s_d3d.draws[s_d3d.draw_count];
                dr->vp_cstride = dr->vp_amask = 0;
''')
rep('''            s_d3d.draws[s_d3d.draw_count].is_vp          = 0;
            s_d3d.draws[s_d3d.draw_count].is_clear       = 0;''', '''            s_d3d.draws[s_d3d.draw_count].is_vp          = 0;
            s_d3d.draws[s_d3d.draw_count].vp_cstride = s_d3d.draws[s_d3d.draw_count].vp_amask = 0;
            s_d3d.draws[s_d3d.draw_count].is_clear       = 0;''')
rep('''        s_d3d.draws[s_d3d.draw_count].is_vp          = 0;
        s_d3d.draws[s_d3d.draw_count].is_clear       = 0;''', '''        s_d3d.draws[s_d3d.draw_count].is_vp          = 0;
        s_d3d.draws[s_d3d.draw_count].vp_cstride = s_d3d.draws[s_d3d.draw_count].vp_amask = 0;
        s_d3d.draws[s_d3d.draw_count].is_clear       = 0;''')
rep('''            D3D12DrawRecord* dr = &s_d3d.draws[s_d3d.draw_count];
            dr->vb_byte_offset = rec;''', '''            D3D12DrawRecord* dr = &s_d3d.draws[s_d3d.draw_count];
            dr->vp_cstride = dr->vp_amask = 0;
            dr->vb_byte_offset = rec;''')

p.write_bytes(t.replace('\n', '\r\n').encode('utf-8'))
print('patched', p)
