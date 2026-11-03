"""T178: replay the real box shaders (private VP C163B50D, FP 022C20C1 HLSL dumps) with the box matrices captured in T165 B1, on WARP,
over a synthetic ground and known test textures, and compare the pixels with an analytic reference. References come from numpy, not project code.
Run from the root under env_t169.cmd: generated\\analysis\\t169\\tools\\env_t169.cmd py -3 generated\\analysis\\t178\\tools\\box_replay_t178.py
Shows whether the translated shaders recover the footprint UV from depth, and what a flat texture or wrong depth looks like."""
import glob, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
A = ROOT / 'generated/analysis'
sys.path.insert(0, str(A / 't169/tools'))
from rsxi_parse_t169 import read_events

VS = glob.glob(str(A / 't171/ab/runtime-TA-*/rsxi/shaders/vp_C163B50D.hlsl'))[0]
FS = glob.glob(str(A / 't169/ab/runtime-VG-*/rsxi/shaders/fp_022C20C1.hlsl'))[0]
EV = glob.glob(str(A / 't165/ab/runtime-B1-*/rsxi/frames/f003500/events.jsonl*'))[0]
W, H = 1272, 715

C = r'''
#define COBJMACROS
#define INITGUID
#include <d3d11.h>
#include <d3dcompiler.h>
#include <stdio.h>
#include <stdlib.h>
static void* rd(const char* p, size_t* n) { FILE* f = fopen(p, "rb"); if (!f) { printf("open %s\n", p); exit(2); } fseek(f, 0, 2); *n = ftell(f); fseek(f, 0, 0);
    void* b = malloc(*n + 1); fread(b, 1, *n, f); ((char*)b)[*n] = 0; fclose(f); return b; }
static ID3DBlob* cc(const char* s, size_t n, const char* t) { ID3DBlob* b = 0, *e = 0; if (FAILED(D3DCompile(s, n, t, 0, 0, "main", t, 0, 0, &b, &e))) { printf("%s\n", (char*)ID3D10Blob_GetBufferPointer(e)); exit(3); } return b; }
/* usage: vs fs consts depth tex1 texw out */
int main(int c, char** v) {
    enum { W = 1272, H = 715 };
    ID3D11Device* d; ID3D11DeviceContext* x; D3D_FEATURE_LEVEL fl;
    if (FAILED(D3D11CreateDevice(0, D3D_DRIVER_TYPE_WARP, 0, 0, 0, 0, D3D11_SDK_VERSION, &d, &fl, &x))) return 4;
    size_t n; char* s = rd(v[1], &n); ID3DBlob* vb = cc(s, n, "vs_5_0"); s = rd(v[2], &n); ID3DBlob* pb = cc(s, n, "ps_5_0");
    ID3D11VertexShader* vs; ID3D11PixelShader* ps;
    ID3D11Device_CreateVertexShader(d, ID3D10Blob_GetBufferPointer(vb), ID3D10Blob_GetBufferSize(vb), 0, &vs);
    ID3D11Device_CreatePixelShader(d, ID3D10Blob_GetBufferPointer(pb), ID3D10Blob_GetBufferSize(pb), 0, &ps);
    D3D11_INPUT_ELEMENT_DESC ie[16]; for (int i = 0; i < 16; i++) { D3D11_INPUT_ELEMENT_DESC e = { "ATTR", i, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 0, D3D11_INPUT_PER_VERTEX_DATA, 0 }; ie[i] = e; }
    ID3D11InputLayout* il; if (FAILED(ID3D11Device_CreateInputLayout(d, ie, 16, ID3D10Blob_GetBufferPointer(vb), ID3D10Blob_GetBufferSize(vb), &il))) return 5;
    float cube[36 * 4]; static const signed char idx[36] = {0,1,2,2,1,3,4,6,5,5,6,7,0,4,1,1,4,5,2,3,6,6,3,7,0,2,4,4,2,6,1,5,3,3,5,7};
    for (int i = 0; i < 36; i++) { int k = idx[i]; cube[i*4] = (k & 4) ? 1.f : -1.f; cube[i*4+1] = (k & 2) ? 1.f : -1.f; cube[i*4+2] = (k & 1) ? 1.f : -1.f; cube[i*4+3] = 1.f; }
    D3D11_BUFFER_DESC bd = { sizeof cube, D3D11_USAGE_DEFAULT, D3D11_BIND_VERTEX_BUFFER }; D3D11_SUBRESOURCE_DATA sd = { cube }; ID3D11Buffer* vbuf; ID3D11Device_CreateBuffer(d, &bd, &sd, &vbuf);
    void* k = rd(v[3], &n); D3D11_BUFFER_DESC cd = { (UINT)n, D3D11_USAGE_DEFAULT, D3D11_BIND_CONSTANT_BUFFER }; sd.pSysMem = k; ID3D11Buffer* cb; ID3D11Device_CreateBuffer(d, &cd, &sd, &cb);
    D3D11_TEXTURE2D_DESC td = { W, H, 1, 1, DXGI_FORMAT_R8G8B8A8_UNORM, {1, 0}, D3D11_USAGE_DEFAULT, D3D11_BIND_SHADER_RESOURCE };
    sd.pSysMem = rd(v[4], &n); sd.SysMemPitch = W * 4; ID3D11Texture2D* zt; ID3D11Device_CreateTexture2D(d, &td, &sd, &zt);
    int tw = atoi(v[6]); td.Width = td.Height = tw; td.Format = DXGI_FORMAT_R8G8B8A8_UNORM; sd.pSysMem = rd(v[5], &n); sd.SysMemPitch = tw * 4;  /* the byte in every channel, as the backend's 0x1000 mapping */ ID3D11Texture2D* t1; ID3D11Device_CreateTexture2D(d, &td, &sd, &t1);
        ID3D11ShaderResourceView* s0, *s1, *s11; ID3D11Device_CreateShaderResourceView(d, (ID3D11Resource*)zt, 0, &s0); ID3D11Device_CreateShaderResourceView(d, (ID3D11Resource*)t1, 0, &s1);
    float white = 1; (void)white; unsigned char wb[4] = {255, 255, 255, 255}; td.Width = td.Height = 1; td.Format = DXGI_FORMAT_R8G8B8A8_UNORM; sd.pSysMem = wb; sd.SysMemPitch = 4; ID3D11Texture2D* tw1; ID3D11Device_CreateTexture2D(d, &td, &sd, &tw1); ID3D11Device_CreateShaderResourceView(d, (ID3D11Resource*)tw1, 0, &s11);
    D3D11_SAMPLER_DESC pd = { D3D11_FILTER_MIN_MAG_MIP_POINT, D3D11_TEXTURE_ADDRESS_CLAMP, D3D11_TEXTURE_ADDRESS_CLAMP, D3D11_TEXTURE_ADDRESS_CLAMP }; pd.MaxLOD = 1000;
    ID3D11SamplerState* sp, *sl; ID3D11Device_CreateSamplerState(d, &pd, &sp); pd.Filter = D3D11_FILTER_MIN_MAG_MIP_LINEAR; ID3D11Device_CreateSamplerState(d, &pd, &sl);
    td.Width = W; td.Height = H; td.Format = DXGI_FORMAT_R32G32B32A32_FLOAT; td.BindFlags = D3D11_BIND_RENDER_TARGET; ID3D11Texture2D* rt; ID3D11Device_CreateTexture2D(d, &td, 0, &rt); ID3D11RenderTargetView* rv; ID3D11Device_CreateRenderTargetView(d, (ID3D11Resource*)rt, 0, &rv);
    float clr[4] = {0, 0, 0, -1}; ID3D11DeviceContext_ClearRenderTargetView(x, rv, clr);
    D3D11_RASTERIZER_DESC rs = { D3D11_FILL_SOLID, D3D11_CULL_NONE }; rs.DepthClipEnable = TRUE; ID3D11RasterizerState* rr; ID3D11Device_CreateRasterizerState(d, &rs, &rr); ID3D11DeviceContext_RSSetState(x, rr);
    D3D11_VIEWPORT vp = {0, 0, W, H, 0, 1}; ID3D11DeviceContext_RSSetViewports(x, 1, &vp); ID3D11DeviceContext_OMSetRenderTargets(x, 1, &rv, 0);
    UINT st = 16, of = 0; ID3D11DeviceContext_IASetInputLayout(x, il); ID3D11DeviceContext_IASetVertexBuffers(x, 0, 1, &vbuf, &st, &of); ID3D11DeviceContext_IASetPrimitiveTopology(x, D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    ID3D11DeviceContext_VSSetShader(x, vs, 0, 0); ID3D11DeviceContext_PSSetShader(x, ps, 0, 0); ID3D11DeviceContext_VSSetConstantBuffers(x, 0, 1, &cb);
    ID3D11DeviceContext_PSSetShaderResources(x, 0, 1, &s0); ID3D11DeviceContext_PSSetShaderResources(x, 1, 1, &s1); ID3D11DeviceContext_PSSetShaderResources(x, 11, 1, &s11);
    ID3D11DeviceContext_PSSetSamplers(x, 0, 1, &sp); ID3D11DeviceContext_PSSetSamplers(x, 1, 1, &sl); ID3D11DeviceContext_PSSetSamplers(x, 11, 1, &sl);
    ID3D11DeviceContext_Draw(x, 36, 0);
    td.Usage = D3D11_USAGE_STAGING; td.BindFlags = 0; td.CPUAccessFlags = D3D11_CPU_ACCESS_READ; ID3D11Texture2D* rb; ID3D11Device_CreateTexture2D(d, &td, 0, &rb); ID3D11DeviceContext_CopyResource(x, (ID3D11Resource*)rb, (ID3D11Resource*)rt);
    D3D11_MAPPED_SUBRESOURCE m; ID3D11DeviceContext_Map(x, (ID3D11Resource*)rb, 0, D3D11_MAP_READ, 0, &m); FILE* o = fopen(v[7], "wb"); for (int y = 0; y < H; y++) fwrite((char*)m.pData + y * m.RowPitch, 16, W, o); fclose(o);
    return 0;
}
'''


