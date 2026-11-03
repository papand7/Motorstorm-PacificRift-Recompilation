from pathlib import Path
p = Path('ps3recomp-t169/libs/video/tests/test_t169_visual_ab_warp.c')
s = p.read_bytes().decode()
pairs = [
    ("    D3D12_DESCRIPTOR_HEAP_DESC hd = {0}; hd.Type = D3D12_DESCRIPTOR_HEAP_TYPE_DSV; hd.NumDescriptors = 1;\r\n",
     "    ID3D12Resource* dcb = NULL; float* k = NULL;   /* the shared cb is one 256-byte slot; this needs two */\r\n"
     "    { D3D12_HEAP_PROPERTIES up = {0}; up.Type = D3D12_HEAP_TYPE_UPLOAD; D3D12_RANGE nr = {0, 0};\r\n"
     "      ID3D12Device_CreateCommittedResource(dev, &up, D3D12_HEAP_FLAG_NONE, &bd, D3D12_RESOURCE_STATE_GENERIC_READ, NULL, &IID_ID3D12Resource, (void**)&dcb);\r\n"
     "      ID3D12Resource_Map(dcb, 0, &nr, (void**)&k); }\r\n"
     "    D3D12_DESCRIPTOR_HEAP_DESC hd = {0}; hd.Type = D3D12_DESCRIPTOR_HEAP_TYPE_DSV; hd.NumDescriptors = 1;\r\n"),
    ("        float* k = (float*)cb_map;\r\n", ""),
    ("        UINT64 gv = ID3D12Resource_GetGPUVirtualAddress(cb);\r\n", "        UINT64 gv = ID3D12Resource_GetGPUVirtualAddress(dcb);\r\n"),
    ("    ID3D12Resource_Release(rt); ID3D12Resource_Release(dt); ID3D12Resource_Release(rb); ID3D12Resource_Release(qb);\r\n",
     "    ID3D12Resource_Release(rt); ID3D12Resource_Release(dt); ID3D12Resource_Release(rb); ID3D12Resource_Release(qb); ID3D12Resource_Release(dcb);\r\n"),
]
for a, b in pairs:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
s = s.replace('int main(void)\r\n{\r\n    test_profile();', 'int main(void)\r\n{\r\n    setvbuf(stdout, NULL, _IONBF, 0);\r\n    test_profile();')
p.write_bytes(s.encode())
print('ok')
