"""T116: wire rsx_shader_cache.h into rsx_d3d12_backend.c (CRLF kept).

Every change is behind RSX_SHADER_CACHE (default 0 = previous behaviour) or
RSX_SHADER_STATS (default off). Each replacement must match exactly once."""
import pathlib, sys

P = pathlib.Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
raw = P.read_bytes()
assert raw.count(b'\r\n') == raw.count(b'\n'), 'expected uniform CRLF'
s = raw.decode('utf-8').replace('\r\n', '\n')


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, (n, old[:80])
    s = s.replace(old, new)


# 1. include + state
rep('''#include <d3dcompiler.h>
''',
    '''#include <d3dcompiler.h>
/* RSX_SHADER_CACHE / RSX_SHADER_STATS: compiled-bytecode and pipeline caches
 * and their counters. Level 0, the default, compiles and creates exactly as
 * before. */
#include "rsx_shader_cache.h"
static rsc_cache s_rsc;
static uint64_t s_vp_root_sig_id;   /* hash of the serialized VP root signature */
''')

# 2. root signature identity (content, not pointer)
rep('''        hr = D3D12SerializeRootSignature(&rd, D3D_ROOT_SIGNATURE_VERSION_1, &sig, &err);
        if (SUCCEEDED(hr)) {
            s_d3d.device->lpVtbl->CreateRootSignature(s_d3d.device, 0,
                sig->lpVtbl->GetBufferPointer(sig), sig->lpVtbl->GetBufferSize(sig),
                &IID_ID3D12RootSignature, (void**)&s_d3d.vp_root_sig);
            sig->lpVtbl->Release(sig);''',
    '''        hr = D3D12SerializeRootSignature(&rd, D3D_ROOT_SIGNATURE_VERSION_1, &sig, &err);
        if (SUCCEEDED(hr)) {
            s_d3d.device->lpVtbl->CreateRootSignature(s_d3d.device, 0,
                sig->lpVtbl->GetBufferPointer(sig), sig->lpVtbl->GetBufferSize(sig),
                &IID_ID3D12RootSignature, (void**)&s_d3d.vp_root_sig);
            { rsc_key z = { 0x726F6F742D736967ull, 0 };   /* pipeline-library identity of this layout */
              s_vp_root_sig_id = rsc_hash(sig->lpVtbl->GetBufferPointer(sig), sig->lpVtbl->GetBufferSize(sig), z).a; }
            sig->lpVtbl->Release(sig);''')

# 3. init after the device exists
rep('''    /* Create command queue */
    D3D12_COMMAND_QUEUE_DESC queue_desc = {0};''',
    '''    rsc_init(&s_rsc, -1, NULL);
    rsc_psolib_open(&s_rsc, s_d3d.device);

    /* Create command queue */
    D3D12_COMMAND_QUEUE_DESC queue_desc = {0};''')

# 4. VS key includes the start slot (level >= 1): a branching program's HLSL
#    depends on it (rsx_vp_set_branch_base), so the same bytes at another
#    slot are another shader.
rep('''    u32 hash = vp_hash_ucode(vuc, vlen);
    for (int i = 0; i < s_d3d.vp_vs_n; i++)''',
    '''    u32 hash = vp_hash_ucode(vuc, vlen);
    if (s_rsc.level > 0) {
        hash ^= (vstart / 16u + 1u) * 0x9E3779B1u;
        hash *= 16777619u;
        if (!hash) hash = 1u;
    }
    for (int i = 0; i < s_d3d.vp_vs_n; i++)''')
rep('''    int ni = rsx_vp_decompile(vuc, vlen, hlsl, sizeof hlsl);
    if (ni <= 0) return -1;
    if (getenv("VP_DUMP")) { static int _d=0; if (PS3_LOG_FIRST(_d, 4)) {''',
    '''    int ni = rsx_vp_decompile(vuc, vlen, hlsl, sizeof hlsl);
    if (ni <= 0) return -1;
    rsc_note_translation(&s_rsc, RSC_STAGE_VS, hash);
    if (getenv("VP_DUMP")) { static int _d=0; if (PS3_LOG_FIRST(_d, 4)) {''')
