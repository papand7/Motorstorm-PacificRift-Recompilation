"""overlap60: add PS3_SAMPLE_EXACT (exact .pdata attribution) to an ISOLATED copy of runtime/ppu/ppu_loader.cpp.
usage: py -3 patch_samp_exact.py <path to ppu_loader.cpp>"""
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)


rep("static SampHG*  s_samp_map = nullptr;\nstatic uint64_t s_samp_n   = 0;\n", r"""static SampHG*  s_samp_map = nullptr;
static uint64_t s_samp_n   = 0;

/* PS3_SAMPLE_EXACT=1 (overlap60): attribute by the exe's own .pdata bounds, not
 * by [entry, next_entry) alone. The extent rule credits runtime code linked after
 * a lifted body (sys_timer's usleep spin, MFC helpers) to that body; with this
 * on, such samples miss, and PS3_SAMPLE_MAIN's stack walk credits the lifted
 * caller. The table is read once from the PE image, so the lookup takes no lock
 * while the sampled thread is suspended. Chained entries resolve to their
 * primary function. */
static int        s_samp_exact;
static uintptr_t  s_pd_base, s_pd_lo, s_pd_hi;
static uint32_t*  s_pd_beg;   /* RVA, sorted */
static uint32_t*  s_pd_end;
static uint32_t*  s_pd_pri;   /* primary function start RVA */
static uint32_t   s_pd_n;

static void samp_build_pdata(void)
{
    HMODULE m = GetModuleHandleW(NULL);
    if (!m) return;
    const uint8_t* b = (const uint8_t*)m;
    const IMAGE_NT_HEADERS64* nt = (const IMAGE_NT_HEADERS64*)(b + ((const IMAGE_DOS_HEADER*)b)->e_lfanew);
    const IMAGE_DATA_DIRECTORY d = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXCEPTION];
    if (!d.VirtualAddress || d.Size < sizeof(RUNTIME_FUNCTION)) return;
    const RUNTIME_FUNCTION* rf = (const RUNTIME_FUNCTION*)(b + d.VirtualAddress);
    uint32_t n = d.Size / (uint32_t)sizeof(RUNTIME_FUNCTION);
    s_pd_beg = (uint32_t*)malloc(n * 4u); s_pd_end = (uint32_t*)malloc(n * 4u); s_pd_pri = (uint32_t*)malloc(n * 4u);
    if (!s_pd_beg || !s_pd_end || !s_pd_pri) return;
    for (uint32_t i = 0; i < n; i++) {
        const RUNTIME_FUNCTION* f = &rf[i];
        for (int depth = 0; depth < 16; depth++) {
            uint32_t ud = f->UnwindData;
            if (ud & 1u) { f = (const RUNTIME_FUNCTION*)(b + (ud & ~1u)); continue; }
            const uint8_t* ui = b + ud;
            if (!((ui[0] >> 3) & 0x4)) break;               /* UNW_FLAG_CHAININFO */
            uint32_t codes = ((uint32_t)ui[2] + 1u) & ~1u;   /* unwind code slots, padded to even */
            f = (const RUNTIME_FUNCTION*)(ui + 4 + codes * 2);
        }
        s_pd_beg[i] = rf[i].BeginAddress; s_pd_end[i] = rf[i].EndAddress; s_pd_pri[i] = f->BeginAddress;
    }
    s_pd_n = n; s_pd_base = (uintptr_t)b;
    s_pd_lo = s_pd_base; s_pd_hi = s_pd_base + nt->OptionalHeader.SizeOfImage;
}

/* index of the .pdata entry containing rip, or -1 (leaf code has none) */
static int64_t samp_pd_find(uintptr_t rip)
{
    if (!s_pd_n || rip < s_pd_lo || rip >= s_pd_hi) return -1;
    uint32_t rva = (uint32_t)(rip - s_pd_base), lo = 0, hi = s_pd_n;
    while (lo < hi) { uint32_t mid = (lo + hi) / 2; if (s_pd_beg[mid] <= rva) lo = mid + 1; else hi = mid; }
    if (!lo) return -1;
    return rva < s_pd_end[lo - 1] ? (int64_t)(lo - 1) : -1;
}

/* first map index whose host start is exactly h, or -1 */
static int64_t samp_map_exact(uintptr_t h)
{
    uint64_t lo = 0, hi = s_samp_n;
    while (lo < hi) { uint64_t mid = (lo + hi) / 2; if (s_samp_map[mid].h < h) lo = mid + 1; else hi = mid; }
    return (lo < s_samp_n && s_samp_map[lo].h == h) ? (int64_t)lo : -1;
}
""")