def blob(n):
    """n x n bytes: 255 at the rim (transparent), dark in a smooth centre."""
    g = (np.arange(n) + .5) / n * 2 - 1
    x, y = np.meshgrid(g, g)
    a = np.clip(1.2 - 1.6 * np.hypot(x, y), 0, .9)
    return np.uint8(np.round(255 * (1 - a)))


def sample(t, u, v):
    """Linear filter, clamp to edge. Texture row 0 is v = 0, as the D3D sampler reads it."""
    n = t.shape[0]
    fx, fy = np.clip(u, 0, 1) * n - .5, np.clip(v, 0, 1) * n - .5
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    ax, ay = fx - x0, fy - y0
    g = lambda a, b: t[np.clip(b, 0, n - 1), np.clip(a, 0, n - 1)] / 255.
    return (g(x0, y0) * (1 - ax) + g(x0 + 1, y0) * ax) * (1 - ay) + (g(x0, y0 + 1) * (1 - ax) + g(x0 + 1, y0 + 1) * ax) * ay


def run(exe, d, b, tex, zmode, tag):
    c = {x[0]: np.array(x[1:], float) for x in b['guest']['vp_consts']}
    M, I = (np.array([c[k + i] for i in range(4)]).T for k in (256, 260))
    k = np.zeros((514, 4), np.float32)
    for i, v in c.items():
        k[i] = np.nan_to_num(v, nan=0., posinf=0., neginf=0.)
    k[512] = (1, 1, .5, 1)   # vp_posscale, vp_posoffset as the backend computes them
    k[513] = (0, 0, .5, 0)
    # Scene: ground plane through the box centre, local z = 0, for each pixel of the ray through it.
    px, py = np.meshgrid(np.arange(W) + .5, np.arange(H) + .5)
    nx, ny = px / W * 2 - 1, 1 - py / H * 2
    # local z(ndc z) along the ray is a projective function of ndc z; solve I*(x,y,z,1) local z = 0
    a = I[2, 0] * nx + I[2, 1] * ny + I[2, 3]
    z = -a / I[2, 2]
    if zmode == 'far':
        z = np.full_like(z, 1.)
    elif zmode == 'near':
        z = z - .02                      # ground well in front of the box
    dd = np.clip(z * .5 + .5, 0, 1)
    k24 = np.minimum(np.uint32(dd * 16777215 + .5), 16777215)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3] = (k24 >> 8) & 255, k24 & 255, 0, k24 >> 16
    z2 = k24 / 2 ** 24 * 2 - 1
    den = I[3, 0] * nx + I[3, 1] * ny + I[3, 2] * z2 + I[3, 3]
    u = (I[0, 0] * nx + I[0, 1] * ny + I[0, 2] * z2 + I[0, 3]) / den / 2 + .5
    v = (I[1, 0] * nx + I[1, 1] * ny + I[1, 2] * z2 + I[1, 3]) / den / 2 + .5
    ref = 1 - sample(tex, u, v)
    P = Path(d)
    (P / 'k').write_bytes(k.tobytes()); (P / 'z').write_bytes(rgba.tobytes()); (P / 't').write_bytes(np.repeat(tex.reshape(-1, 1), 4, 1).tobytes())
    r = subprocess.run([str(exe), VS, FS, str(P / 'k'), str(P / 'z'), str(P / 't'), str(tex.shape[0]), str(P / 'o')], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f'harness rc={r.returncode}: {r.stdout[-800:]}')
    o = np.frombuffer((P / 'o').read_bytes(), np.float32).reshape(H, W, 4)[..., 3]
    m = o >= 0
    # pixels next to a box edge or with a texel-size UV jump are not compared
    err = np.abs(o - ref)[m]
    print(f'{tag}: covered {int(m.sum())} px; alpha min {o[m].min():.3f} max {o[m].max():.3f} std {o[m].std():.3f}; reference std {ref[m].std():.3f}; '
          f'|out-ref| p50 {np.percentile(err, 50):.4f} p99 {np.percentile(err, 99):.4f} max {err.max():.4f}')
    return o[m], ref[m]