rep('''    HRESULT hr = D3DCompile(hlsl, strlen(hlsl), "guest_vp2", NULL, NULL,
                            "main", "vs_5_0", 0, 0, &vb, &e);''',
    '''    char rsc_detail[48]; snprintf(rsc_detail, sizeof rsc_detail, "vs_hash=0x%08X", hash);
    HRESULT hr = rsc_compile(&s_rsc, RSC_STAGE_VS, hlsl, strlen(hlsl), "guest_vp2",
                             "main", "vs_5_0", 0, 0, &vb, &e, rsc_detail);''')

# 5. FP: one insert routine for pipelines and (level >= 1) remembered failures
rep('''static ID3D12PipelineState* vp_get_fp_pso(int vs_idx, u32 fp_addr, u32 blend, int nrt,
                                          DXGI_FORMAT rtfmt, int exp32, u32 cmask, u32 cull,
                                          u32 cube_mask, const rsx_fp_shadow_desc* shadow,
                                          u32 shadow_key, u32 depth, const rsx_color_xfer* xf)
{''',
    '''/* RSX_SHADER_CACHE >= 1: remember that a program does not translate or
 * compile under this key, as an entry with no pipeline, so the lookup returns
 * NULL -- the same answer as before -- without decompiling and compiling it
 * again on every frame. Evicts like the insert at the end of vp_get_fp_pso. */
static void vp_fp_remember_failure(u32 fp_addr, int vs_idx, u32 vs_hash, u32 blend, int nrt, DXGI_FORMAT rtfmt,
                                   int exp32, u32 uhash, u32 cmask, u32 cull, u32 depth, u32 cube_mask,
                                   u32 shadow_key, u8 xs, const u8 xg[16], const u8 xe[16])
{
    if (s_d3d.vp_fp_n >= VP_FP_CACHE) {
        s_fpm_epoch++;   /* a remembered pipeline may be the one released here */
        if (s_d3d.vp_fp[0].pso) s_d3d.vp_fp[0].pso->lpVtbl->Release(s_d3d.vp_fp[0].pso);
        memmove(&s_d3d.vp_fp[0], &s_d3d.vp_fp[1], sizeof(VPFPEntry) * (VP_FP_CACHE - 1));
        s_d3d.vp_fp_n = VP_FP_CACHE - 1;
    }
    VPFPEntry* q = &s_d3d.vp_fp[s_d3d.vp_fp_n];
    q->fp_addr = fp_addr; q->vs_idx = vs_idx; q->vs_hash = vs_hash; q->gen = s_d3d.vp_gen;
    q->blend = blend; q->nrt = nrt; q->rtfmt = (u32)rtfmt; q->exp32 = exp32; q->ucode_hash = uhash;
    q->cmask = cmask; q->cull = cull; q->depth = depth; q->cube_mask = cube_mask;
    q->shadow_key = shadow_key; q->xf_srgb = xs;
    memcpy(q->xf_gamma, xg, sizeof q->xf_gamma); memcpy(q->xf_expand, xe, sizeof q->xf_expand);
    q->pso = NULL;
    s_d3d.vp_fp_n++;
}

static ID3D12PipelineState* vp_get_fp_pso(int vs_idx, u32 fp_addr, u32 blend, int nrt,
                                          DXGI_FORMAT rtfmt, int exp32, u32 cmask, u32 cull,
                                          u32 cube_mask, const rsx_fp_shadow_desc* shadow,
                                          u32 shadow_key, u32 depth, const rsx_color_xfer* xf)
{''')

# the key as looked up, kept before xs can be cleared below
rep('''    const int xmasks = (rsx_fp_texture_gamma_units(vm_base + off, 4096, xg) |
                        rsx_fp_texture_expand_units(vm_base + off, 4096, xe)) != 0;
''',
    '''    const int xmasks = (rsx_fp_texture_gamma_units(vm_base + off, 4096, xg) |
                        rsx_fp_texture_expand_units(vm_base + off, 4096, xe)) != 0;
    const u8 xs_key = xs;   /* RSX_SHADER_CACHE >= 1 stores the key as looked up */
''')

