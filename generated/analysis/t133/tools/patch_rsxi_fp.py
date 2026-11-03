"""T133: RSXI shader events carry per-precision instruction counts and the raw FP ucode (one-shot)."""
import sys
p = sys.argv[1] + '/libs/video/rsx_d3d12_backend.c'
s = open(p, newline='', encoding='utf-8').read().replace('\r\n', '\n')


def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    assert n == cnt, (a[:90], n)
    s = s.replace(a, b)


rep('''        int n = -1; u32 hash = 0;
        snprintf(path, sizeof path, "%s/shaders/fp_%08X.hlsl", s_rsxi.dir, fp);
        if (vm_base && off != 0xFFFFFFFFu) {
            static char hl[RSX_FP_HLSL_BUFFER_SIZE];
            hash = rsx_fp_code_hash(vm_base + off, fp_span(vm_base + off));
            n = rsx_fp_decompile(vm_base + off, fp_span(vm_base + off), s_rsxi.fp_exp[i] ? 0x40u : 0u, hl, sizeof hl);
            if (n > 0 && GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) {
                FILE* hf = fopen(path, "w");
                if (hf) { fprintf(hf, "/* fp=0x%08X code_hash=0x%08X instrs=%d */\\n%s", fp, hash, n, hl); fclose(hf); }
            }
        }
        if (n > 0)
            fprintf(s_rsxi.ev, "{\\"e\\":\\"shader\\",\\"fp\\":\\"0x%08X\\",\\"code_hash\\":\\"0x%08X\\",\\"decompile\\":\\"ok\\","
                               "\\"instructions\\":%d,\\"hlsl\\":\\"shaders/fp_%08X.hlsl\\"}\\n", fp, hash, n, fp);
''', '''        int n = -1; u32 hash = 0;
        u32 prec[4] = {0, 0, 0, 0};   /* OPDEST precision counts: FP32, FP16, FX12, FX9 */
        snprintf(path, sizeof path, "%s/shaders/fp_%08X.hlsl", s_rsxi.dir, fp);
        if (vm_base && off != 0xFFFFFFFFu) {
            static char hl[RSX_FP_HLSL_BUFFER_SIZE];
            const u32 span = fp_span(vm_base + off);
            hash = rsx_fp_code_hash(vm_base + off, span);
            rsx_fp_precision_counts(vm_base + off, span, prec);
            n = rsx_fp_decompile(vm_base + off, span, s_rsxi.fp_exp[i] ? 0x40u : 0u, hl, sizeof hl);
            if (n > 0 && GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) {
                FILE* hf = fopen(path, "w");
                if (hf) { fprintf(hf, "/* fp=0x%08X code_hash=0x%08X instrs=%d */\\n%s", fp, hash, n, hl); fclose(hf); }
                /* The guest ucode itself (PS3 halfword order), for offline
                 * re-decompilation; the capture directory is private. */
                char upath[512];
                snprintf(upath, sizeof upath, "%s/shaders/fp_%08X.ucode", s_rsxi.dir, fp);
                FILE* uf = fopen(upath, "wb");
                if (uf) { fwrite(vm_base + off, 1, span, uf); fclose(uf); }
            }
        }
        if (n > 0)
            fprintf(s_rsxi.ev, "{\\"e\\":\\"shader\\",\\"fp\\":\\"0x%08X\\",\\"code_hash\\":\\"0x%08X\\",\\"decompile\\":\\"ok\\","
                               "\\"instructions\\":%d,\\"prec\\":[%u,%u,%u,%u],\\"prec_clamp\\":%d,\\"hlsl\\":\\"shaders/fp_%08X.hlsl\\"}\\n",
                    fp, hash, n, prec[0], prec[1], prec[2], prec[3], rsx_fp_precision_clamp_on(), fp);
''')
open(p, 'w', newline='', encoding='utf-8').write(s.replace('\n', '\r\n'))
print('ok')
