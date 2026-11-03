"""T169 continuation: one-shot edit of ps3recomp-t169: RSX_VISUAL_PROFILE on the active init path, effective line, [visual-active] counters."""
p = 'rsx_d3d12_backend.c'
s = open(p, encoding='utf-8', newline='').read()


def sub(a, b):
    global s
    if '\r\n' in s:
        a, b = a.replace('\n', '\r\n'), b.replace('\n', '\r\n')
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


sub('''    { const unsigned vm = rsx_visual_profile_parse(getenv("RSX_VISUAL_PROFILE"));
      for (unsigned i = 0; vm && i < RSX_VISUAL_SWITCH_N; i++) {
          const char* v = rsx_visual_profile_value(vm, i, getenv(rsx_visual_switches[i].name));
          if (v) _putenv_s(rsx_visual_switches[i].name, v);
      }
      if (vm) fprintf(stderr, "[visual] RSX_VISUAL_PROFILE=0x%X%c", vm, 10); }
    (void)ud;
    printf("[D3D12] Backend init''', '''    (void)ud;
    printf("[D3D12] Backend init''')
sub('''static int  s_msaa = -1;          /* read once;''', '''/* RSX_VISUAL_ACTIVE=1: cumulative counts of what the corrections actually did,
 * one [visual-active] line every 64 presents. Read-only. */
static struct {
    int on;
    u64 fp_draws, depth_state, depth_differs, xfer_gamma, xfer_expand, xfer_srgb, srgb_rewrites, srgb_refused;
    u64 samp_new, samp_binds, win_draws, fb_draws, zeta_color_draws, mrt_draws, ms_draws;
} s_va;
static int  s_msaa = -1;          /* read once;''')
sub('''    s_visd.w.sampler_binds++;
''', '''    s_visd.w.sampler_binds++; s_va.samp_binds++;
''')
sub('''        s_visd.w.samplers_new++;
''', '''        s_visd.w.samplers_new++; s_va.samp_new++;
''')
sub('''                            " compiled without it%c", fp_addr, 10);
        xs = 0;
    }
''', '''                            " compiled without it%c", fp_addr, 10);
        xs = 0;
        s_va.srgb_refused++;
    } else if (xs) s_va.srgb_rewrites++;
''')
sub('''static void rsxi_on_draw(u32 d, const D3D12DrawRecord* dr, int cur_rt, const int* cur_m,''', '''/* RSX_VISUAL_ACTIVE: one replayed guest-FP draw. depth_differs: the guest's
 * state is one the legacy pipeline (writes on, LESS_EQUAL, no stencil) ignores. */
static void va_draw(const D3D12DrawRecord* dr)
{
    rsx_color_xfer x;
    s_va.fp_draws++;
    if (ds_state_on()) {
        s_va.depth_state++;
        if (((dr->g_depth >> 16) & 1u) && (!((dr->g_depth >> 8) & 1u) || (dr->g_depth & 0xFFu) != 0x03u || (dr->g_stencil >> 24)))
            s_va.depth_differs++;
    }
    if (dr_xfer_req(dr, &x)) {
        int g = 0, e = 0;
        for (int u = 0; u < RSX_DSP_NUM_TEXTURES; u++)
            if ((dr->fp_units >> u) & 1u) { g |= x.gamma[u]; e |= x.expand[u]; }
        s_va.xfer_gamma += g != 0; s_va.xfer_expand += e != 0; s_va.xfer_srgb += x.srgb_output != 0;
    }
    s_va.win_draws += dr->tex_win != 0;
    s_va.fb_draws += dr->tex_fb != 0;
    if (zeta_exact_on())
        for (int u = 0; u < RSX_DSP_NUM_TEXTURES; u++)
            if (((dr->fp_units >> u) & 1u) && dr->tex_src[u] == RSXI_SRC_ZETA_AS_COLOR) { s_va.zeta_color_draws++; break; }
    s_va.mrt_draws += dr_mrt_key(dr) != 0;
    s_va.ms_draws += dr_ms(dr) != 0;
}

static void va_report(void)
{
    fprintf(stderr, "[visual-active] present=%llu fp_draws=%llu depth_state=%llu depth_differs=%llu xfer_gamma=%llu xfer_expand=%llu xfer_srgb=%llu "
                    "srgb_rewrites=%llu srgb_refused=%llu samp_new=%llu samp_binds=%llu mip_multi=%llu mip_levels=%llu win_draws=%llu fb_draws=%llu "
                    "fb_copies=%llu zeta_color_draws=%llu mrt_draws=%llu ms_draws=%llu%c",
            (unsigned long long)s_d3d.frame_count, (unsigned long long)s_va.fp_draws, (unsigned long long)s_va.depth_state,
            (unsigned long long)s_va.depth_differs, (unsigned long long)s_va.xfer_gamma, (unsigned long long)s_va.xfer_expand,
            (unsigned long long)s_va.xfer_srgb, (unsigned long long)s_va.srgb_rewrites, (unsigned long long)s_va.srgb_refused,
            (unsigned long long)s_va.samp_new, (unsigned long long)s_va.samp_binds, (unsigned long long)s_texmip.multi,
            (unsigned long long)s_texmip.levels, (unsigned long long)s_va.win_draws, (unsigned long long)s_va.fb_draws,
            (unsigned long long)s_fbc.copies, (unsigned long long)s_va.zeta_color_draws, (unsigned long long)s_va.mrt_draws,
            (unsigned long long)s_va.ms_draws, 10);
}

static void rsxi_on_draw(u32 d, const D3D12DrawRecord* dr, int cur_rt, const int* cur_m,''')
sub('''                /* RSX_MSAA: a 2-sample pass has no 1-sample fallback pipeline. */
                if (s_pass_ms && (!dpso || !s_ms_pass_ok)) { s_msc.skipped++; continue; }
''', '''                /* RSX_MSAA: a 2-sample pass has no 1-sample fallback pipeline. */
                if (s_pass_ms && (!dpso || !s_ms_pass_ok)) { s_msc.skipped++; continue; }
                if (s_va.on && dpso) va_draw(dr);
''')
sub('''    if (early || !present) return;
    u64 wall = 0;
''', '''    if (early || !present) return;
    if (s_va.on && (s_d3d.frame_count & 63u) == 0) va_report();
    u64 wall = 0;
''')
sub('''int rsx_d3d12_backend_init(u32 width, u32 height, const char* title)
{
    fpf_init();''', '''/* RSX_VISUAL_PROFILE, before anything reads the switches it supplies. The game's
 * path is rsx_d3d12_backend_init -> init_d3d12; the backend's init callback never
 * runs. tools/test_t169_profile.py checks this through the output pixels. */
static void visual_profile_apply(void)
{
    const char* e = getenv("RSX_VISUAL_PROFILE");
    const unsigned vm = rsx_visual_profile_parse(e);
    for (unsigned i = 0; vm && i < RSX_VISUAL_SWITCH_N; i++) {
        const char* v = rsx_visual_profile_value(vm, i, getenv(rsx_visual_switches[i].name));
        if (v) _putenv_s(rsx_visual_switches[i].name, v);
    }
    if (rsx_visual_profile_invalid(e))
        fprintf(stderr, "[visual] RSX_VISUAL_PROFILE=%s rejected: no switch changed%c", e, 10);
    { const char* a = getenv("RSX_VISUAL_ACTIVE"); s_va.on = a && a[0] == '1' && !a[1]; }
}

/* What the renderer resolved, read through the accessors the draw path uses,
 * after init_d3d12 (a device that cannot support a mode turns it off). */
static void visual_effective_log(void)
{
    fprintf(stderr, "[visual] effective profile=0x%X xfer=0x%X samplers=0x%X mips=%d zeta_exact=%d rt_window=%d rt_feedback=%d msaa=%d depth_state=%d mrt_state=%d%c",
            rsx_visual_profile_parse(getenv("RSX_VISUAL_PROFILE")), xfer_mode(), s_gs_mode, texmip_mode(), zeta_exact_on(), rtwin_on(),
            rt_feedback_on(), msaa_on(), ds_state_on(), mrt_state_on(), 10);
}

int rsx_d3d12_backend_init(u32 width, u32 height, const char* title)
{
    visual_profile_apply();
    fpf_init();''')
sub('''        printf("[D3D12] ERROR: D3D12 initialization failed\\n");
        return -1;
    }

    /* Set up backend callbacks */''', '''        printf("[D3D12] ERROR: D3D12 initialization failed\\n");
        return -1;
    }
    visual_effective_log();

    /* Set up backend callbacks */''')
open(p, 'w', encoding='utf-8', newline='').write(s)
p = 'rsx_visual_profile.h'
s = open(p, encoding='utf-8', newline='').read()
sub('''/* The value the profile gives switch i''', '''/* A value was given and refused, so nothing is applied; "0" and unset are not refusals. */
static inline int rsx_visual_profile_invalid(const char* e)
{
    char* end = NULL;
    if (!e || !e[0] || rsx_visual_profile_parse(e)) return 0;
    return strtoul(e, &end, 0) != 0ul || *end != 0;
}

/* The value the profile gives switch i''')
open(p, 'w', encoding='utf-8', newline='').write(s)