rep('''    if (n <= 0) { static int _e=0; if(PS3_LOG_FIRST(_e, 16)) printf("[FP] decompile fail (fp=0x%08X)\\n", fp_addr);
                  shtrace("translate_fail", fp_addr, uhash, cube_mask, rtfmt, nrt, NULL); return NULL; }''',
    '''    if (n <= 0) { static int _e=0; if(PS3_LOG_FIRST(_e, 16)) printf("[FP] decompile fail (fp=0x%08X)\\n", fp_addr);
                  shtrace("translate_fail", fp_addr, uhash, cube_mask, rtfmt, nrt, NULL);
                  if (s_rsc.level > 0)
                      vp_fp_remember_failure(fp_addr, vs_idx, vs_hash, blend, nrt, rtfmt, exp32, uhash, cmask,
                                             cull, depth, cube_mask, shadow_key, xs_key, xg, xe);
                  return NULL; }
    rsc_note_translation(&s_rsc, RSC_STAGE_PS, uhash);''')

rep('''    ID3DBlob* pb = NULL; ID3DBlob* e = NULL;
    HRESULT hr = D3DCompile(hlsl, strlen(hlsl), "guest_fp", NULL, NULL,
                            "main", "ps_5_0", 0, 0, &pb, &e);''',
    '''    ID3DBlob* pb = NULL; ID3DBlob* e = NULL;
    char rsc_detail[64]; snprintf(rsc_detail, sizeof rsc_detail, "fp=0x%08X ucode=0x%08X", fp_addr, uhash);
    HRESULT hr = rsc_compile(&s_rsc, RSC_STAGE_PS, hlsl, strlen(hlsl), "guest_fp",
                             "main", "ps_5_0", 0, 0, &pb, &e, rsc_detail);''')

rep('''            printf("[FP] PS compile FAIL (fp=0x%08X): %s\\n", fp_addr,
                   e ? (const char*)e->lpVtbl->GetBufferPointer(e) : "?");
        if (shtrace_on()) {''',
    '''            printf("[FP] PS compile FAIL (fp=0x%08X): %s\\n", fp_addr,
                   e ? (const char*)e->lpVtbl->GetBufferPointer(e) : "?");
        if (s_rsc.level > 0 && hr == E_FAIL)   /* a compile error, not a transient failure */
            vp_fp_remember_failure(fp_addr, vs_idx, vs_hash, blend, nrt, rtfmt, exp32, uhash, cmask, cull,
                                   depth, cube_mask, shadow_key, xs_key, xg, xe);
        if (shtrace_on()) {''')

rep('''    ID3D12PipelineState* pso = NULL;
    hr = s_d3d.device->lpVtbl->CreateGraphicsPipelineState(
        s_d3d.device, &pd, &IID_ID3D12PipelineState, (void**)&pso);
    pb->lpVtbl->Release(pb);''',
    '''    ID3D12PipelineState* pso = NULL;
    hr = rsc_create_pso(&s_rsc, s_d3d.device, &pd, s_vp_root_sig_id, &pso, rsc_detail);
    pb->lpVtbl->Release(pb);''')

rep('''    s_d3d.vp_fp[s_d3d.vp_fp_n].xf_srgb = xs;
''',
    '''    /* Level 0 keys the entry with xs as compiled -- 0 when the sRGB rewrite did
     * not apply, a key the lookup (xs = 1) never matches; level >= 1 keys it as
     * looked up. */
    s_d3d.vp_fp[s_d3d.vp_fp_n].xf_srgb = s_rsc.level > 0 ? xs_key : xs;
''')

# 6. once per frame, after the frame's work is submitted
rep('''    s_d3d.frame_count++;

    /* VPVB_GROW_AT_FRAME_END: this frame is submitted and its per-frame offset''',
    '''    s_d3d.frame_count++;
    rsc_frame_end(&s_rsc);   /* RSX_SHADER_STATS lines; level 3 saves the pipeline library when quiet */

    /* VPVB_GROW_AT_FRAME_END: this frame is submitted and its per-frame offset''')

# 7. shutdown: save, report, release (before the device goes)
rep('''    wait_for_gpu();
    rtrb_shutdown();   /* RSX_RT_READBACK: no guest writes past this point */
''',
    '''    wait_for_gpu();
    rtrb_shutdown();   /* RSX_RT_READBACK: no guest writes past this point */
    rsc_shutdown(&s_rsc);
''')

P.write_bytes(s.replace('\n', '\r\n').encode('utf-8'))
print('patched', P)