def main():
    rows = list(read_events(EV))
    box = {r['op']: r for r in rows if r.get('e') == 'draw' and r['guest'].get('fp') == '0x022C20C1'}
    fails = 0
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / 'h.c').write_text(C)
        exe = Path(d) / 'h.exe'
        r = subprocess.run(['clang-cl', '/nologo', '/O1', '/MD', '/w', '-std:c17', '/D_CRT_SECURE_NO_WARNINGS', str(Path(d) / 'h.c'), f'/Fe{exe}', f'/Fo{d}\\', '/link',
                            'd3d11.lib', 'd3dcompiler.lib', 'dxguid.lib'], capture_output=True, text=True)
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-800:])
            return 1
        for op, n in ((911, 8), (913, 8), (912, 16)):
            b = box[op]
            o, ref = run(exe, d, b, blob(n), 'ground', f'op {op} {n}x{n} blob, ground in box')
            if np.percentile(np.abs(o - ref), 99) > .02 or o.std() < .02:
                print('  FAIL: translated shader does not match the analytic footprint'); fails += 1
            o, ref = run(exe, d, b, blob(n), 'near', f'op {op} {n}x{n} blob, ground in front')
            if np.percentile(np.abs(o - ref), 99) > .02 or (n == 8 and o.max() > .02):   # z - 0.02 stays inside the larger 16x16 box
                print('  FAIL: rim-transparent texture must leave ground outside the box untouched'); fails += 1
            o, ref = run(exe, d, b, np.full((n, n), 168, np.uint8), 'ground', f'op {op} {n}x{n} flat 168')
            if abs(o.mean() - 87 / 255) > .01 or o.std() > .002:
                print('  FAIL: flat control'); fails += 1
            o, ref = run(exe, d, b, blob(n), 'far', f'op {op} {n}x{n} blob, depth 1.0')
            if o.max() > .02:
                print('  FAIL: far depth control'); fails += 1
    print('box_replay failures:', fails)
    return 1 if fails else 0


sys.exit(main())
