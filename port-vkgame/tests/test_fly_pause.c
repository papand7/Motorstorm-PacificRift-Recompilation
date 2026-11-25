/* test_fly_pause.c: the F3 pause of the game's simulation step (fly_cam.h fly_toggle / fly_sim_step).
 *
 * The lifted frame step func_008CF1C0 takes the per-frame step in f1; the hook at its entry replaces f1
 * with mspr_fly_sim_step(f1), which is fly_sim_step(&mode, f1) when MSPR_DEBUG_FLY=1. Here the sim clock is
 * modelled as the sum of the steps the frame function receives, and the checks are:
 *   - fly mode off: the step is the frame's dt, unchanged (bit for bit);
 *   - fly mode on (F3): the step is 0 whatever dt is, so the sim clock stops and no frame is counted;
 *   - F3 off: the next step is the frame's own dt, with no catch-up for the paused time;
 *   - no drift: the sim clock after any number of pause cycles equals the sum of the running steps only;
 *   - the frame keeps running while paused: the frame counter advances on every call, paused or not.
 * Build and run: generated\analysis\pcmenu\tools\build_tests.cmd. */
#include "fly_cam.h"
#include <assert.h>
#include <stdio.h>

/* one frame of the game as the hook sees it: f1 in, the sim clock and the sim frame count out */
typedef struct { double clock; long sim_frames; long calls; } sim_state;

static double sim_frame(const fly_mode* m, sim_state* s, double f1)
{
    const double step = fly_sim_step(m, f1);   /* what mspr_fly_sim_step returns into f1 */
    s->calls++;
    if (step > 0.0) { s->clock += step; s->sim_frames++; }
    return step;
}

static void test_off_passes_dt(void)
{
    fly_mode m = { 0, 0 };
    sim_state s = { 0.0, 0, 0 };
    const double dts[] = { 1.0 / 30.0, 1.0 / 60.0, 0.0333, 0.25, 1e-9 };
    for (int i = 0; i < (int)(sizeof dts / sizeof dts[0]); i++) {
        const double r = sim_frame(&m, &s, dts[i]);
        assert(r == dts[i]);
    }
    assert(s.sim_frames == 5);
}

static void test_on_holds_the_step(void)
{
    fly_mode m = { 0, 0 };
    sim_state s = { 0.0, 0, 0 };
    sim_frame(&m, &s, 1.0 / 30.0);
    const double before = s.clock;
    fly_toggle(&m);                                 /* F3 on */
    assert(m.on == 1 && m.init == 1);
    for (int i = 0; i < 200; i++) {
        const double dt = (i % 7 == 0) ? 0.5 : 1.0 / 30.0;   /* a stalled frame must not move the clock either */
        assert(sim_frame(&m, &s, dt) == 0.0);
    }
    assert(s.clock == before);
    assert(s.calls == 201);                         /* the frame keeps running: every call is counted */
}

static void test_resume_exact_no_drift(void)
{
    /* ref adds only the running steps, in the same order; the pauses in between must add nothing */
    fly_mode m = { 0, 0 };
    sim_state run = { 0.0, 0, 0 };
    double ref = 0.0;
    long ref_frames = 0;
    const double dt = 1.0 / 30.0;
    for (int cycle = 0; cycle < 6; cycle++) {
        for (int i = 0; i < 40 + cycle * 3; i++) {       /* running */
            assert(sim_frame(&m, &run, dt) == dt);
            ref += dt;
            ref_frames++;
        }
        fly_toggle(&m);                                  /* F3 on: pause */
        assert(m.on);
        for (int i = 0; i < 25 + cycle * 11; i++)        /* paused, with dt values the sim must not see */
            assert(sim_frame(&m, &run, 0.2 + 0.01 * i) == 0.0);
        fly_toggle(&m);                                  /* F3 off: resume */
        assert(!m.on);
        assert(sim_frame(&m, &run, dt) == dt);           /* the first step after resume is the game's own dt */
        ref += dt;
        ref_frames++;
    }
    assert(run.clock == ref);                            /* exact: same steps, same order */
    assert(run.sim_frames == ref_frames);
    printf("pause: %ld running steps, clock %.9f, no drift\n", run.sim_frames, run.clock);
}

static void test_toggle_twice_is_identity(void)
{
    fly_mode m = { 0, 0 };
    fly_toggle(&m);
    fly_toggle(&m);
    assert(!m.on && !m.init);
    assert(fly_sim_step(&m, 0.5) == 0.5);
}

static void test_zero_dt_when_off(void)
{
    fly_mode m = { 0, 0 };
    assert(fly_sim_step(&m, 0.0) == 0.0);
    fly_toggle(&m);
    assert(fly_sim_step(&m, 0.0) == 0.0);
}

int main(void)
{
    test_off_passes_dt();
    test_on_holds_the_step();
    test_resume_exact_no_drift();
    test_toggle_twice_is_identity();
    test_zero_dt_when_off();
    printf("test_fly_pause: ok\n");
    return 0;
}
