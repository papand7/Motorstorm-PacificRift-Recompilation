"""RSX_TEX_PBR without frame stalls: a pipeline whose rewritten pixel program is not translated yet
is built with the original program; the rewritten one is translated on the backend's worker
(shader_ready) and replaces it on a later use, at most RSX_TEX_PBR_UPGRADES (default 2) a frame.
Kk61/Kk62 stopped on GcKernel::Present() Timeout while the FIFO thread translated the rewritten
programs at race entry. rsx_draw_engine.c is CRLF.

usage: py -3 edit_pbr_engine3.py"""
import pathlib

V = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'libs' / 'video'


def edit(name, subs):
    p = V / name
    raw = p.read_bytes().decode('utf-8')
    crlf = '\r\n' in raw
    s = raw.replace('\r\n', '\n')
    for a, b in subs:
        assert s.count(a) == 1, (name, a[:80], s.count(a))
        s = s.replace(a, b)
    if crlf:
        s = s.replace('\n', '\r\n')
    p.write_bytes(s.encode('utf-8'))
    print('edited', name)


edit('rsx_draw_engine.c', [
("""    u16 pbr_consts[RSX_PBR_MAX_DOTS];
} eng_pipeline;""",
"""    u16 pbr_consts[RSX_PBR_MAX_DOTS];
    struct eng_pbr_job* pbr_job; /* RSX_TEX_PBR: the rewritten program while it translates, or NULL */
} eng_pipeline;"""),

("""static char s_ps_hlsl[256 * 1024];
""",
"""static char s_ps_hlsl[256 * 1024];
static char s_pbr_hlsl[256 * 1024];   /* RSX_TEX_PBR: s_ps_hlsl rewritten */
"""),

("""/* The pipeline eng_pipeline_get last returned, or NULL. */
static const eng_pipeline* s_pipe_last;
""",
"""/* The pipeline eng_pipeline_get last returned, or NULL. */
static const eng_pipeline* s_pipe_last;

/* RSX_TEX_PBR: a rewritten pixel program is new to every cache, and a race
 * entry asks for dozens at once (Kk61/Kk62: GcKernel::Present() Timeout
 * while the FIFO thread translated them). So a pipeline whose rewritten
 * program is not translated yet is built with the original one, which the
 * caches already hold; the backend translates the rewritten one on a worker
 * (shader_ready), and a later use of the pipeline swaps it in. At most
 * RSX_TEX_PBR_UPGRADES (default 2, 1..64) swaps a frame, because the new
 * pipeline's first draw still compiles in the driver. The original pipeline
 * is kept, not released, so nothing recorded this frame loses it; the
 * backend frees every pipeline at shutdown. */
typedef struct eng_pbr_job {
    char* vs;
    char* ps;
    rsx_be_render_state rs;
    rsx_vertex_layout_plan layout;
    rsx_be_format rt_fmt;
    u32 rt_count;
    rsx_pbr_info pbr;
    u32 polled;                 /* g.frames + 1 of the last shader_ready */
} eng_pbr_job;

static struct { u32 frame, used, waiting, lit, failed; int max; } s_pbr_up = { 0, 0, 0, 0, 0, -1 };

static eng_pbr_job* eng_pbr_job_new(const char* vs, const char* ps, const rsx_be_render_state* rs,
                                    const rsx_vertex_layout_plan* layout, rsx_be_format rt_fmt,
                                    u32 rt_count, const rsx_pbr_info* pbr)
{
    eng_pbr_job* j = (eng_pbr_job*)calloc(1, sizeof *j);
    if (!j) return NULL;
    const size_t nv = strlen(vs) + 1u, np = strlen(ps) + 1u;
    j->vs = (char*)malloc(nv);
    j->ps = (char*)malloc(np);
    if (!j->vs || !j->ps) { free(j->vs); free(j->ps); free(j); return NULL; }
    memcpy(j->vs, vs, nv);
    memcpy(j->ps, ps, np);
    j->rs = *rs;
    j->layout = *layout;
    j->rt_fmt = rt_fmt;
    j->rt_count = rt_count;
    j->pbr = *pbr;
    s_pbr_up.waiting++;
    return j;
}

static void eng_pbr_job_free(eng_pipeline* p)
{
    if (!p->pbr_job) return;
    free(p->pbr_job->vs);
    free(p->pbr_job->ps);
    free(p->pbr_job);
    p->pbr_job = NULL;
    s_pbr_up.waiting--;
}

static void eng_pbr_upgrade(eng_pipeline* p)
{
    eng_pbr_job* j = p->pbr_job;
    if (j->polled == g.frames + 1u) return;              /* asked this frame already */
    if (s_pbr_up.max < 0) {
        const char* e = getenv("RSX_TEX_PBR_UPGRADES");
        const int k = e && *e ? atoi(e) : 2;
        s_pbr_up.max = k < 1 ? 1 : k > 64 ? 64 : k;
    }
    if (s_pbr_up.frame != g.frames + 1u) { s_pbr_up.frame = g.frames + 1u; s_pbr_up.used = 0; }
    if (s_pbr_up.used >= (u32)s_pbr_up.max) return;
    j->polled = g.frames + 1u;
    const int r = g.be->shader_ready ? g.be->shader_ready(g.be->user, j->ps) : 1;
    if (r == 0) return;
    u32 h = 0;
    if (r > 0) {
        s_pbr_up.used++;
        h = g.be->pipeline_create(g.be->user, j->vs, j->ps, &j->rs, &j->layout,
                                  j->layout.stride, j->rt_fmt, j->rt_count);
    }
    if (h) {
        p->handle = h;
        p->tex_used = (u16)(eng_sampled_units(j->ps) & ~(1u << j->pbr.unit));
        p->pbr_unit = (s8)j->pbr.unit;
        p->pbr_src = (s8)j->pbr.src_unit;
        p->pbr_n = (u8)j->pbr.n_consts;
        for (u32 k = 0; k < RSX_PBR_MAX_DOTS; k++)
            p->pbr_consts[k] = (u16)(k < j->pbr.n_consts ? j->pbr.consts[k] : 0u);
        s_pbr_up.lit++;
    } else {
        s_pbr_up.failed++;
    }
    eng_pbr_job_free(p);
    const u32 n = s_pbr_up.lit + s_pbr_up.failed;
    if ((n & (n - 1u)) == 0 || !s_pbr_up.waiting)
        fprintf(stderr, "[tex-pbr] %u pipeline(s) lit, %u failed, %u waiting (frame %u)\\n",
                s_pbr_up.lit, s_pbr_up.failed, s_pbr_up.waiting, g.frames);
}
"""),

("""            const u32 i = g.pipe_index[h] - 1u;
            if (g.pipelines[i].key == key) {
                *out_fixed = g.pipelines[i].fixed;""",
"""            const u32 i = g.pipe_index[h] - 1u;
            if (g.pipelines[i].key == key) {
                if (g.pipelines[i].pbr_job) eng_pbr_upgrade(&g.pipelines[i]);
                *out_fixed = g.pipelines[i].fixed;"""),

("""    for (u32 i = 0; i < g.n_pipelines; i++)
        if (g.pipelines[i].key == key) {
            *out_fixed = g.pipelines[i].fixed;""",
"""    for (u32 i = 0; i < g.n_pipelines; i++)
        if (g.pipelines[i].key == key) {
            if (g.pipelines[i].pbr_job) eng_pbr_upgrade(&g.pipelines[i]);
            *out_fixed = g.pipelines[i].fixed;"""),

("""    rsx_pbr_info pbr;
    memset(&pbr, 0, sizeof pbr);
    pbr.unit = pbr.src_unit = -1;
""",
"""    rsx_pbr_info pbr;
    memset(&pbr, 0, sizeof pbr);
    pbr.unit = pbr.src_unit = -1;
    eng_pbr_job* pbr_job = NULL;
"""),

("""        /* RSX_TEX_PBR: sun-lit programs light with the texture pack's PBR maps
         * (rsx_pbr.h); the map takes a free unit the program declares 2D. */
        rsx_tp_init();
        if (fi > 0 && s_tp.pbr_on) {
            const int r = rsx_pbr_apply(s_ps_hlsl, sizeof s_ps_hlsl, cube_mask | vol_mask, &pbr);
            { static u32 logs = 0; if (r > 0 && PS3_LOG_FIRST(logs, 16))
                fprintf(stderr, "[tex-pbr] fp %016llx: %d dot(s) rewritten, albedo t%d, map t%d\\n",
                        (unsigned long long)eng_fp_debug_hash(fp_uc, fp_size), r, pbr.src_unit, pbr.unit); }
        }""",
"""        /* RSX_TEX_PBR: sun-lit programs light with the texture pack's PBR maps
         * (rsx_pbr.h); the map takes a free unit the program declares 2D. A
         * rewritten program not translated yet waits on the backend's worker
         * while the original draws (eng_pbr_upgrade). */
        rsx_tp_init();
        if (fi > 0 && s_tp.pbr_on) {
            memcpy(s_pbr_hlsl, s_ps_hlsl, strlen(s_ps_hlsl) + 1u);
            const int r = rsx_pbr_apply(s_pbr_hlsl, sizeof s_pbr_hlsl, cube_mask | vol_mask, &pbr);
            const int ready = r <= 0 ? -1 : g.be->shader_ready ? g.be->shader_ready(g.be->user, s_pbr_hlsl) : 1;
            { static u32 logs = 0; if (r > 0 && PS3_LOG_FIRST(logs, 16))
                fprintf(stderr, "[tex-pbr] fp %016llx: %d dot(s) rewritten, albedo t%d, map t%d, %s\\n",
                        (unsigned long long)eng_fp_debug_hash(fp_uc, fp_size), r, pbr.src_unit, pbr.unit,
                        ready > 0 ? "translated" : ready == 0 ? "translating" : "failed"); }
            if (ready > 0) {
                memcpy(s_ps_hlsl, s_pbr_hlsl, strlen(s_pbr_hlsl) + 1u);
            } else {
                if (ready == 0)
                    pbr_job = eng_pbr_job_new(s_vs_hlsl, s_pbr_hlsl, rs, layout, rt_fmt, rt_count, &pbr);
                memset(&pbr, 0, sizeof pbr);
                pbr.unit = pbr.src_unit = -1;
            }
        }"""),

("""    for (u32 k = 0; k < RSX_PBR_MAX_DOTS; k++)
        g.pipelines[g.n_pipelines].pbr_consts[k] = (u16)(k < pbr.n_consts ? pbr.consts[k] : 0u);
""",
"""    for (u32 k = 0; k < RSX_PBR_MAX_DOTS; k++)
        g.pipelines[g.n_pipelines].pbr_consts[k] = (u16)(k < pbr.n_consts ? pbr.consts[k] : 0u);
    g.pipelines[g.n_pipelines].pbr_job = handle ? pbr_job : NULL;
    if (!handle && pbr_job) { eng_pipeline tmp = { 0 }; tmp.pbr_job = pbr_job; eng_pbr_job_free(&tmp); }
"""),

("""    for (u32 i = 0; i < g.n_pipelines; i++)
        if (g.pipelines[i].handle) g.be->pipeline_release(g.be->user, g.pipelines[i].handle);
""",
"""    for (u32 i = 0; i < g.n_pipelines; i++) {
        if (g.pipelines[i].handle) g.be->pipeline_release(g.be->user, g.pipelines[i].handle);
        eng_pbr_job_free(&g.pipelines[i]);
    }
"""),
])
