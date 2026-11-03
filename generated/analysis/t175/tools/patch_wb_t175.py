"""T175: adds RSX_VP_VB_WB to the backend. usage: py -3 patch_wb_t175.py <tree>"""
import sys
F = sys.argv[1] + '/libs/video/rsx_d3d12_backend.c'
s = open(F, encoding='utf-8', errors='surrogateescape', newline='').read()
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')


def sub(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)


sub('#include "ps3emu/vp_indexed.h"        /* RSX_VP_INDEXED: compact strips as unique vertices and a triangle index list */\n',
    '#include "ps3emu/vp_indexed.h"        /* RSX_VP_INDEXED: compact strips as unique vertices and a triangle index list */\n'
    '#include "ps3emu/vp_vb_heap.h"        /* RSX_VP_VB_WB: the VP vertex buffer in CPU-cached memory on a discrete GPU */\n')

helper = '''/* RSX_VP_VB_WB=1 (off by default, read once; ps3emu/vp_vb_heap.h): create the VP vertex buffer write-back in pool L0
 * on a discrete adapter. If the driver refuses, the UPLOAD heap, as without the switch. */
static HRESULT vp_vb_create(const D3D12_RESOURCE_DESC* bd, ID3D12Resource** out)
{
    static int m = -1;
    if (m < 0) {
        D3D12_FEATURE_DATA_ARCHITECTURE a = {0};
        const int known = SUCCEEDED(s_d3d.device->lpVtbl->CheckFeatureSupport(s_d3d.device, D3D12_FEATURE_ARCHITECTURE, &a, sizeof a));
        m = known ? vpwb_wanted(getenv("RSX_VP_VB_WB"), a.UMA != 0) : 0;
        if (m) fprintf(stderr, "[vp-wb] on%c", 10);
    }
    D3D12_HEAP_PROPERTIES hp = {0};
    if (m) {
        hp.Type = D3D12_HEAP_TYPE_CUSTOM; hp.CPUPageProperty = D3D12_CPU_PAGE_PROPERTY_WRITE_BACK; hp.MemoryPoolPreference = D3D12_MEMORY_POOL_L0;
        const HRESULT hr = s_d3d.device->lpVtbl->CreateCommittedResource(s_d3d.device, &hp, D3D12_HEAP_FLAG_NONE, bd,
            D3D12_RESOURCE_STATE_GENERIC_READ, NULL, &IID_ID3D12Resource, (void**)out);
        if (SUCCEEDED(hr)) return hr;
        fprintf(stderr, "[vp-wb] refused (0x%08lx), using the UPLOAD heap%c", (unsigned long)hr, 10);
        memset(&hp, 0, sizeof hp);
    }
    hp.Type = D3D12_HEAP_TYPE_UPLOAD;
    return s_d3d.device->lpVtbl->CreateCommittedResource(s_d3d.device, &hp, D3D12_HEAP_FLAG_NONE, bd,
        D3D12_RESOURCE_STATE_GENERIC_READ, NULL, &IID_ID3D12Resource, (void**)out);
}

'''
sub('static int vp_get_vs(const rsx_state* st)\n{\n', helper + 'static int vp_get_vs(const rsx_state* st)\n{\n')
sub('''        if (SUCCEEDED(s_d3d.device->lpVtbl->CreateCommittedResource(s_d3d.device, &hp,
                D3D12_HEAP_FLAG_NONE, &bd, D3D12_RESOURCE_STATE_GENERIC_READ, NULL,
                &IID_ID3D12Resource, (void**)&s_d3d.vp_vb)))
''', '''        if (SUCCEEDED(vp_vb_create(&bd, &s_d3d.vp_vb)))
''')
sub('''    if (SUCCEEDED(s_d3d.device->lpVtbl->CreateCommittedResource(s_d3d.device, &hp,
            D3D12_HEAP_FLAG_NONE, &bd, D3D12_RESOURCE_STATE_GENERIC_READ, NULL,
            &IID_ID3D12Resource, (void**)&nb))) {
        if (SUCCEEDED(nb->lpVtbl->Map(nb, 0, &nr, &nm)) && nm) ok = 1;
''', '''    if (SUCCEEDED(vp_vb_create(&bd, &nb))) {
        if (SUCCEEDED(nb->lpVtbl->Map(nb, 0, &nr, &nm)) && nm) ok = 1;
''')
sub('''    D3D12_HEAP_PROPERTIES hp = {0}; hp.Type = D3D12_HEAP_TYPE_UPLOAD;
    D3D12_RESOURCE_DESC bd = {0};
    bd.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER; bd.Height = 1;
    bd.DepthOrArraySize = 1; bd.MipLevels = 1; bd.SampleDesc.Count = 1;
    bd.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    bd.Width = (u64)new_cap * 256 * 2;
''', '''    D3D12_RESOURCE_DESC bd = {0};
    bd.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER; bd.Height = 1;
    bd.DepthOrArraySize = 1; bd.MipLevels = 1; bd.SampleDesc.Count = 1;
    bd.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    bd.Width = (u64)new_cap * 256 * 2;
''')
if crlf:
    s = s.replace('\n', '\r\n')
open(F, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(s)