rep("""    uintptr_t next = (k + 1 < s_samp_n) ? s_samp_map[k + 1].h : s_samp_map[k].h + 0x20000;
    if (rip >= next) return 0;
    return s_samp_map[k].spu ? (0x80000000u | s_samp_map[k].g) : s_samp_map[k].g;""",
"""    uintptr_t next = (k + 1 < s_samp_n) ? s_samp_map[k + 1].h : s_samp_map[k].h + 0x20000;
    if (rip >= next) return 0;
    if (s_samp_exact && s_pd_n) {
        int64_t p = samp_pd_find(rip);
        if (p >= 0) {   /* inside a function with unwind data: a lifted body only if its primary start is one */
            int64_t e = samp_map_exact(s_pd_base + s_pd_pri[p]);
            if (e < 0) return 0;
            k = (uint64_t)e;
        } else {        /* leaf code: keep the extent, unless the body before it has .pdata ending before rip */
            int64_t q = samp_pd_find(s_samp_map[k].h);
            if (q >= 0 && rip >= s_pd_base + s_pd_end[q]) return 0;
        }
    }
    return s_samp_map[k].spu ? (0x80000000u | s_samp_map[k].g) : s_samp_map[k].g;""")

# self-test runs after the map is built; samp_lookup is defined later, so forward-declare it.
rep("static void samp_build_map(void)\n{", "static uint32_t samp_lookup(uintptr_t rip);\nstatic void samp_build_map(void)\n{")
rep("""            (unsigned long long)function_table_count, nspu);""",
r"""            (unsigned long long)function_table_count, nspu);
    s_samp_exact = getenv("PS3_SAMPLE_EXACT") && atoi(getenv("PS3_SAMPLE_EXACT")) != 0;
    if (s_samp_exact) {
        samp_build_pdata();
        /* self-test: every mapped body with unwind data maps back to itself one byte in
         * (identical-code folding: any entry sharing the host address is acceptable);
         * this function (runtime code) must map to no guest body. */
        uint64_t with = 0, ok = 0, bad = 0;
        for (uint64_t i = 0; i < s_samp_n; i++) {
            if (samp_pd_find(s_samp_map[i].h) < 0) continue;
            with++;
            uint32_t got = samp_lookup(s_samp_map[i].h + 1);
            bool hit = false;
            for (int64_t e = samp_map_exact(s_samp_map[i].h); e >= 0 && (uint64_t)e < s_samp_n && s_samp_map[e].h == s_samp_map[i].h; e++) {
                uint32_t w = s_samp_map[e].spu ? (0x80000000u | s_samp_map[e].g) : s_samp_map[e].g;
                if (w == got) { hit = true; break; }
            }
            if (hit) ok++; else bad++;
        }
        uint32_t self = samp_lookup((uintptr_t)&samp_build_pdata + 8);
        fprintf(stderr, "[samp] exact: pdata %u entries; mapped bodies with pdata %llu of %llu; self-test ok %llu bad %llu; runtime probe -> %s\n",
                s_pd_n, (unsigned long long)with, (unsigned long long)s_samp_n, (unsigned long long)ok,
                (unsigned long long)bad, self ? "MAPPED (bad)" : "none (ok)");
    }""")
open(p, 'w', encoding='utf-8').write(s)
print('patched', p)
