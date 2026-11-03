"""T120: add the D3D12 debug-layer error check to test_t120_depth_state.c (one-shot)."""
import sys
p = sys.argv[1]
s = open(p, newline='').read().replace('\r\n', '\n')
a = '''    IDXGIFactory4* f = NULL; IDXGIAdapter* a = NULL;
    if (FAILED(CreateDXGIFactory1(&IID_IDXGIFactory4, (void**)&f))) return 0;
    if (FAILED(IDXGIFactory4_EnumWarpAdapter(f, &IID_IDXGIAdapter, (void**)&a))) return 0;
    if (FAILED(D3D12CreateDevice((IUnknown*)a, D3D_FEATURE_LEVEL_11_0, &IID_ID3D12Device, (void**)&dev))) return 0;
'''
b = '''    IDXGIFactory4* f = NULL; IDXGIAdapter* a = NULL;
    ID3D12Debug* dbg = NULL;   /* debug layer when the Graphics Tools are installed */
    if (SUCCEEDED(D3D12GetDebugInterface(&IID_ID3D12Debug, (void**)&dbg))) { ID3D12Debug_EnableDebugLayer(dbg); ID3D12Debug_Release(dbg); }
    if (FAILED(CreateDXGIFactory1(&IID_IDXGIFactory4, (void**)&f))) return 0;
    if (FAILED(IDXGIFactory4_EnumWarpAdapter(f, &IID_IDXGIAdapter, (void**)&a))) return 0;
    if (FAILED(D3D12CreateDevice((IUnknown*)a, D3D_FEATURE_LEVEL_11_0, &IID_ID3D12Device, (void**)&dev))) return 0;
    if (FAILED(ID3D12Device_QueryInterface(dev, &IID_ID3D12InfoQueue, (void**)&iq))) iq = NULL;
'''
assert s.count(a) == 1
s = s.replace(a, b)
s = s.replace('static ID3DBlob *vsb, *psb; static ID3D12Resource *rt, *ds, *rb;\n',
              'static ID3DBlob *vsb, *psb; static ID3D12Resource *rt, *ds, *rb;\n'
              'static ID3D12InfoQueue* iq;   /* NULL without the debug layer */\n', 1)
c = '''    printf("test_t120_depth_state: %d checks, %d failed\\n", checks, fails);
    return fails ? 1 : 0;
}
'''
assert s.count(c) == 1, s.count(c)
d = '''    if (iq) {
        UINT64 n = ID3D12InfoQueue_GetNumStoredMessages(iq); int errs = 0;
        for (UINT64 i = 0; i < n; i++) {
            SIZE_T len = 0; ID3D12InfoQueue_GetMessage(iq, i, NULL, &len);
            D3D12_MESSAGE* m = (D3D12_MESSAGE*)malloc(len);
            if (m && SUCCEEDED(ID3D12InfoQueue_GetMessage(iq, i, m, &len)) &&
                m->Severity <= D3D12_MESSAGE_SEVERITY_ERROR) { errs++; printf("debug layer: %s\\n", m->pDescription); }
            free(m);
        }
        printf("debug layer: %llu messages, %d errors\\n", (unsigned long long)n, errs);
        CHECK(errs == 0, "no D3D12 debug-layer errors");
    } else printf("debug layer: not available (Graphics Tools not installed)\\n");
'''
s = s.replace(c, d + c)
s = s.replace('#include <string.h>\n', '#include <stdlib.h>\n#include <string.h>\n', 1)
open(p, 'w', newline='').write(s.replace('\n', '\r\n'))
print('ok')
