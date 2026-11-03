"""T110: wire rsx_sampler_xlate.h into rsx_d3d12_backend.c (RSX_GUEST_SAMPLERS).
Each replacement must match exactly once.  py -3 -I edit_samplers.py <tree>"""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
s = p.read_text(encoding='utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, f'{n} matches (want {count}) for:\n{old[:200]}'
    s = s.replace(old, new)


# 1. include
rep('#include "rsx_color_xfer.h"   /* sRGB output / texture gamma the guest asks for */\n',
    '#include "rsx_color_xfer.h"   /* sRGB output / texture gamma the guest asks for */\n'
    '#include "rsx_sampler_xlate.h" /* guest sampler words -> host sampler (RSX_GUEST_SAMPLERS) */\n')

# 2. record + current-texture border word
rep('        u32 filter, address, control0;  /* raw sampler words (RSXI record only) */\n',
    '        u32 filter, address, control0;  /* raw sampler words (RSXI; RSX_GUEST_SAMPLERS) */\n'
    '        u32 border;                     /* SET_TEXTURE_BORDER_COLOR (RSX_GUEST_SAMPLERS) */\n')
rep('             u32 filter, address, control0; }\n        cur_texs[RSX_DSP_NUM_TEXTURES];\n',
    '             u32 filter, address, control0, border; }\n        cur_texs[RSX_DSP_NUM_TEXTURES];\n')
rep('        dr->tex[u].control0 = s_d3d.cur_texs[u].control0;\n',
    '        dr->tex[u].control0 = s_d3d.cur_texs[u].control0;\n'
    '        dr->tex[u].border   = s_d3d.cur_texs[u].border;\n')
rep('        s_d3d.cur_texs[unit].control0 = tex->control0;\n',
    '        s_d3d.cur_texs[unit].control0 = tex->control0;\n'
    '        s_d3d.cur_texs[unit].border   = tex->border_color;\n')

# 3. device fields
rep('    ID3D12RootSignature*  vp_root_sig;          /* CBV(b0) + SRV table + sampler */\n',
    '    ID3D12RootSignature*  vp_root_sig;          /* CBV(b0) + SRV table + sampler */\n'
    '    ID3D12DescriptorHeap* samp_heap;            /* RSX_GUEST_SAMPLERS: shader-visible samplers */\n'
    '    u32                   samp_inc;\n')

# 4. guest-sampler state + helpers, before the device init function that builds the root signature.
helpers = r'''
/* ---------------------------------------------------------------------------
 * RSX_GUEST_SAMPLERS=<mask> (rsx_sampler_xlate.h): sample each guest-FP unit
 * with the guest's own SET_TEXTURE_FILTER / ADDRESS / CONTROL0 / BORDER_COLOR
 * instead of the root signature's fixed samplers (unit 0 point/clamp, 1-15
 * linear/wrap). Bit 0 = filters, wrap and LOD range (required), 0x2 LOD bias,
 * 0x4 anisotropy, 0x8 border colour; 15 = all. Unset or bit 0 clear: the
 * fixed static samplers, exactly as before.
 * With it on, the guest-FP root signature has one single-descriptor sampler
 * table per unit (s0..s15, the registers rsx_fp_decompiler declares), pointing
 * into a shader-visible sampler heap: descriptors 0..15 are the old fixed
 * samplers (unit u keeps its old one wherever guest state does not apply:
 * host-built shaders, unbound units), and the rest an append-only cache of
 * distinct guest samplers, never rewritten, so no fence protects them.
 * ------------------------------------------------------------------------- */
#define GS_ROOT_BASE   3u                    /* root parameters 3..18 */
#define GS_FIXED       RSX_DSP_NUM_TEXTURES  /* descriptors 0..15: the old samplers */
#define GS_HEAP_SIZE   2048u                 /* D3D12_MAX_SHADER_VISIBLE_SAMPLER_HEAP_SIZE */
typedef char gs_enum_check1[(RSX_XL_D3D_FILTER_ANISOTROPIC == (u32)D3D12_FILTER_ANISOTROPIC) ? 1 : -1];
typedef char gs_enum_check2[(RSX_XL_D3D_ADDR_WRAP == (u32)D3D12_TEXTURE_ADDRESS_MODE_WRAP) ? 1 : -1];
typedef char gs_enum_check3[(RSX_XL_D3D_ADDR_MIRROR == (u32)D3D12_TEXTURE_ADDRESS_MODE_MIRROR) ? 1 : -1];
typedef char gs_enum_check4[(RSX_XL_D3D_ADDR_CLAMP == (u32)D3D12_TEXTURE_ADDRESS_MODE_CLAMP) ? 1 : -1];
typedef char gs_enum_check5[(RSX_XL_D3D_ADDR_BORDER == (u32)D3D12_TEXTURE_ADDRESS_MODE_BORDER) ? 1 : -1];
typedef char gs_enum_check6[(RSX_XL_D3D_ADDR_MIRROR_ONCE == (u32)D3D12_TEXTURE_ADDRESS_MODE_MIRROR_ONCE) ? 1 : -1];
typedef char gs_enum_check7[((u32)D3D12_FILTER_MIN_MAG_MIP_LINEAR == 0x15u && (u32)D3D12_FILTER_MIN_LINEAR_MAG_POINT_MIP_LINEAR == 0x11u) ? 1 : -1];
static u32 s_gs_mode = 0;                   /* features; 0 = off. Read once at device init. */
static rsx_sampler_cache s_gs_cache;
static int s_gs_cur[RSX_DSP_NUM_TEXTURES];  /* descriptor bound per unit since the last root-signature set */

static u32 gs_mode_from_env(void)
{
    const char* e = getenv("RSX_GUEST_SAMPLERS");
    u32 m = e ? (u32)strtoul(e, NULL, 0) : 0u;
    return (m & RSX_SAMP_F_BASE) ? (m & RSX_SAMP_F_ALL) : 0u;
}

/* The old static sampler of unit u, as a descriptor. */
static void gs_fixed_desc(int u, D3D12_SAMPLER_DESC* d)
{
    memset(d, 0, sizeof *d);
    d->Filter = u == 0 ? D3D12_FILTER_MIN_MAG_MIP_POINT : D3D12_FILTER_MIN_MAG_MIP_LINEAR;
    d->AddressU = d->AddressV = d->AddressW =
        u == 0 ? D3D12_TEXTURE_ADDRESS_MODE_CLAMP : D3D12_TEXTURE_ADDRESS_MODE_WRAP;
    d->MaxLOD = D3D12_FLOAT32_MAX;
    d->MaxAnisotropy = 1;
    d->ComparisonFunc = D3D12_COMPARISON_FUNC_NEVER;
}

static void gs_xl_desc(const rsx_sampler_xl* x, D3D12_SAMPLER_DESC* d)
{
    memset(d, 0, sizeof *d);
    d->Filter = (D3D12_FILTER)rsx_sampler_d3d_filter(x);
    d->AddressU = (D3D12_TEXTURE_ADDRESS_MODE)rsx_sampler_d3d_address(x->wrap[0]);
    d->AddressV = (D3D12_TEXTURE_ADDRESS_MODE)rsx_sampler_d3d_address(x->wrap[1]);
    d->AddressW = (D3D12_TEXTURE_ADDRESS_MODE)rsx_sampler_d3d_address(x->wrap[2]);
    d->MipLODBias = rsx_sampler_bias(x);
    d->MaxAnisotropy = x->aniso;
    d->ComparisonFunc = D3D12_COMPARISON_FUNC_NEVER;
    rsx_sampler_border_rgba(x, d->BorderColor);
    d->MinLOD = rsx_sampler_min_lod(x);
    d->MaxLOD = rsx_sampler_max_lod(x);
}

static D3D12_CPU_DESCRIPTOR_HANDLE gs_cpu(u32 i)
{
    D3D12_CPU_DESCRIPTOR_HANDLE h;
    s_d3d.samp_heap->lpVtbl->GetCPUDescriptorHandleForHeapStart(s_d3d.samp_heap, &h);
    h.ptr += (size_t)i * s_d3d.samp_inc;
    return h;
}

/* Device init: the heap and its 16 fixed descriptors. Failure turns the mode
 * off before the root signature is built, so nothing references the heap. */
static void gs_init(void)
{
    s_gs_mode = gs_mode_from_env();
    if (!s_gs_mode) return;
    D3D12_DESCRIPTOR_HEAP_DESC hd = {0};
    hd.Type = D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER;
    hd.NumDescriptors = GS_HEAP_SIZE;
    hd.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    if (FAILED(s_d3d.device->lpVtbl->CreateDescriptorHeap(s_d3d.device, &hd,
            &IID_ID3D12DescriptorHeap, (void**)&s_d3d.samp_heap)) || !s_d3d.samp_heap) {
        fprintf(stderr, "[samplers] RSX_GUEST_SAMPLERS: sampler heap creation failed; fixed samplers kept%c", 10);
        s_gs_mode = 0; s_d3d.samp_heap = NULL; return;
    }
    s_d3d.samp_inc = s_d3d.device->lpVtbl->GetDescriptorHandleIncrementSize(
        s_d3d.device, D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER);
    for (int u = 0; u < GS_FIXED; u++) {
        D3D12_SAMPLER_DESC d; gs_fixed_desc(u, &d);
        s_d3d.device->lpVtbl->CreateSampler(s_d3d.device, &d, gs_cpu((u32)u));
    }
    rsx_sampler_cache_init(&s_gs_cache, GS_HEAP_SIZE - GS_FIXED);
    fprintf(stderr, "[samplers] RSX_GUEST_SAMPLERS=0x%X: guest sampler state on (bias %s, aniso %s, border %s)%c",
            s_gs_mode, (s_gs_mode & RSX_SAMP_F_BIAS) ? "on" : "off",
            (s_gs_mode & RSX_SAMP_F_ANISO) ? "on" : "off", (s_gs_mode & RSX_SAMP_F_BORDER) ? "on" : "off", 10);
}

static void gs_set(ID3D12GraphicsCommandList* cl, int u, int desc)
{
    D3D12_GPU_DESCRIPTOR_HANDLE g;
    s_d3d.samp_heap->lpVtbl->GetGPUDescriptorHandleForHeapStart(s_d3d.samp_heap, &g);
    g.ptr += (u64)(u32)desc * s_d3d.samp_inc;
    cl->lpVtbl->SetGraphicsRootDescriptorTable(cl, GS_ROOT_BASE + (UINT)u, g);
    s_gs_cur[u] = desc;
}

/* Right after SetGraphicsRootSignature(vp_root_sig): a root-signature change
 * discards the tables, so every unit gets its fixed sampler again. */
static void gs_bind_fixed(ID3D12GraphicsCommandList* cl)
{
    if (!s_gs_mode) return;
    for (int u = 0; u < GS_FIXED; u++) gs_set(cl, u, u);
}

/* The descriptor unit u of this draw samples with: the guest's, for a guest
 * fragment program sampling a bound unit; else the unit's fixed sampler. */
static int gs_desc_for(const D3D12DrawRecord* dr, int u)
{
    if (!dr->fp_addr || !dr->tex[u].set || !((dr->fp_units >> u) & 1u)) return u;
    rsx_sampler_xl x; uint64_t k[2]; int added = 0;
    rsx_sampler_decode(dr->tex[u].filter, dr->tex[u].address, dr->tex[u].control0, dr->tex[u].border,
                       dr->tex[u].shadow.enabled == 1, s_gs_mode, &x);
    rsx_sampler_key(&x, k);
    int i = rsx_sampler_cache_get(&s_gs_cache, k, &added);
    if (i < 0) {
        { static int _n = 0; if (PS3_LOG_FIRST(_n, 1))
            fprintf(stderr, "[samplers] %u distinct guest samplers: heap full, later ones use the fixed sampler%c",
                    s_gs_cache.n, 10); }
        return u;
    }
    if (added) {
        D3D12_SAMPLER_DESC d; gs_xl_desc(&x, &d);
        s_d3d.device->lpVtbl->CreateSampler(s_d3d.device, &d, gs_cpu(GS_FIXED + (u32)i));
    }
    return GS_FIXED + i;
}

static void gs_bind_draw(ID3D12GraphicsCommandList* cl, const D3D12DrawRecord* dr)
{
    if (!s_gs_mode) return;
    for (int u = 0; u < GS_FIXED; u++) {
        const int want = gs_desc_for(dr, u);
        if (want != s_gs_cur[u]) gs_set(cl, u, want);
    }
}

/* What the RSXI record calls the host sampler of unit u. */
static const char* gs_host_name(const D3D12DrawRecord* dr, int u)
{
    if (!s_gs_mode || !dr->fp_addr || !dr->tex[u].set || !((dr->fp_units >> u) & 1u))
        return u == 0 ? "point_clamp" : "linear_wrap";
    return dr->tex[u].shadow.enabled == 1 ? "guest_depth_compare" : "guest";
}
'''
anchor = '/* Compiled guest-FP pipeline cache: decompiled VS (by cache slot) + decompiled\n'
# helpers need D3D12DrawRecord, which is defined before VPFPEntry? check order below
s_idx_rec = s.index('} D3D12DrawRecord;')
s_idx_anchor = s.index(anchor)
assert s_idx_rec < s_idx_anchor, 'D3D12DrawRecord must precede the helper block'
# s_d3d must be declared before the helpers: place them right after the s_d3d definition instead.
dev_anchor = 'static D3D12State s_d3d;\n'
assert s.count(dev_anchor) == 1, 's_d3d anchor'
rep(dev_anchor, dev_anchor + helpers)

# 5. root signature: per-unit sampler tables when on
old_rs = '''        D3D12_ROOT_SIGNATURE_DESC rd = {0};
        rd.NumParameters = 3; rd.pParameters = rp;
        rd.NumStaticSamplers = RSX_DSP_NUM_TEXTURES; rd.pStaticSamplers = samp;
        rd.Flags = D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;
'''
new_rs = '''        D3D12_ROOT_SIGNATURE_DESC rd = {0};
        rd.NumParameters = 3; rd.pParameters = rp;
        rd.NumStaticSamplers = RSX_DSP_NUM_TEXTURES; rd.pStaticSamplers = samp;
        rd.Flags = D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;
        /* RSX_GUEST_SAMPLERS: s0..s15 become one sampler table each (root
         * parameters 3..18, 21 DWORDs in all), bound per draw. */
        D3D12_ROOT_PARAMETER rpg[GS_ROOT_BASE + RSX_DSP_NUM_TEXTURES];
        D3D12_DESCRIPTOR_RANGE srg[RSX_DSP_NUM_TEXTURES];
        gs_init();
        if (s_gs_mode) {
            memset(rpg, 0, sizeof rpg); memset(srg, 0, sizeof srg);
            memcpy(rpg, rp, sizeof rp);
            for (int _s = 0; _s < RSX_DSP_NUM_TEXTURES; _s++) {
                srg[_s].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SAMPLER;
                srg[_s].NumDescriptors = 1;
                srg[_s].BaseShaderRegister = (UINT)_s;
                srg[_s].OffsetInDescriptorsFromTableStart = 0;
                rpg[GS_ROOT_BASE + _s].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
                rpg[GS_ROOT_BASE + _s].DescriptorTable.NumDescriptorRanges = 1;
                rpg[GS_ROOT_BASE + _s].DescriptorTable.pDescriptorRanges = &srg[_s];
                rpg[GS_ROOT_BASE + _s].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
            }
            rd.NumParameters = GS_ROOT_BASE + RSX_DSP_NUM_TEXTURES; rd.pParameters = rpg;
            rd.NumStaticSamplers = 0; rd.pStaticSamplers = NULL;
        }
'''
rep(old_rs, new_rs)

# 6. heaps + tables wherever the guest-FP root signature is set
old_bind = '''            s_d3d.cmd_list->lpVtbl->SetGraphicsRootSignature(s_d3d.cmd_list, s_d3d.vp_root_sig);
            s_d3d.cmd_list->lpVtbl->SetPipelineState(s_d3d.cmd_list, vpso);
            s_d3d.cmd_list->lpVtbl->IASetPrimitiveTopology(s_d3d.cmd_list, D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
            s_d3d.cmd_list->lpVtbl->SetGraphicsRootConstantBufferView(s_d3d.cmd_list, 0,
                s_d3d.vp_cb->lpVtbl->GetGPUVirtualAddress(s_d3d.vp_cb));
            ID3D12DescriptorHeap* heaps[] = { s_d3d.srv_heap };
            s_d3d.cmd_list->lpVtbl->SetDescriptorHeaps(s_d3d.cmd_list, 1, heaps);
'''
new_bind = '''            s_d3d.cmd_list->lpVtbl->SetGraphicsRootSignature(s_d3d.cmd_list, s_d3d.vp_root_sig);
            s_d3d.cmd_list->lpVtbl->SetPipelineState(s_d3d.cmd_list, vpso);
            s_d3d.cmd_list->lpVtbl->IASetPrimitiveTopology(s_d3d.cmd_list, D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
            s_d3d.cmd_list->lpVtbl->SetGraphicsRootConstantBufferView(s_d3d.cmd_list, 0,
                s_d3d.vp_cb->lpVtbl->GetGPUVirtualAddress(s_d3d.vp_cb));
            ID3D12DescriptorHeap* heaps[] = { s_d3d.srv_heap, s_d3d.samp_heap };
            s_d3d.cmd_list->lpVtbl->SetDescriptorHeaps(s_d3d.cmd_list, s_gs_mode ? 2 : 1, heaps);
            gs_bind_fixed(s_d3d.cmd_list);
'''
rep(old_bind, new_bind)
old_conv = '''                        cl->lpVtbl->SetGraphicsRootSignature(cl, s_d3d.vp_root_sig);
                        ID3D12DescriptorHeap* hp2[] = { s_d3d.srv_heap };
                        cl->lpVtbl->SetDescriptorHeaps(cl, 1, hp2);
'''
new_conv = '''                        cl->lpVtbl->SetGraphicsRootSignature(cl, s_d3d.vp_root_sig);
                        ID3D12DescriptorHeap* hp2[] = { s_d3d.srv_heap, s_d3d.samp_heap };
                        cl->lpVtbl->SetDescriptorHeaps(cl, s_gs_mode ? 2 : 1, hp2);
                        gs_bind_fixed(cl);
'''
rep(old_conv, new_conv)

# 7. per-draw sampler tables next to the per-draw SRV table
old_srv = '''                gh.ptr += (u64)(DRAW_SRV_BASE + d * RSX_DSP_NUM_TEXTURES) * s_d3d.srv_inc;
                s_d3d.cmd_list->lpVtbl->SetGraphicsRootDescriptorTable(s_d3d.cmd_list, 1, gh);
'''
new_srv = '''                gh.ptr += (u64)(DRAW_SRV_BASE + d * RSX_DSP_NUM_TEXTURES) * s_d3d.srv_inc;
                s_d3d.cmd_list->lpVtbl->SetGraphicsRootDescriptorTable(s_d3d.cmd_list, 1, gh);
                gs_bind_draw(s_d3d.cmd_list, dr);   /* RSX_GUEST_SAMPLERS */
'''
rep(old_srv, new_srv)

# 8. RSXI host_sampler truthful
rep('                u == 0 ? "point_clamp" : "linear_wrap", xf.gamma[u], xf.expand[u]);\n',
    '                gs_host_name(dr, u), xf.gamma[u], xf.expand[u]);\n')
rep('''        /* Guest sampler words next to the host sampler actually used: the
         * root signature's static samplers ignore them (unit 0 point/clamp,
         * the others linear/wrap). */
''', '''        /* Guest sampler words next to the host sampler actually used: the
         * root signature's static samplers ignore them (unit 0 point/clamp,
         * the others linear/wrap) unless RSX_GUEST_SAMPLERS is on. */
''')

p.write_text(s, encoding='utf-8')
print('ok')
