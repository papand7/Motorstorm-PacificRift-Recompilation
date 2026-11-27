/*
 * ps3recomp game project -- entry point template.
 *
 * This is the runner. It boots a lifted title through the toolkit's PPU
 * scaffold: allocate the flat guest VM, load the PPU ELF named on the command
 * line, register the lifted function table and the HLE NID handlers, start a
 * frame clock, and dispatch the entry OPD.
 *
 * The scaffold does the work; nothing below reimplements it. ppu_load_elf,
 * ppu_recomp_register, ppu_hle_init, ppu_sysprx_register, ppu_fs_register,
 * lv2_init_syscalls and ppu_run all come from the toolkit, compiled into this
 * project from PS3RECOMP_DIR (see CMakeLists.txt). What is left here is the
 * part a port owns: which backend to present through, how the frame clock is
 * paced, and whatever diagnostics the title turns out to need.
 *
 * runtime/ppu/tests/boot_main.cpp in the toolkit is the same boot in its
 * fully-instrumented form -- crash filter, hang watchdog, guest-PC sampling
 * profiler. Read it when a boot goes wrong; copy from it what the title
 * needs. It is deliberately not what a fresh project starts with.
 *
 * The one part that IS duplicated from it is the frame clock below, because a
 * port is expected to change its pacing and a shared one would be the wrong
 * shape for that. It was copied faithfully, comments and all. If a pacing bug
 * is fixed in one of the two, look at the other.
 *
 * This builds on Windows, macOS and Linux. CI builds and runs it against the
 * boot smoke title on the last two, and compile-checks it against clang-cl on
 * the first (tools/check_ppu_scaffold.py).
 */

/* The lifter's generated header, which declares ppu_context and the function
 * table. It comes first: everything below is written against that struct. */
#include "ppu_recomp.h"

/* The Win32 names -- Sleep, GetTickCount64, CreateThread, InterlockedIncrement,
 * VirtualAlloc, the scalar typedefs -- from one place. On Windows this is a
 * passthrough to <windows.h>; off Windows the toolkit's shim supplies the same
 * names over pthreads and mmap, so the call sites below are written once. */
#include "win32_compat.h"
#include "ps3emu/vblank_clock.h"   /* 59.94 Hz vblank deadlines */
#include "ps3emu/frame_beat.h"     /* vblank beat ordering */
#include "frame_clock_watchdog.h"   /* PS3_FC_WATCHDOG_MS: name the stage a stalled frame clock is in */
#include "stdio_async.h"           /* PS3_STDIO_ASYNC: log writes never wait for the disk */
#include "ps3emu/pad_trigger.h"     /* PS3_DEV_SKIP_INTRO: one CROSS press during the intro */
#include "mspr_patch.h"            /* MSPR_PATCH: default patch list (drs) */
extern "C" void pcmenu_boot(const char* argv0);   /* pc_menu.cpp: settings.ini, PC Settings page */
extern "C" void pcmenu_init(void);
#include "lan_play.h"              /* Host / Join (LAN): no socket until a page asks; atexit closes them */
extern "C" int pcmenu_owns_env(const char* name);   /* settings.ini names the setting behind this variable */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>   /* MSPR_CAM_COCKPIT: overlay probe */

#ifdef _WIN32
/* timeBeginPeriod: <windows.h> arrives with WIN32_LEAN_AND_MEAN set, which
 * excludes the multimedia timer API, so it is asked for by name -- and after
 * windows.h, since timeapi.h uses UINT. No shim exists off Windows because
 * there is nothing to shim: the 15.6 ms default timer granularity this works
 * around is a Windows problem. */
#include <timeapi.h>
#endif

/* ---------------------------------------------------------------------------
 * What the scaffold gives this file
 * -----------------------------------------------------------------------*/
extern "C" {
uint32_t ppu_load_elf(const char* path);      /* ELF -> guest RAM, returns entry OPD */
void     ppu_recomp_register(void);           /* generated: lifted table -> address map */
void     ppu_hle_init(void);                  /* firmware import NID -> HLE handler */
void     ppu_sysprx_register(void);           /* boot-critical CRT (sys_initialize_tls, ...) */
void     ppu_fs_register(void);               /* cellFs over the real game directory */
void     lv2_init_syscalls(void);             /* the lv2 syscall table */
int      ppu_run(uint32_t entry_opd, uint32_t stack_top);

/* This project's own: load whatever real system PRX modules the title needs
 * into guest RAM and register their exports. stubs.cpp has the empty version
 * a game with no lifted PRX wants. */
void     ps3_load_prx_modules(void);

extern const char* ppu_vfs_root;              /* host dir the PS3 mount points map into */

/* The status the guest handed to sys_process_exit. A title that exits that way
 * never returns through ppu_run, so this is only read on the path where the
 * entry function unwound instead. */
extern int     g_sys_process_exit_called;
extern int32_t g_sys_process_exit_code;

/* Host-provided symbols the runtime and the HLE libraries link against. */
uint8_t* vm_base = nullptr;
extern uint32_t ppu_vm_size;                  /* ppu_loader.cpp: the OOB guard */

/* Guest-callback dispatch. g_ps3_guest_caller is the hook the HLE runtime
 * calls back into recompiled code through -- cellSysutil events and the GCM
 * vblank/flip handlers. ppu_guest_call does the OPD -> dispatch. */
typedef void (*ps3_guest_caller_fn)(uint32_t, uint64_t, uint64_t, uint64_t, uint64_t,
                                    uint64_t, uint64_t, uint64_t, uint64_t);
extern ps3_guest_caller_fn g_ps3_guest_caller;
uint64_t ppu_guest_call(uint32_t, uint64_t, uint64_t, uint64_t, uint64_t,
                        uint64_t, uint64_t, uint64_t, uint64_t);

/* The GCM half of the frame clock. */
void     cellGcmTickVBlank(void);
void     cellGcmTickFlip(void);
int      cellGcm_take_flip_pending(void);
void     cellGcm_rsx_process_fifo(void);      /* drain get -> put */
void     cellGcm_fifo_kick_wait(unsigned ms); /* idle wait, woken by a kick */
unsigned cellGcm_flip_request_count(void);
int      rsx_draw_engine_ab_phase(void);      /* the engine's in-run A/B side */
extern volatile int g_vmx_fast;               /* PS3_VMX_FAST: ppu_vmx.h's x86 fast paths */
void     sys_timer_usleep_ab_phase(int on);   /* PS3_USLEEP_SPIN=ab: which side */
extern int (*cellGcm_fifo_fast_ab)(void);     /* GCM_FIFO_FAST=ab: which side */
}

/* ---------------------------------------------------------------------------
 * RSX present backend
 * -----------------------------------------------------------------------*/
/* D3D12 on Windows, Metal on Apple, and the null backend's headless software
 * path anywhere else -- the same selection runtime/host/host_posix.c and the
 * toolkit's boot harness make. All three expose the same three entry points,
 * so the frame clock below is backend-agnostic. */
#if defined(_WIN32)
extern "C" int  rsx_d3d12_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_d3d12_backend_present(void);
extern "C" int  rsx_d3d12_backend_pump_messages(void);
#  if defined(PS3RECOMP_RSX_VULKAN)
/* Built with the Vulkan backend: D3D12 stays the default and RSX_BACKEND=vulkan
 * picks Vulkan (PS3RECOMP_VK_WINDOW=1 for its window), chosen once at start-up. */
extern "C" int  rsx_vulkan_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_vulkan_backend_present(void);
extern "C" int  rsx_vulkan_backend_pump_messages(void);
static int  (*g_rsx_init)(uint32_t, uint32_t, const char*) = rsx_d3d12_backend_init;
static void (*g_rsx_present)(void)                         = rsx_d3d12_backend_present;
static int  (*g_rsx_pump)(void)                            = rsx_d3d12_backend_pump_messages;
static const char* g_rsx_name                              = "D3D12";
static const bool  g_rsx_selected = [] {
    const char* e = getenv("RSX_BACKEND");
    if (e && (!strcmp(e, "vulkan") || !strcmp(e, "vk"))) {
        g_rsx_init = rsx_vulkan_backend_init; g_rsx_present = rsx_vulkan_backend_present;
        g_rsx_pump = rsx_vulkan_backend_pump_messages; g_rsx_name = "Vulkan";
    }
    return true;
}();
#    define rsx_backend_init    g_rsx_init
#    define rsx_backend_present g_rsx_present
#    define rsx_backend_pump    g_rsx_pump
#    define RSX_BACKEND_NAME    g_rsx_name
#  else
#    define rsx_backend_init    rsx_d3d12_backend_init
#    define rsx_backend_present rsx_d3d12_backend_present
#    define rsx_backend_pump    rsx_d3d12_backend_pump_messages
#    define RSX_BACKEND_NAME    "D3D12"
#  endif
#elif defined(__APPLE__)
extern "C" int  rsx_metal_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_metal_backend_present(void);
extern "C" int  rsx_metal_backend_pump_messages(void);
#  define rsx_backend_init    rsx_metal_backend_init
#  define rsx_backend_present rsx_metal_backend_present
#  define rsx_backend_pump    rsx_metal_backend_pump_messages
#  define RSX_BACKEND_NAME    "Metal"
#else
extern "C" int  rsx_null_backend_init(uint32_t w, uint32_t h, const char* title);
extern "C" void rsx_null_backend_present(void);
extern "C" int  rsx_null_backend_pump_messages(void);
#  define rsx_backend_init    rsx_null_backend_init
#  define rsx_backend_present rsx_null_backend_present
#  define rsx_backend_pump    rsx_null_backend_pump_messages
#  define RSX_BACKEND_NAME    "null (headless software)"
#endif

/* ---------------------------------------------------------------------------
 * Configuration
 * -----------------------------------------------------------------------*/
/* The flat VM must span every region the PS3 memory map uses, not just the
 * game image: sys_ppu_thread_create puts thread stacks at 0xD0000000, so a
 * smaller arena makes every spawned thread's stack access out of bounds. */
#define VM_SIZE       0x100010000ull   /* the full 32-bit guest space + a 64K guard */
#define STACK_TOP     0x0FF00000u      /* main-thread stack, below the 0x10000000 segment */
#define WINDOW_WIDTH  1280
#define WINDOW_HEIGHT 720

/* ---------------------------------------------------------------------------
 * Frame clock
 * -----------------------------------------------------------------------*/
/* On real hardware the RSX raises a vblank interrupt about 60 times a second
 * and that is what drives the game's frame loop. With no RSX it is synthesized
 * here: a host thread calls cellGcmTickVBlank/TickFlip, which invoke the
 * handlers the guest registered, and drains the GCM FIFO. Without this the
 * title initialises, registers its handlers and then waits forever.
 *
 * The ticks are driven off real elapsed time rather than off how long present()
 * took. A hidden or occluded window makes present block hard, and pacing the
 * ticks behind it paces the whole game behind it. */
static volatile LONG g_frames_presented = 0;

/* Frames handed to the backend at a guest FLIP boundary -- one per frame the
 * guest actually finished. The presents made before the guest's first flip, so
 * a fresh window is not left blank through a long boot, carry no guest frame
 * and are deliberately not counted. */
extern "C" unsigned ppu_boot_frames_presented(void)
{
    return (unsigned)g_frames_presented;
}

static void fly_frame(void);   /* MSPR_DEBUG_FLY: F3, the mouse and the keys, once per presented frame (below) */
static void frame_log(char kind);   /* MSPR_FRAME_LOG: one line a present (below) */
static void bench_frame(void);      /* MSPR_BENCH: the benchmark's guest frames, window and result (below) */
static void present_clock_start(void);   /* the first present: the frame log's and the benchmark's ms origin */
static void present_guest_frame(void)
{
    rsx_backend_present();
    present_clock_start();
    frame_log('g');
    bench_frame();
    /* This thread increments and guest threads read, so interlocked rather
     * than a volatile ++, which on arm64 is neither atomic nor a fence. */
    InterlockedIncrement(&g_frames_presented);
    fly_frame();
}

/* One vblank beat (ps3emu/frame_beat.h): present the flip the drain completed,
 * THEN make the vblank and the flip completion visible, then drain. Ticking
 * first told the guest the frame was done while the backend was still copying
 * its textures out of guest memory, and a Bink player decoded the next frame
 * into them (PS3_VIDEO_STATS `torn`). */
struct frame_beat_state { int rsx_ok; unsigned* last_flip; };
static int beat_take_flip(void* u)
{
    return ((frame_beat_state*)u)->rsx_ok && cellGcm_take_flip_pending();
}
static void beat_present(void* u)
{
    present_guest_frame();
    *((frame_beat_state*)u)->last_flip = cellGcm_flip_request_count();
}
static void beat_vblank(void*) { cellGcmTickVBlank(); }
static void beat_flip_done(void*) { cellGcmTickFlip(); }
/* Drain the FIFO every tick. This is what writes the RSX sync-fence labels the
 * game's per-frame logic blocks on, so it has to keep advancing at 60 Hz even
 * while present() throttles. */
static void beat_drain(void* u)
{
    if (((frame_beat_state*)u)->rsx_ok) cellGcm_rsx_process_fifo();
}

#ifdef _WIN32
#include <powerbase.h>   /* CallNtPowerInformation: per-processor maximum clock (PS3_MAIN_CORE) */
#pragma comment(lib, "powrprof.lib")
#include "main_core_pick.h"
static HANDLE s_main_thread;   /* PS3_MAIN_CYCLES: the thread ppu_run runs the guest main thread on */

/* MSPR_FRAME_LOG=<file> (benchmark, off by default): one text line per backend present, written by the thread that
 * presents, right after the present call returns: "<g|b> <ms> <main Mcycles> <flips>", g = a present at a guest
 * flip, b = a boot present before the first flip. <flips> is the guest's flip count: count guest frames by it, not by
 * the g lines (a flip can be presented twice: Klbr2 had 4687 g lines for 3226 flips in 90 s). <ms> counts from the first present (any kind), the same origin as the Vulkan
 * backend's [rsx-hb] ms= (its first present), so a reader can pick a window by heartbeat time. <main Mcycles> is the
 * guest main thread's cumulative CPU cycles (QueryThreadCycleTime, 0 when the thread is not known yet). Flushed every
 * 240 lines (the runner kills the game). Unset: one cached getenv test a present. generated/analysis/perf60/
 * bench_race.py reads it. */
static LARGE_INTEGER s_present_t0;   /* QueryPerformanceCounter at the first present (any kind) */
static void present_clock_start(void)
{
    if (!s_present_t0.QuadPart) QueryPerformanceCounter(&s_present_t0);
}

static void frame_log(char kind)
{
    static int on = -1;
    static FILE* f;
    static LARGE_INTEGER freq, t0;
    static unsigned n;
    if (on == 0) return;
    if (on < 0) {
        const char* e = getenv("MSPR_FRAME_LOG");
        on = 0;
        if (!e || !e[0]) return;
        f = fopen(e, "w");
        if (!f) { fprintf(stderr, "[frame-log] cannot open %s\n", e); return; }
        setvbuf(f, NULL, _IOFBF, 1 << 16);
        QueryPerformanceFrequency(&freq);
        t0 = s_present_t0;   /* present_clock_start: the first present */
        if (!t0.QuadPart) QueryPerformanceCounter(&t0);
        fprintf(f, "# MSPR_FRAME_LOG kind ms main_mcycles flips\n");
        fprintf(stderr, "[frame-log] %s\n", e);
        on = 1;
    }
    LARGE_INTEGER t;
    QueryPerformanceCounter(&t);
    ULONG64 c = 0;
    if (s_main_thread) QueryThreadCycleTime(s_main_thread, &c);
    fprintf(f, "%c %.3f %.3f %u\n", kind, (double)(t.QuadPart - t0.QuadPart) * 1000.0 / (double)freq.QuadPart, (double)c / 1e6,
            cellGcm_flip_request_count());
    if (++n % 240u == 0) fflush(f);
}

/* MSPR_BENCH=fly|race (the launcher's Benchmark page, off by default; bench_run.h): the game runs the benchmark,
 * measures it, writes the result to MSPR_BENCH_OUT (JSON) and quits by itself.
 *   fly   the disc's benchmark config (booted through PS3_DEV_GUEST_STR): from the first frame with the world drawn
 *         (>= 200 guest draws) to the first "HotSpot" view (mspr_bench_hotspot, a lift hook) = the camera flight.
 *   race  a race with AI racers (configs/mspr_bench_race.cfg from the launcher) and the player's car driven by the
 *         game's AI (mspr_bench_ai_ctl): CROSS skips the pre-race flyover (pad_trigger.h, as a pad would), the
 *         window is race start + 21.5 s .. + 111.5 s.
 * Guest frames count, not presents (bench_run.h). The result names the GPU the game rendered on (the Vulkan device),
 * the CPU (cpuid brand string), the installed RAM, and the settings the game started with (pc_menu.cpp). Nothing is
 * changed in the game's settings; unset, one cached test a present. tests/test_bench_run.c. */
#include "bench_run.h"
#include <intrin.h>   /* __cpuid: the CPU's brand string */
extern "C" unsigned rsx_draw_engine_guest_draws(void);
#if defined(PS3RECOMP_RSX_VULKAN)
extern "C" const char* rsx_vulkan_device_name(void);
extern "C" void rsx_vulkan_live_pipelines(unsigned long long* n, double* ms);
#endif
extern "C" int pcmenu_bench_settings(char* out, size_t cap);   /* pc_menu.cpp */

static volatile int s_bench_mode = -1;
static volatile LONG64 s_bench_hot_qpc, s_bench_fly_qpc, s_bench_race_qpc;   /* the game's events (guest threads) */
static double* s_bench_t;            /* per guest present: ms since the first present ... */
static uint32_t* s_bench_f;          /* ... and the guest flip count */
static uint32_t s_bench_n, s_bench_cap;
static double s_bench_start = -1.0;  /* fly: the first frame with the world drawn */
static unsigned s_bench_presses;     /* race: CROSS presses made */
static int s_bench_done;
static int s_bench_live_at_w0;            /* the pipeline counts sampled at the window's start */
static unsigned long long s_bench_live_n0;
static double s_bench_live_ms0;
/* pipelines built on demand so far (the Vulkan backend; 0 with another backend) */
static void bench_live(unsigned long long* n, double* ms)
{
    *n = 0; *ms = 0.0;
#if defined(PS3RECOMP_RSX_VULKAN)
    if (!strcmp(RSX_BACKEND_NAME, "Vulkan")) rsx_vulkan_live_pipelines(n, ms);
#endif
}
static void bench_live_mark(void)
{
    if (s_bench_live_at_w0) return;
    bench_live(&s_bench_live_n0, &s_bench_live_ms0);
    s_bench_live_at_w0 = 1;
}

static int bench_mode(void)
{
    int m = s_bench_mode;
    if (m < 0) {
        m = bench_mode_of(getenv("MSPR_BENCH"));
        s_bench_mode = m;
        if (m) fprintf(stderr, "[bench] MSPR_BENCH=%s: the game measures the %s and quits; result to %s\n",
                       bench_mode_name(m), m == BENCH_FLY ? "camera flight" : "race",
                       getenv("MSPR_BENCH_OUT") ? getenv("MSPR_BENCH_OUT") : "(stderr only: MSPR_BENCH_OUT unset)");
    }
    return m;
}

static double bench_ms(LONGLONG qpc)
{
    static LARGE_INTEGER freq;
    if (!freq.QuadPart) QueryPerformanceFrequency(&freq);
    return (double)(qpc - s_present_t0.QuadPart) * 1000.0 / (double)freq.QuadPart;
}

static void bench_note(volatile LONG64* slot, const char* what)
{
    if (*slot) return;
    LARGE_INTEGER q;
    QueryPerformanceCounter(&q);
    if (InterlockedCompareExchange64(slot, q.QuadPart, 0) == 0)
        fprintf(stderr, "[bench] %s at %.1f ms\n", what, bench_ms(q.QuadPart));
}

/* The lift hook (launcher/pipeline/bench_patch_lifted.py): the game formats a "HotSpot" view's label, so the camera
 * flight is over. Only noted with MSPR_BENCH=fly. */
extern "C" void mspr_bench_hotspot(void)
{
    if (s_bench_mode == BENCH_FLY || (s_bench_mode < 0 && bench_mode() == BENCH_FLY))
        bench_note(&s_bench_hot_qpc, "first HotSpot view (the camera flight is over)");
}

/* race: one CROSS press through the pad layer, as a held button (pad_trigger.h: OR'd into port 0's reads for
 * PAD_TRIGGER_HOLD_MS and at least PAD_TRIGGER_MIN_READS reads), the way the flyover's "Press X to Skip" expects */
static void bench_press_cross(void)
{
    pad_trigger_state* p = &g_pad_trigger;
    if (__atomic_load_n(&p->state, __ATOMIC_ACQUIRE) == PT_PRESSING) return;
    if (__atomic_load_n(&p->cfg, __ATOMIC_ACQUIRE) != 2)
        pad_trigger_configure("\x01mspr-bench", 0x4000 /* CROSS */, 0, PAD_TRIGGER_HOLD_MS);   /* no open matches */
    p->mask = 0x4000; p->delay_ms = 0; p->hold_ms = PAD_TRIGGER_HOLD_MS; p->reads = 0;
    p->t_arm_ms = pad_trigger_now_ms();
    __atomic_store_n(&p->state, PT_ARMED, __ATOMIC_RELEASE);
}

static void bench_cpu_brand(char* out, size_t cap)
{
    int r[4];
    char b[49] = { 0 };
    __cpuid(r, (int)0x80000000);
    if ((unsigned)r[0] >= 0x80000004u)
        for (int i = 0; i < 3; i++) { __cpuid(r, (int)(0x80000002u + i)); memcpy(b + 16 * i, r, 16); }
    const char* p = b;
    while (*p == ' ') p++;
    snprintf(out, cap, "%s", p);
    for (size_t n = strlen(out); n && out[n - 1] == ' '; n--) out[n - 1] = 0;
}

/* Writes the result (or the error) and ends the process. It runs on its own thread (bench_finish below): the frame
 * clock keeps presenting meanwhile, so the guest never waits on a flip that does not come. When the frame clock's
 * own thread did this work, the guest reported "GcKernel::Present() Timeout" at the end of every run (Klbr2, Klbf4,
 * the launcher runs). */
static struct { int m; bench_result r; int have_r; double w0, w1; const char* anchor; const char* err; } s_bench_fin;
static DWORD WINAPI bench_finish_main(LPVOID)
{
    const int m = s_bench_fin.m;
    const bench_result* r = s_bench_fin.have_r ? &s_bench_fin.r : NULL;
    const double w0 = s_bench_fin.w0, w1 = s_bench_fin.w1;
    const char* anchor = s_bench_fin.anchor;
    const char* err = s_bench_fin.err;
    static char cpu[64], settings[8192];
    bench_cpu_brand(cpu, sizeof cpu);
    MEMORYSTATUSEX ms;
    ms.dwLength = sizeof ms;
    const unsigned long long ram = GlobalMemoryStatusEx(&ms) ? (unsigned long long)ms.ullTotalPhys : 0ull;
    pcmenu_bench_settings(settings, sizeof settings);
    const char* gpu = "";
#if defined(PS3RECOMP_RSX_VULKAN)
    if (!strcmp(RSX_BACKEND_NAME, "Vulkan")) gpu = rsx_vulkan_device_name();
#endif
    unsigned long long ln = 0;
    double lms = 0.0;
    bench_live(&ln, &lms);
    if (!s_bench_live_at_w0) { s_bench_live_n0 = ln; s_bench_live_ms0 = lms; }
    const bench_info in = { gpu, cpu, ram, settings, w0, w1, anchor, (unsigned)(ln - s_bench_live_n0), lms - s_bench_live_ms0 };
    const char* out = getenv("MSPR_BENCH_OUT");
    if (out && *out) {
        FILE* f = fopen(out, "w");
        if (f) { bench_write_json(f, m, r, &in, err); fclose(f); }
        else fprintf(stderr, "[bench] cannot write %s\n", out);
    }
    if (err) fprintf(stderr, "[bench] %s: no result: %s\n", bench_mode_name(m), err);
    else fprintf(stderr, "[bench] %s: %u guest frames in %.2f s (window %.1f .. %.1f ms, %s): avg %.2f fps, min %.0f, "
                 "max %.0f, 1%% low %.2f, 0.1%% low %.2f; P50 %.2f ms, P99 %.2f ms; GPU %s, CPU %s, RAM %.1f GB\n",
                 bench_mode_name(m), r->frames, r->span_ms / 1000.0, w0, w1, anchor, r->avg, r->min, r->max, r->low1,
                 r->low01, r->p50, r->p99, gpu, cpu, (double)ram / (1024.0 * 1024.0 * 1024.0));
    fflush(NULL);
    stdio_async_drain(1000);
    /* the result and the log are out: end at once, without ExitProcess's DLL teardown (the Vulkan driver's, seconds
     * while the guest still runs) */
    TerminateProcess(GetCurrentProcess(), err ? 3u : 0u);
    return 0;
}
static void bench_finish(int m, const bench_result* r, double w0, double w1, const char* anchor, const char* err)
{
    if (s_bench_done) return;
    s_bench_done = 1;
    s_bench_fin.m = m; s_bench_fin.have_r = r != NULL;
    if (r) s_bench_fin.r = *r;
    s_bench_fin.w0 = w0; s_bench_fin.w1 = w1; s_bench_fin.anchor = anchor; s_bench_fin.err = err;
    HANDLE h = CreateThread(NULL, 0, bench_finish_main, NULL, 0, NULL);
    if (h) CloseHandle(h);
    else bench_finish_main(NULL);
}

static void bench_end_window(int m, double w0, double w1, const char* anchor)
{
    uint32_t flips = s_bench_f[s_bench_n - 1] - s_bench_f[0] + 16u;
    double* scratch = (double*)malloc(sizeof(double) * flips);
    const bench_result r = scratch ? bench_compute(s_bench_t, s_bench_f, s_bench_n, w0, w1, scratch, flips) : bench_result{};
    free(scratch);
    bench_finish(m, &r, w0, w1, anchor, r.ok ? NULL : "the measured window has no frames");
}

/* each guest present (present_guest_frame, the frame clock thread) */
static void bench_frame(void)
{
    const int m = s_bench_mode < 0 ? bench_mode() : s_bench_mode;
    if (!m || s_bench_done) return;
    LARGE_INTEGER q;
    QueryPerformanceCounter(&q);
    const double t = bench_ms(q.QuadPart);
    if (s_bench_n == s_bench_cap) {
        const uint32_t cap = s_bench_cap ? 2 * s_bench_cap : 16384u;
        double* nt = (double*)realloc(s_bench_t, sizeof(double) * cap);
        if (nt) s_bench_t = nt;
        uint32_t* nf = (uint32_t*)realloc(s_bench_f, sizeof(uint32_t) * cap);
        if (nf) s_bench_f = nf;
        if (!nt || !nf) { bench_finish(m, NULL, 0, 0, "", "out of memory"); return; }
        s_bench_cap = cap;
    }
    s_bench_t[s_bench_n] = t;
    s_bench_f[s_bench_n] = cellGcm_flip_request_count();
    s_bench_n++;
    if (m == BENCH_FLY) {
        if (s_bench_start < 0.0 && rsx_draw_engine_guest_draws() >= BENCH_SCENE_DRAWS) {
            s_bench_start = t;
            bench_live_mark();
            fprintf(stderr, "[bench] the world is drawn (%u guest draws) at %.1f ms: the camera flight is measured from here\n",
                    rsx_draw_engine_guest_draws(), t);
        }
        const LONG64 h = s_bench_hot_qpc;
        static double linger = -1.0;   /* MSPR_BENCH_LINGER_MS (developer check only): quit this much later, same window */
        if (linger < 0.0) { const char* l = getenv("MSPR_BENCH_LINGER_MS"); linger = l ? atof(l) : 0.0; }
        if (h && t < bench_ms(h) + linger) return;
        if (h) {
            const double e = bench_ms(h);
            if (s_bench_start < 0.0) bench_finish(m, NULL, 0, e, "", "the HotSpot views came before the camera flight");
            else if (e - s_bench_start < BENCH_FLY_MIN_MS) bench_finish(m, NULL, s_bench_start, e, "", "the camera flight ended too early");
            else bench_end_window(m, s_bench_start, e, "first frame with the world drawn .. first HotSpot view");
        } else if (s_bench_start < 0.0 && t > BENCH_START_TIMEOUT_MS) {
            bench_finish(m, NULL, 0, t, "", "the benchmark did not start");
        } else if (s_bench_start >= 0.0 && t - s_bench_start > BENCH_FLY_TIMEOUT_MS) {
            bench_finish(m, NULL, s_bench_start, t, "", "the camera flight did not end: this build lacks the benchmark "
                         "hooks (Install: Build again)");
        }
        return;
    }
    /* race */
    const double fly = s_bench_fly_qpc ? bench_ms(s_bench_fly_qpc) : -1.0;
    const double race = s_bench_race_qpc ? bench_ms(s_bench_race_qpc) : -1.0;
    if (bench_skip_due(fly, race, s_bench_presses, t)) {
        bench_press_cross();
        s_bench_presses++;
        fprintf(stderr, "[bench] CROSS (skip the flyover) at %.1f ms, %.1f s into the flyover\n", t, (t - fly) / 1000.0);
    }
    if (race >= 0.0) {
        if (t >= race + BENCH_RACE_FROM_MS) bench_live_mark();
        if (t >= race + BENCH_RACE_TO_MS)
            bench_end_window(m, race + BENCH_RACE_FROM_MS, race + BENCH_RACE_TO_MS, "race start + 21.5 s .. + 111.5 s");
    } else if (t > BENCH_START_TIMEOUT_MS) {
        bench_finish(m, NULL, 0, t, "", fly < 0.0 ? "no race: this build lacks the benchmark hooks (Install: Build again)"
                                                  : "the race did not start");
    }
}

#ifdef _WIN32
/* PS3_MAIN_CORE (opt-in): one physical core for the guest main thread alone. "1" (or "auto") takes the fastest
 * physical core (main_core_pick.h: efficiency class, then the preferred-core rank, then the maximum clock, then the
 * last index; on a CPU with Zen 5 and Zen 5c cores that is a Zen 5 core), "c<N>" core N. Every other thread of the process (the SPU and job
 * threads that spin-wait, the RSX drain, the audio worker) gets the process default CPU set, which leaves that core
 * out, so nothing shares it with the main thread, not even through SMT; the main thread is also raised to
 * above-normal priority. Windows CPU sets (Windows 10 1709+); without them nothing changes. */
static void main_core_setup(void)
{
    const char* e = getenv("PS3_MAIN_CORE");
    if (!e || !*e || !strcmp(e, "0")) return;
    ULONG len = 0;
    GetSystemCpuSetInformation(NULL, 0, &len, GetCurrentProcess(), 0);
    if (!len) { fprintf(stderr, "[main-core] no CPU set information\n"); return; }
    unsigned char* buf = (unsigned char*)malloc(len);
    if (!buf || !GetSystemCpuSetInformation((PSYSTEM_CPU_SET_INFORMATION)buf, len, &len, GetCurrentProcess(), 0)) {
        free(buf); fprintf(stderr, "[main-core] GetSystemCpuSetInformation failed\n"); return;
    }
    int target = -1;
    if (e[0] == 'c') target = atoi(e + 1);
    else {   /* default: the fastest core (main_core_pick.h) */
        struct { ULONG Number, MaxMhz, CurrentMhz, MhzLimit, MaxIdleState, CurrentIdleState; } ppi[256];
        const DWORD nlp = GetActiveProcessorCount(0);   /* group 0: the processors CallNtPowerInformation reports */
        const int have_mhz = nlp && nlp <= 256 &&
            CallNtPowerInformation(ProcessorInformation, NULL, 0, ppi, (ULONG)(sizeof ppi[0] * nlp)) == 0;
        main_core_lp lp[256];
        int n = 0;
        for (ULONG off = 0; off < len && n < 256;) {
            const SYSTEM_CPU_SET_INFORMATION* c = (const SYSTEM_CPU_SET_INFORMATION*)(buf + off);
            if (c->Type == CpuSetInformation) {
                const unsigned li = c->CpuSet.LogicalProcessorIndex;
                lp[n].core = c->CpuSet.CoreIndex;
                lp[n].eff = c->CpuSet.EfficiencyClass;
                lp[n].sched = c->CpuSet.SchedulingClass;
                lp[n].mhz = have_mhz && c->CpuSet.Group == 0 && li < nlp ? (unsigned)ppi[li].MaxMhz : 0u;
                n++;
            }
            off += c->Size;
        }
        target = main_core_pick(lp, n);
        for (int i = 0; i < n; i++)
            if (lp[i].core == target) {
                fprintf(stderr, "[main-core] fastest core %d: efficiency class %d, preferred-core rank %d, max %u MHz\n",
                        target, lp[i].eff, lp[i].sched, lp[i].mhz);
                break;
            }
    }
    ULONG mine[8], rest[256];
    ULONG nmine = 0, nrest = 0;
    for (ULONG off = 0; off < len;) {
        const SYSTEM_CPU_SET_INFORMATION* c = (const SYSTEM_CPU_SET_INFORMATION*)(buf + off);
        if (c->Type == CpuSetInformation) {
            if (c->CpuSet.CoreIndex == target) { if (nmine < 8) mine[nmine++] = c->CpuSet.Id; }
            else if (nrest < 256) rest[nrest++] = c->CpuSet.Id;
        }
        off += c->Size;
    }
    free(buf);
    if (!nmine || !nrest) { fprintf(stderr, "[main-core] core %d not found\n", target); return; }
    const BOOL a = SetProcessDefaultCpuSets(GetCurrentProcess(), rest, nrest);
    const BOOL b = SetThreadSelectedCpuSets(GetCurrentThread(), mine, nmine);
    const BOOL c = SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_ABOVE_NORMAL);
    fprintf(stderr, "[main-core] main thread on core %d (%lu logical), %lu CPU sets for the rest, above-normal: %s/%s/%s\n",
            target, (unsigned long)nmine, (unsigned long)nrest, a ? "ok" : "FAIL", b ? "ok" : "FAIL", c ? "ok" : "FAIL");
}
#endif

#endif

#ifdef PORT_PGO_GEN
/* An instrumented (-fprofile-generate) build only: PS3_PGO_WINDOW=<from ms>:<to ms> after start
 * resets the counters at <from> and writes the profile (LLVM_PROFILE_FILE) at <to>, so the
 * profile is the race and not the boot, and exists although the runner kills the process. */
extern "C" int __llvm_profile_write_file(void);
extern "C" void __llvm_profile_reset_counters(void);
#endif

static DWORD WINAPI frame_clock(LPVOID)
{
    const char* title = getenv("PS3_TITLE");
    if (!title || !*title) title = "Motorstorm: Pacific Rift";

    int rsx_ok = (rsx_backend_init(WINDOW_WIDTH, WINDOW_HEIGHT, title) == 0);
    fprintf(stderr, "[rsx] %s backend init %s\n", RSX_BACKEND_NAME,
            rsx_ok ? "OK -- window open" : "FAILED");

    unsigned  last_flip = 0;
    fcw_start_for_current_thread(stderr);
    /* Vblank deadlines at the 59.94 Hz cellVideoOut reports. Whole 16 ms
     * steps gave 62.5 Hz. */
    ps3_vblank_clock vbc;
    ps3_vblank_clock_init(&vbc, ps3_vblank_now_us());

    frame_beat_state beat_state = { rsx_ok, &last_flip };
    const ps3_frame_beat_ops beat = { beat_take_flip, beat_present, beat_vblank,
                                      beat_flip_done, beat_drain, &beat_state };

    /* PS3_FRAME_CLOCK_KICK=1 (T151, off by default, read once): wait on the
     * FIFO kick event instead of a flat Sleep(4). A guest spinning on the RSX
     * reference register signals it when the drain has not yet published the
     * fence (cellGcm_ref_on_poll, "dry"), so the drain runs then rather than
     * up to one 4 ms tick later. No kick: the same 4 ms. The drain, the beat
     * and the presents run on this thread and in this order either way. */
    /* "ab": on and off by turns, following the draw engine's in-run A/B, whose
     * "[eng-ab]" line then times each side. */
    const char* kick_env = getenv("PS3_FRAME_CLOCK_KICK");
    const int kick = !kick_env ? 0 : !strcmp(kick_env, "1") ? 1 : !strcmp(kick_env, "ab") ? 2 : 0;
    if (kick) fprintf(stderr, "[frame-clock] PS3_FRAME_CLOCK_KICK=%s: idle wait woken by FIFO kicks\n", kick_env);
    /* PS3_USLEEP_SPIN=ab: guest usleeps exact (mode 2) or on the timer, by
     * the same turns. */
    const char* us_env = getenv("PS3_USLEEP_SPIN");
    const int usleep_ab = us_env && !strcmp(us_env, "ab");
    /* MSPR_STORE_INLINE_AB=1 (with PS3_VM_STORE_INLINE=1, in a build with
     * MSPR_PPU_INLINE_STORES): the lifted code's inline stores on and off by
     * the same turns, once the runtime has turned them on. Off sends every
     * store through vm_write*, with the same result. */
    const char* sab_env = getenv("MSPR_STORE_INLINE_AB");
    int store_ab = sab_env && !strcmp(sab_env, "1");
    /* PS3_VMX_FAST (on by default, =0 disables): the float VMX helpers' x86
     * fast paths (ppu_vmx.h), the same bits as the per-lane code; "ab": on
     * and off by the same turns. */
    const char* vmx_env = getenv("PS3_VMX_FAST");
    const int vmx_ab = vmx_env && !strcmp(vmx_env, "ab");
    g_vmx_fast = !(vmx_env && !strcmp(vmx_env, "0"));
    fprintf(stderr, "[vmx-fast] PS3_VMX_FAST=%s: float VMX helpers %s\n", vmx_env ? vmx_env : "(default 1)",
            vmx_ab ? "on x86 fast paths by turns" : g_vmx_fast ? "on x86 fast paths" : "per lane");
#ifdef _WIN32
    /* PS3_MAIN_CYCLES=1 (off by default): every 5 s, the CPU cycles the guest
     * main thread ran per guest flip. Cycles do not count waiting or time the
     * thread was descheduled, so this compares builds even when other work
     * shares the PC (it still moves with cache and SMT contention). */
    const char* mcy_env = getenv("PS3_MAIN_CYCLES");
    const int main_cycles = mcy_env && mcy_env[0] == '1' && !mcy_env[1];
    ULONG64 mcy_last = 0;
    unsigned mcy_flips = 0;
    ULONGLONG mcy_t = GetTickCount64();
    if (main_cycles && s_main_thread) QueryThreadCycleTime(s_main_thread, &mcy_last);
    mcy_flips = cellGcm_flip_request_count();
#endif

#ifdef PORT_PGO_GEN
    const ULONGLONG pgo_t0 = GetTickCount64();
    unsigned long pgo_from = 0, pgo_to = 0;
    int pgo_state = 0;   /* 0 waiting, 1 counting, 2 written */
    { const char* e = getenv("PS3_PGO_WINDOW");
      if (e && sscanf(e, "%lu:%lu", &pgo_from, &pgo_to) == 2 && pgo_to > pgo_from)
          fprintf(stderr, "[pgo] counters reset at %lu ms, profile written at %lu ms\n", pgo_from, pgo_to);
      else pgo_state = 2; }
#endif

    for (;;) {
#ifdef PORT_PGO_GEN
        if (pgo_state < 2) {
            const ULONGLONG el = GetTickCount64() - pgo_t0;
            if (pgo_state == 0 && el >= pgo_from) { __llvm_profile_reset_counters(); pgo_state = 1;
                fprintf(stderr, "[pgo] counters reset\n"); }
            if (pgo_state == 1 && el >= pgo_to) { const int rc = __llvm_profile_write_file(); pgo_state = 2;
                fprintf(stderr, "[pgo] profile written (rc %d)\n", rc); }
        }
#endif
#ifdef _WIN32
        if (main_cycles && s_main_thread && GetTickCount64() - mcy_t >= 5000) {
            ULONG64 c = 0;
            QueryThreadCycleTime(s_main_thread, &c);
            const unsigned fl = cellGcm_flip_request_count();
            if (fl != mcy_flips)
                fprintf(stderr, "[main-cyc] %u flips, %.2f Mcycles a flip on the guest main thread\n",
                        fl - mcy_flips, (double)(c - mcy_last) / 1e6 / (double)(fl - mcy_flips));
            mcy_last = c; mcy_flips = fl; mcy_t = GetTickCount64();
        }
#endif
        if (usleep_ab) sys_timer_usleep_ab_phase(rsx_draw_engine_ab_phase());
        if (store_ab == 1 && __atomic_load_n(&vm_st_inline, __ATOMIC_ACQUIRE)) {
            store_ab = 2;
            fprintf(stderr, "[store-ab] inline guest stores on and off by turns\n");
        }
        if (store_ab == 2) __atomic_store_n(&vm_st_inline, rsx_draw_engine_ab_phase(), __ATOMIC_RELEASE);
        if (vmx_ab) g_vmx_fast = rsx_draw_engine_ab_phase();
        fcw_mark(FCW_SLEEP);
        if (kick == 1 || (kick == 2 && rsx_draw_engine_ab_phase())) cellGcm_fifo_kick_wait(4);
        else                                                        Sleep(4);

        const unsigned due = ps3_vblank_clock_poll(&vbc, ps3_vblank_now_us(), 240);
        for (unsigned fired = 0; fired < due; fired++) {
            beat_state.rsx_ok = rsx_ok;
            fcw_mark(FCW_BEAT);
            ps3_frame_beat(&beat);
        }

        /* Drain at the outer cadence too, not only on the 16 ms tick: titles
         * fence every render pass on a label the drain writes, and one wave of
         * those at 16 ms apiece paces the guest into single-figure frame rates.
         * The real RSX writes them in microseconds. */
        if (rsx_ok) {
            if (cellGcm_take_flip_pending()) {
                fcw_mark(FCW_PRESENT);
                present_guest_frame();
                last_flip = cellGcm_flip_request_count();
            }
            fcw_mark(FCW_DRAIN);
            cellGcm_rsx_process_fifo();

            fcw_mark(FCW_PUMP);
            if (rsx_backend_pump() != 0) {
                rsx_ok = 0;              /* window closed */
#ifdef _WIN32
                /* The guest threads keep running without a backend and crash on the way out: leave the
                 * process here, the caches are already saved while running. */
                fflush(NULL);
                ExitProcess(0);
#endif
                continue;
            }
            /* Present on a guest flip. A present on a fixed clock can catch the
             * drain mid-frame and flash a partial one. Before the first flip
             * present freely, so the window is not blank during boot. */
            unsigned fc = cellGcm_flip_request_count();
            if (fc != last_flip) {
                fcw_mark(FCW_PRESENT);
                present_guest_frame();
                last_flip = fc;
            } else if (fc == 0) {
                fcw_mark(FCW_PRESENT);
                rsx_backend_present();
                present_clock_start();
                frame_log('b');
            }
        }
    }
    return 0;
}

/* ---------------------------------------------------------------------------
 * VFS root
 * -----------------------------------------------------------------------*/
/* Derive the directory holding PS3_GAME from the EBOOT path
 * <root>/PS3_GAME/USRDIR/EBOOT.elf -> <root>. $PS3_VFS_ROOT overrides. */
static char s_vfs_root[1024];

static void derive_vfs_root(const char* eboot)
{
    const char* env = getenv("PS3_VFS_ROOT");
    if (env && *env) { ppu_vfs_root = env; return; }

    strncpy(s_vfs_root, eboot, sizeof s_vfs_root - 1);
    for (char* p = s_vfs_root; *p; p++) if (*p == '\\') *p = '/';
    /* strip EBOOT.elf, USRDIR and PS3_GAME */
    for (int i = 0; i < 3; i++) { char* s = strrchr(s_vfs_root, '/'); if (s) *s = 0; }
    if (!s_vfs_root[0]) strcpy(s_vfs_root, ".");
    ppu_vfs_root = s_vfs_root;
}

/* /dev_hdd1 is the writable cache partition. Without PS3_HDD1_ROOT the runtime
 * resolves it inside the VFS root, i.e. the extracted disc tree, and the game's
 * cache writes (FIOS cache, font copies) land there. Default it to "hdd1"
 * beside the executable and make sure the directory exists. */
static char s_hdd1_root[1100];

static void isolate_hdd1(const char* exe)
{
    const char* env = getenv("PS3_HDD1_ROOT");
    if (env && *env) {
        strncpy(s_hdd1_root, env, sizeof s_hdd1_root - 1);
    } else {
        strncpy(s_hdd1_root, exe, sizeof s_hdd1_root - 1);
#ifdef _WIN32
        GetModuleFileNameA(NULL, s_hdd1_root, sizeof s_hdd1_root - 8);  /* argv[0] may lack a dir */
#endif
        for (char* p = s_hdd1_root; *p; p++) if (*p == '\\') *p = '/';
        char* s = strrchr(s_hdd1_root, '/');
        if (s) strcpy(s + 1, "hdd1"); else strcpy(s_hdd1_root, "hdd1");
    }
#ifdef _WIN32
    CreateDirectoryA(s_hdd1_root, NULL);
    if (!env || !*env) {
        char kv[1200];
        snprintf(kv, sizeof kv, "PS3_HDD1_ROOT=%s", s_hdd1_root);
        _putenv(kv);
    }
#else
    mkdir(s_hdd1_root, 0755);
    setenv("PS3_HDD1_ROOT", s_hdd1_root, 0);
#endif
    fprintf(stderr, "[vfs] /dev_hdd1 -> %s\n", s_hdd1_root);
}

/* ---------------------------------------------------------------------------
 * PS3_DEV_SKIP_INTRO (development only, off by default)
 * -----------------------------------------------------------------------*/
/* PS3_DEV_SKIP_INTRO=1 presses CROSS once, PS3_DEV_SKIP_INTRO_DELAY_MS (default
 * 1500) after the guest opens gui_intro_*.bik, through cellPadGetData port 0.
 * The original intro page (introvideo.lyt) binds its Accept slot to
 * TransitionPage(black), the page its movie's VideoIsFinished also leads to;
 * the game reads the press and takes that path itself. Input only: no guest
 * state, PC, file data or timing is touched. See
 * docs/ORIGINAL_INTRO_SKIP_ANALYSIS.md and docs/INTRO_SKIP_IMPLEMENTATION.md. */
static void dev_skip_intro(void)
{
    const char* e = getenv("PS3_DEV_SKIP_INTRO");
    if (!e || strcmp(e, "1") != 0) return;
    uint32_t delay = PAD_TRIGGER_DELAY_MS;
    const char* d = getenv("PS3_DEV_SKIP_INTRO_DELAY_MS");
    if (d && *d) delay = (uint32_t)strtoul(d, NULL, 10);
    if (pad_trigger_configure("gui_intro_", 0x4000 /* CROSS */, delay, PAD_TRIGGER_HOLD_MS) != 0)
        fprintf(stderr, "[dev-skip-intro] not configured\n");
}

/* ---------------------------------------------------------------------------
 * MSPR_PATCH (drs by default)
 * -----------------------------------------------------------------------*/
/* MSPR_PATCH=<names, comma separated> turns on the RPCS3 community patches for
 * this disc (BCUS98155 01.00, RPCS3 key PPU-34984cacd60f2ee2a380157a009122698d470056;
 * authors illusion, ZEROx and regal.). A code patch named as <name>:ab goes on
 * and off with the engine's in-run A/B side instead (drs:ab). Unset, the list
 * is MSPR_PATCH_DEFAULT (drs, mspr_patch.h); "none" or empty turns all off.
 *   60fps    0x00435D1C  stw -> nop          60 Hz; needs a locked 60 fps
 *   vfps     0x00435F9C  lwz r6 -> li r6,1   variable frame rate, speed by elapsed time
 *   drs      0x00360590  lbz r3 -> li r3,0   no dynamic resolution scaling
 *   mblur    0x0035FDEC  lbz r3 -> li r3,0   no motion blur
 *   shadows  0x00E31300  "data/%s/%s.trg" -> ""
 *   crowd    0x00DFF908  "audio/crowd0%d" -> ""   no crowd noise in the menus
 *   audiothread (1.03 only, opt-in)  the audio update on its own guest thread, joined at the flip (audio_thread.cpp)
 * The code patches are in the lifted code, each asking mspr_patch_on()
 * (generated/analysis/vksync/tools/mspr_patch_lifted.py); the string patches
 * are written here once the ELF is loaded, if the original bytes are there. */
static uint32_t s_mspr_patch, s_mspr_patch_ab;

extern "C" int mspr_patch_on(uint32_t bit)
{
    if (s_mspr_patch & bit) return 1;
    return (s_mspr_patch_ab & bit) ? rsx_draw_engine_ab_phase() : 0;
}

/* A patch turned on or off from the PC Settings page (pc_menu.cpp). */
extern "C" void mspr_patch_set(uint32_t bit, int on)
{
    if (on) s_mspr_patch |= bit;
    else s_mspr_patch &= ~bit;
    fprintf(stderr, "[mspr-patch] on 0x%02X (PC Settings)\n", s_mspr_patch);
}

/* MSPR_SLICE_MS: the main thread's per-frame task slice in func_005346A8 (1.00;
 * generated/analysis/vksync/tools/slice_patch_lifted.py). The game polls its task list
 * until more than 11 ms have passed, about 12 ms every frame, made for the 30 fps lock;
 * a smaller value lets a menu frame rate go above ~80 fps. Unset: the game's 11 at every rate.
 * K3039/K3040 (4 ms "held" 100/144 Hz) never reached a race; in a real 1.00 race 4 ms is far
 * worse (Kk3070 11 ms 28.8 fps vs Kk3071 4 ms 11.6 fps, main-thread usleep 258 -> 816 ms/s):
 * the slice is real task work, not idle polling. */
extern "C" int mspr_slice_ms(int game_ms)
{
    static int v = -2;
    if (v == -2) {
        const char* e = getenv("MSPR_SLICE_MS");
        const char* hz = getenv("PS3_SIM_PACE_HZ");
        (void)hz;   /* no rate-based default any more: see the comment above */
        v = (e && *e) ? atoi(e) : -1;
        if (v < 0 || v > 100) v = -1;
        if (v >= 0) fprintf(stderr, "[mspr-slice] task slice %d ms (game %d)\n", v, game_ms);
    }
    return v >= 0 ? v : game_ms;
}

/* MSPR_DIST: draw, LOD and shadow distances, each the game's value unless set
 * (generated/analysis/distance/DISTANCE.md; vksync/tools/dist_patch_lifted.py).
 *   0 MSPR_SHADOW_RANGE  shadow range, replaces 200.0
 *   1 MSPR_LOD_BIAS      added to every viewportquality.xml lodBias
 *   2,3 MSPR_CULL_SCALE  multiplies cullThreshold and shadowCullThreshold
 *   4 MSPR_SHADOW_FADE   multiplies shadowFadeDistModifier
 * MSPR_DIST_GROUPS (kinds 1-3 only): the GroupSettings groups the LOD bias and cull scale reach.
 * The parser stores each group's lodBias (kind 1), then its cullThreshold (2) and shadowCullThreshold (3),
 * groups in file order object, dyn, world, vehicle, player for 1, 2 and 4 viewports (game.log lines), so
 * the group is the kind-1 call count mod 5. Default "object,dyn,world": the opponents' vehicle group and the
 * player group keep the game's values (far opponents drawn past their cull showed through terrain, user report
 * 2026-11-22, generated/analysis/vksync/GLITCHES.md; HYPOTHESIS until the Kfd arms). "all" = every group. */
static int mspr_dist_group_on(int group)
{
    static int mask = -1;
    if (mask < 0) {
        static const char* const gname[] = { "object", "dyn", "world", "vehicle", "player" };
        const char* e = getenv("MSPR_DIST_GROUPS");
        if (!e || !*e) e = "object,dyn,world";
        mask = 0;
        if (strstr(e, "all")) mask = 31;
        for (int g = 0; g < 5; g++) if (strstr(e, gname[g])) mask |= 1 << g;
        fprintf(stderr, "[mspr-dist] groups %s (mask 0x%X)\n", e, mask);
    }
    return group < 0 || ((mask >> group) & 1);
}

extern "C" float mspr_dist_f(int kind, float v)
{
    static const char* const name[] = { "MSPR_SHADOW_RANGE", "MSPR_LOD_BIAS", "MSPR_CULL_SCALE",
                                        "MSPR_CULL_SCALE", "MSPR_SHADOW_FADE" };
    static int logged[5];
    static long n_group;   /* kind-1 calls: one per group */
    static int group = -1;
    if (kind < 0 || kind > 4) return v;
    if (kind == 1) group = (int)(n_group++ % 5);
    const char* e = getenv(name[kind]);
    if (!e || !*e) return v;
    if (kind >= 1 && kind <= 3 && !mspr_dist_group_on(group)) {
        if (logged[kind]++ < 16)
            fprintf(stderr, "[mspr-dist] %s kind %d group %d: %g kept\n", name[kind], kind, group, v);
        return v;
    }
    const float x = (float)atof(e);
    const float r = kind == 0 ? x : kind == 1 ? v + x : v * x;
    if (logged[kind]++ < 16)
        fprintf(stderr, "[mspr-dist] %s kind %d group %d: %g -> %g\n", name[kind], kind, group, v, r);
    return r;
}

/* Screens (settings.ini "screens", PS3RECOMP_VK_SPAN=2|3; libs/video rsx_multiscreen.h): Hor+ for a window
 * over two or three monitors. The lens's frustum (1.00 func_004302B4, the body func_004302A8 branches to)
 * takes each half-angle from a film size over the focal length: f9 = [lens+0xB4] * [TOC 0x7050], then
 * f1 = f9 / focal [lens+0xB0] into the libm stub func_00755EE8 -> func_0070B6F0, an arc tangent (|x| > 1 is
 * reduced through 1/x, the infinities return constant half-pi values), and the same for [lens+0xB8].
 * The results become the frustum vector at lens+0x70, which func_004301A8 reads back as the view's x and y
 * extents. launcher/pipeline/screens_patch_lifted.py makes the first film load pass through here, so the
 * horizontal extent (tan of the half-angle) is widened by the window's aspect over 16:9 while the vertical one,
 * the focal length and the lens memory stay as they are (nothing is written to the guest; a lens rebuilt
 * again gets the same result, no compounding). Without a span window the factor is 1 and v comes back as is. */
extern "C" float rsx_ms_hfov_scale(void);   /* libs/video rsx_draw_engine.c: 1 unless a span window is open */
extern "C" double mspr_screens_film(double v)
{
    const float k = rsx_ms_hfov_scale();
    if (k == 1.0f) return v;
    static int logged;
    if (logged++ < 4) fprintf(stderr, "[multiscreen] lens film width %g -> %g (x%.3f)\n", v, v * k, k);
    return v * (double)k;
}

/* MSPR_CAM: the camera-shake fix under vfps (generated/analysis/vksync/GLITCHES.md;
 * vksync/tools/cam_patch_lifted.py). The camera scales its per-update deltas by
 * a rate in updates per second that the game copies each frame from a field set
 * once: 30 at the 30 fps lock, but 25 under vfps while the world steps the real
 * frame time, so the camera and the vehicle disagree by an error that grows with
 * speed. With vfps on, the rate becomes 1/(this frame's clamped world dt), which
 * is 30 at 30 fps. MSPR_CAM=0 keeps the game's value. */
static double s_mspr_wdt;

extern "C" void mspr_wdt_note(double dt)
{
    s_mspr_wdt = dt;
    static int log = -1;   /* MSPR_DT_LOG=<n>: the first n world steps with their wall time (diagnostic, generated/analysis/vehfps) */
    static long n;
    if (log < 0) { const char* e = getenv("MSPR_DT_LOG"); log = e && *e ? atoi(e) : 0; }
    if (log > 0 && n < log) {
        struct timespec ts;
        timespec_get(&ts, TIME_UTC);
        fprintf(stderr, "[wdt] n=%ld t=%.0f dt=%.6f\n", n++, (double)ts.tv_sec * 1e6 + (double)ts.tv_nsec * 1e-3, dt);
    }
}

static int mspr_cam_mode(void);

/* The frame-rate patch whose world step the camera must follow: vfps always (mode 0 and 1);
 * mode 1 also the 60 fps lock, whose camera rate is the same 30 copy with a 1/60 world step. */
static int mspr_cam_driven(void)
{
    if (mspr_patch_on(2u)) return 1;
    return mspr_cam_mode() == 1 && mspr_patch_on(1u);
}

extern "C" float mspr_cam_rate(float v)
{
    static int on = -1, logged;
    if (on < 0) { const char* e = getenv("MSPR_CAM"); on = !(e && e[0] == '0'); }
    if (!on || !mspr_cam_driven() || !(s_mspr_wdt > 1e-4)) return v;
    const float r = (float)(1.0 / s_mspr_wdt);
    if (logged++ < 8) fprintf(stderr, "[mspr-cam] camera rate %g -> %g (world dt %g)\n", v, r, s_mspr_wdt);
    return r;
}

/* MSPR_CAM_SHAKE=<scale>: how much of camerasystem::Shake reaches the camera.
 * The game runs it on every race update (Kk117: active in all of them), so the
 * view shakes harder the faster you go. Default 0.3; 1 is the game's shake, 0
 * none (then the update is skipped at entry, as the game's own inactive path). */
/* MSPR_CAM_MODE (default 0 = the behaviour above, unchanged):
 *   0  the rate fix, and the shake at MSPR_CAM_SHAKE (default 0.3) under every patch set.
 *   1  the rate fix also under the 60 fps lock, and under vfps or 60fps the shake stays at the
 *      game's strength (1) but its offset is renewed at 30 Hz of world time and held in between
 *      (mspr_cam_shake_hold), so above 30 fps it moves as at the original 30. An explicit
 *      MSPR_CAM_SHAKE still overrides the scale. With neither patch the behaviour is unchanged. */
static int mspr_cam_mode(void)
{
    static int m = -1;
    if (m < 0) {
        const char* e = getenv("MSPR_CAM_MODE");
        m = (e && *e == '1') ? 1 : 0;
        fprintf(stderr, "[mspr-cam] camera mode %d%s\n", m,
                m ? " (shake held at 30 Hz under vfps)" : "");
    }
    return m;
}

static float mspr_cam_shake_scale(void)
{
    static float s = -1.0f;
    if (s < 0.0f) {
        const char* e = getenv("MSPR_CAM_SHAKE");
        if (e && *e) s = (float)atof(e);
        else if (mspr_cam_mode() == 1 && mspr_cam_driven()) s = 0.3f;   /* as at 30 fps (mode 0), renewed at 30 Hz */
        else s = 0.3f;
        if (!(s >= 0.0f)) s = 0.0f;
        if (s > 1.0f) s = 1.0f;
        fprintf(stderr, "[mspr-cam] camera shake scale %g\n", s);
    }
    return s;
}

/* Mode 1 above 30 fps: the game draws a new random shake offset every update, so at 60 it jitters twice
 * as often as the original (the "vibrating" look) while the boost shake should stay. The offset is renewed
 * once per 1/30 s of world time and held in between, applied to each update's unshaken camera. */
static int s_shake_renew = 1;
static double s_shake_acc;

static int mspr_cam_shake_hold(void)
{
    return mspr_cam_mode() == 1 && mspr_cam_driven() && s_mspr_wdt > 1e-4 && s_mspr_wdt < 1.0 / 30.0 - 1e-4;
}

/* MSPR_CAM_SHAKE_SMOOTH (default 1; 0 = the plain hold above): a held offset steps the camera position
 * every second frame at 60, and the shake is a position offset, so the near vehicle jumps on screen in
 * 2-frame steps while the far scene barely moves -- the vehicle "runs at a lower frame rate"
 * (generated/analysis/vehfps, Kveh60f2 vs Kveh60fs). Smoothed, the applied offset walks linearly from
 * the previous 30 Hz offset to the newest by the world time since the renewal (half a renewal behind):
 * still one new random offset per 1/30 s, but no 2-frame steps. Only while the hold is active. */
static int mspr_cam_shake_smooth(void)
{
    static int on = -1;
    if (on < 0) {
        const char* e = getenv("MSPR_CAM_SHAKE_SMOOTH");
        on = !(e && e[0] == '0');
        fprintf(stderr, "[mspr-cam] held shake %s\n", on ? "smoothed between 30 Hz offsets" : "held (stepped)");
    }
    return on;
}

extern "C" int mspr_cam_shake(uint32_t active)
{
    static uint32_t calls, act;
    const float s = mspr_cam_shake_scale();
    if (mspr_cam_shake_hold()) {
        s_shake_acc += s_mspr_wdt;
        s_shake_renew = s_shake_acc >= 1.0 / 30.0;
        if (s_shake_renew) { s_shake_acc -= 1.0 / 30.0; if (s_shake_acc > 1.0 / 30.0) s_shake_acc = 0; }
    } else s_shake_renew = 1;
    calls++;
    if (active & 0xFFu) act++;
    if (!(calls & 4095u)) fprintf(stderr, "[mspr-cam] shake active in %u of %u updates\n", act, calls);
    return s == 0.0f && (active & 0xFFu);
}

/* The shake's result stores (two camera vectors, guest byte order): blended
 * from what was there (the unshaken camera) by the scale. */
extern "C" void mspr_cam_shake_st16(uint64_t ea, const void* src)
{
    uint8_t* p = vm_base + (uint32_t)ea;
    const float s = mspr_cam_shake_scale();
    static uint32_t n;
    static double sum, mx;
    {   /* the shake's offset (xyz) before the blend, logged every 256 stores */
        double d2 = 0;
        for (int i = 0; i < 3; i++) {
            uint32_t a, b;
            memcpy(&a, p + 4 * i, 4); memcpy(&b, (const uint8_t*)src + 4 * i, 4);
            a = _byteswap_ulong(a); b = _byteswap_ulong(b);
            float fa, fb;
            memcpy(&fa, &a, 4); memcpy(&fb, &b, 4);
            d2 += (double)(fb - fa) * (fb - fa);
        }
        const double d = sqrt(d2);
        if (d == d && d < 1e6) { sum += d; if (d > mx) mx = d; }
        if (!(++n & 255u)) {
            fprintf(stderr, "[mspr-cam] shake offset mean %.4f max %.4f (world units, x%g applied)\n", sum / 256.0, mx, s);
            sum = 0; mx = 0;
        }
    }
    /* the held offsets, one per store address (the shake writes 4 camera vectors) */
    static struct { uint32_t ea; float off[4], prev[4]; } held[8];   /* off: the newest 30 Hz offset; prev: the one before */
    int h = -1;
    for (int k = 0; k < 8; k++) if (held[k].ea == (uint32_t)ea) { h = k; break; }
    if (h < 0) { for (int k = 0; k < 8; k++) if (!held[k].ea) { h = k; held[k].ea = (uint32_t)ea; break; } }
    const int holding = h >= 0 && mspr_cam_shake_hold();
    const int hold = holding && !s_shake_renew;
    const int smooth = holding && mspr_cam_shake_smooth();
    float ph = (float)(s_shake_acc * 30.0);   /* world time since the renewal, in 30 Hz steps */
    if (!(ph > 0.0f)) ph = 0.0f;
    if (ph > 1.0f) ph = 1.0f;
    if (s >= 1.0f && !hold && h < 0) { memcpy(p, src, 16); return; }
    for (int i = 0; i < 4; i++) {
        uint32_t a, b;
        memcpy(&a, p + 4 * i, 4); memcpy(&b, (const uint8_t*)src + 4 * i, 4);
        a = _byteswap_ulong(a); b = _byteswap_ulong(b);
        float fa, fb;
        memcpy(&fa, &a, 4); memcpy(&fb, &b, 4);
        float off = fb - fa;
        if (h >= 0) {
            if (smooth) {   /* MSPR_CAM_SHAKE_SMOOTH: prev -> newest by the phase */
                if (s_shake_renew) { held[h].prev[i] = held[h].off[i]; held[h].off[i] = off; }
                off = held[h].prev[i] + (held[h].off[i] - held[h].prev[i]) * ph;
            } else {
                if (hold) off = held[h].off[i]; else held[h].off[i] = off;
                held[h].prev[i] = held[h].off[i];
            }
        }
        const float f = fa + s * off;
        uint32_t r;
        memcpy(&r, &f, 4);
        r = _byteswap_ulong(r);
        memcpy(p + 4 * i, &r, 4);
    }
}

/* MSPR_CAM_SPRING=1 (generated/analysis/otherport/IMPLEMENT.md item 4b, opt-in, default off): the chase
 * camera's spring step, func_0037FB68(camera r3, vehicle r4) (and its alias entry 0x0037FB64), adds a fixed
 * per-call acceleration and damping to the CHASE_SHAKE springs at camera +0x230..+0x280 and never reads dt,
 * so above 30 fps the camera sways and shakes faster and harder than the original. With the switch it runs
 * once per 1/30 s of the game's frame clock per camera (the per-frame step func_008CF1C0 receives in f1,
 * before any slow-motion scaling), and is skipped (at entry, nothing written) on the frames in between. At
 * 30 fps every call runs, as before. Every call of one camera within one frame gets the same answer.
 * generated/analysis/otherport/tools/spring_patch_ppucc.py adds the two hooks to the lifted code. */
static double s_mspr_frame_clock;     /* sum of the game's per-frame steps (s) */
static uint64_t s_mspr_frame_no;      /* frame-step calls so far */

extern "C" void mspr_frame_step_note(double dt)
{
    if (dt > 0.0 && dt < 1.0) s_mspr_frame_clock += dt;
    s_mspr_frame_no++;
    static int log = -1;   /* MSPR_CAM_SPRING_LOG=<n>: the first n frame steps (diagnostic) */
    if (log < 0) { const char* e = getenv("MSPR_CAM_SPRING_LOG"); log = e && *e ? atoi(e) : 0; }
    if (log > 0 && s_mspr_frame_no <= (uint64_t)log)
        fprintf(stderr, "[mspr-spring] frame %llu step %.6f clock %.4f\n", (unsigned long long)s_mspr_frame_no, dt,
                s_mspr_frame_clock);
}

extern "C" int mspr_cam_spring_skip(uint64_t cam)
{
    static int on = -1;
    if (on < 0) {
        const char* e = getenv("MSPR_CAM_SPRING");
        on = e && e[0] == '1';
        fprintf(stderr, "[mspr-spring] chase-camera springs %s\n", on ? "stepped at 30 Hz of the frame clock" : "every call (game)");
    }
    if (!on) return 0;
    if (!s_mspr_frame_no) {   /* no frame clock yet: never skip */
        static int warned;
        if (!warned++) fprintf(stderr, "[mspr-spring] no frame step seen yet: springs run every call\n");
        return 0;
    }
    static struct { uint32_t cam; uint64_t frame; int skip; double due; } t[8];
    static uint64_t steps, skips;
    int h = -1;
    for (int k = 0; k < 8; k++) if (t[k].cam == (uint32_t)cam) { h = k; break; }
    if (h < 0) {
        for (int k = 0; k < 8; k++) if (!t[k].cam) { h = k; break; }
        if (h < 0) return 0;   /* more than 8 cameras: unchanged */
        t[h].cam = (uint32_t)cam; t[h].frame = s_mspr_frame_no; t[h].skip = 0;
        t[h].due = s_mspr_frame_clock + 1.0 / 30.0;
        steps++;
        return 0;
    }
    if (t[h].frame == s_mspr_frame_no) return t[h].skip;
    t[h].frame = s_mspr_frame_no;
    const double now = s_mspr_frame_clock;
    if (now + 1e-4 >= t[h].due) {
        t[h].due += 1.0 / 30.0;
        if (t[h].due + 1e-4 <= now) t[h].due = now + 1.0 / 30.0;   /* a long frame: no burst of catch-up steps */
        t[h].skip = 0;
        steps++;
    } else {
        t[h].skip = 1;
        skips++;
    }
    if (!((steps + skips) & 4095u))
        fprintf(stderr, "[mspr-spring] %llu spring steps, %llu skipped (camera 0x%08X)\n",
                (unsigned long long)steps, (unsigned long long)skips, (uint32_t)cam);
    return t[h].skip;
}

static void mspr_patch_init(void)
{
    static const struct { const char* name; uint32_t bit, ea; const char* str; } k[] = {
        { "60fps", 1u, 0, NULL }, { "vfps", 2u, 0, NULL }, { "drs", 4u, 0, NULL }, { "mblur", 8u, 0, NULL },
        { "shadows", 16u, 0x00E31300u, "data/%s/%s.trg" }, { "crowd", 32u, 0x00DFF908u, "audio/crowd0%d" },
        { "audiothread", 64u, 0, NULL },
    };
    const size_t n = sizeof k / sizeof k[0];
    const char* env = getenv("MSPR_PATCH");
    const char* e = mspr_patch_spec(env);
    if (!*e) {
        fprintf(stderr, "[mspr-patch] none\n");
        return;
    }
    char buf[256];
    snprintf(buf, sizeof buf, "%s", e);
    for (char* t = strtok(buf, ","); t; t = strtok(NULL, ",")) {
        char* mode = strchr(t, ':');
        if (mode) *mode++ = 0;
        size_t i = 0;
        while (i < n && strcmp(t, k[i].name) != 0) i++;
        if (i == n || (mode && (strcmp(mode, "ab") != 0 || k[i].str))) {
            fprintf(stderr, "[mspr-patch] '%s%s%s' not known, ignored\n", t, mode ? ":" : "", mode ? mode : "");
            continue;
        }
        if (k[i].str) {
            const size_t len = strlen(k[i].str) + 1;
            if (memcmp(vm_base + k[i].ea, k[i].str, len) != 0) {
                fprintf(stderr, "[mspr-patch] %s: bytes at 0x%08X are not the expected string, not applied\n",
                        k[i].name, k[i].ea);
                continue;
            }
            vm_base[k[i].ea] = 0;
        }
        if (mode) s_mspr_patch_ab |= k[i].bit;
        else s_mspr_patch |= k[i].bit;
    }
    fprintf(stderr, "[mspr-patch] on 0x%02X, by turns 0x%02X%s\n", s_mspr_patch, s_mspr_patch_ab,
            env ? "" : " (default " MSPR_PATCH_DEFAULT ")");
}

/* MSPR_CAM_COCKPIT=1 (opt-in, 1.00 ELF): an extra in-cockpit camera in the
 * SELECT cycle, data-driven. The game reads each vehicle's camera list from
 * "data/camera_config_files/%s_cams.txt" (1.00: string at 0x00E1C810, loader
 * 0x00374084); the list has CAMERA 1 (chase) and CAMERA 2 (bonnet), and the
 * loader keeps as many cameras as the highest CAMERA number (1..9), which the
 * SELECT cycle (0x00371948) walks. Here the name becomes "%s_camz.txt": no
 * archive member has it, so the game's file layer reads it from
 * PS3_VFS_OVERLAY, where generated/analysis/cockpit/tools/make_cockpit_overlay.py
 * writes each original list plus a CAMERA 3 at the driver's eye. Applied only
 * when the overlay has data/camera_config_files/, so a missing overlay cannot
 * leave the game without camera files. No code, physics or gameplay changes. */
static void mspr_cam_cockpit_init(void)
{
    const char* e = getenv("MSPR_CAM_COCKPIT");
    if (!e || e[0] != '1') return;
    static const char k_orig[] = "data/camera_config_files/%s_cams.txt";
    const uint32_t ea = 0x00E1C810u;
    const char* ov = getenv("PS3_VFS_OVERLAY");
    char probe[1024];
    struct stat st;
    if (!ov || !*ov || snprintf(probe, sizeof probe, "%s/data/camera_config_files/buggy01_camz.txt", ov) >= (int)sizeof probe
        || stat(probe, &st) != 0) {
        fprintf(stderr, "[cam-cockpit] no %s, not applied (make_cockpit_overlay.py --out <PS3_VFS_OVERLAY>)\n",
                ov && *ov ? probe : "PS3_VFS_OVERLAY");
        return;
    }
    if (memcmp(vm_base + ea, k_orig, sizeof k_orig) != 0) {
        fprintf(stderr, "[cam-cockpit] bytes at 0x%08X are not the expected string, not applied\n", ea);
        return;
    }
    vm_base[ea + sizeof k_orig - 6] = 'z';   /* "_cams.txt" -> "_camz.txt" */
    fprintf(stderr, "[cam-cockpit] on: camera lists from %s/data/camera_config_files/*_camz.txt\n", ov);
}

/* MSPR_COCKPIT_TUNE (on with the cockpit camera; MSPR_COCKPIT_TUNE=0 turns it off): live tuning of the cockpit
 * camera per vehicle. The camera-list parser (1.00 func_0037D640, line "CAMERA n TYPE focal x y z yaw pitch roll",
 * sscanf locals at r1+0xB4 focal, +0xB0 x, +0xAC y, +0xA8 z, +0xA4 yaw, +0x9C pitch, +0x94 roll, n at r1+0xA0,
 * vehicle name in r25, camera slot in r27) stores a FORWARD entry into the slot's view [slot+8]: position object
 * [view+4] +0x70/+0x74/+0x78 = x/y/z, orientation object [view+8] +0x7C/+0x80/+0x84 = yaw/pitch/roll, lens
 * [view+0] +0xB0 = focal * 0.001 clamped to [+0xA8, +0xAC] (func_0042FDB0), projection from func_004302A8.
 * Both objects are camera platforms (constructor func_008F58F8 stores x y z yaw pitch roll at +0x70..+0x84): [view+4]
 * "Offset camera platform" (translation from the vehicle = the eye), [view+8] "Orientation camera platform", its
 * child (rotation about that eye). Their update (vtable slot 2, func_004271A0) reads +0x70..+0x84 every update
 * into func_0042D2E0, so a write moves the eye (and with it the view) or turns the view about the eye.
 * generated/analysis/cockpit/tools/cockpit_tune_patch_ppucc.py adds two hooks to the lifted code: after those
 * stores mspr_cock_parsed() records CAMERA 2 (bonnet) and CAMERA 3 (cockpit) of the loading vehicle (one list per
 * race: the player's) and applies its saved values; once per camera update mspr_cock_tick() reads the keys and
 * writes the cockpit camera's own objects (no other camera reads them). A non-zero return is the lens the patched
 * code passes to func_004302A8 again. Keys, only while the game window is in front:
 *   free flight (held keys move at a speed, frame-time scaled): I/K forward/back and J/L strafe along the
 *   camera's heading, T/G (or Num+/Num-) up/down, . / , pitch, M / N turn (yaw), O / U focal, Shift x5, Num0 x0.2,
 *   only while the cockpit view is the current camera; F2 saves all to
 *   cockpit_positions.json beside the exe (read at start; make_cockpit_overlay.py --positions bakes it in).
 * The values and the vehicle show in the window title and the log ([cockpit-tune]). */
#include "cockpit_tune.h"
extern "C" char rsx_title_suffix[256];   /* rsx_vulkan_backend.c: appended to the title-bar fps line */

static ct_table s_ct;
static struct {
    int ok;                       /* the cockpit camera below is live */
    char veh[CT_NAME];
    uint32_t slot, view, pos, ori, lens;   /* the cockpit camera's slot, its view and the view's objects */
    uint32_t ox, roll, pyaw, proll;   /* raw words never written here: the objects are still this vehicle's */
    char veh2[CT_NAME];           /* the bonnet camera of the list being parsed */
    float y2, z2, p2, yaw2;
} s_cock;
static char s_ct_path[1024];

static uint32_t ct_rd32(uint32_t ea) { uint32_t v; memcpy(&v, vm_base + ea, 4); return _byteswap_ulong(v); }
static float ct_rdf(uint32_t ea) { const uint32_t v = ct_rd32(ea); float f; memcpy(&f, &v, 4); return f; }
static void ct_wrf(uint32_t ea, float f) { uint32_t v; memcpy(&v, &f, 4); v = _byteswap_ulong(v); memcpy(vm_base + ea, &v, 4); }
static int ct_ea_ok(uint32_t ea) { return ea >= 0x10000u && ea < 0xE0000000u - 0x100u; }

static int ct_on(void)
{
    static int on = -1;
    if (on >= 0) return on;
    const char* c = getenv("MSPR_CAM_COCKPIT");
    const char* e = getenv("MSPR_COCKPIT_TUNE");
    on = c && c[0] == '1' && !(e && e[0] == '0');
    if (!on) return 0;
    char dir[1024];
    DWORD n = GetModuleFileNameA(NULL, dir, sizeof dir);
    if (!n || n >= sizeof dir) dir[0] = 0;
    char* sl = strrchr(dir, '\\');
    if (!sl) sl = strrchr(dir, '/');
    if (sl) sl[1] = 0; else dir[0] = 0;
    snprintf(s_ct_path, sizeof s_ct_path, "%scockpit_positions.json", dir);
    FILE* f = fopen(s_ct_path, "rb");
    if (f) {
        static char buf[65536];
        const size_t got = fread(buf, 1, sizeof buf - 1, f);
        fclose(f);
        buf[got] = 0;
        const int r = ct_parse_json(&s_ct, buf);
        if (r < 0) { s_ct.n = 0; fprintf(stderr, "[cockpit-tune] %s: not read (malformed)\n", s_ct_path); }
        else fprintf(stderr, "[cockpit-tune] %s: %d saved vehicle(s)\n", s_ct_path, r);
    } else fprintf(stderr, "[cockpit-tune] on, no %s yet (F2 writes it)\n", s_ct_path);
    return 1;
}

static void ct_show(const ct_entry* e)
{
    char ro[256];
    ct_readout(e, s_cock.p2, ro, sizeof ro);
    snprintf(rsx_title_suffix, sizeof rsx_title_suffix, " | %s", ro);
    fprintf(stderr, "[cockpit-tune] %s\n", ro);
}

/* the cockpit objects still hold what the parser wrote for this vehicle (a later race may have freed them) */
static int ct_live(void)
{
    if (!s_cock.ok) return 0;
    if (ct_rd32(s_cock.ori + 0x70) != s_cock.ox || ct_rd32(s_cock.ori + 0x84) != s_cock.roll
        || ct_rd32(s_cock.pos + 0x7C) != s_cock.pyaw || ct_rd32(s_cock.pos + 0x84) != s_cock.proll) {
        s_cock.ok = 0;
        rsx_title_suffix[0] = 0;
        fprintf(stderr, "[cockpit-tune] %s: cockpit camera gone, not written\n", s_cock.veh);
        return 0;
    }
    return 1;
}

static float s_wrote[6];   /* what ct_apply last wrote: x y z / yaw pitch (position and orientation objects) */
static int s_wrote_ok;

static void ct_apply(const ct_entry* e)
{
    s_wrote[0] = e->x; s_wrote[1] = s_cock.y2 + e->dy; s_wrote[2] = s_cock.z2 + e->dz;
    s_wrote[3] = s_cock.yaw2 + e->yaw; s_wrote[4] = s_cock.p2 + e->pitch; s_wrote_ok = 1;
    ct_wrf(s_cock.pos + 0x70, e->x);
    /* the height: the view's update (func_0037C598 region, 0x0037CBEC..0x0037CC18) sets the offset platform's y every
     * frame to [view+0x54] - [view+0x58] (the parsed eye height minus a clearance term), so the eye height lives at
     * view+0x54 (func_0037D1D0 stores the line's y there); +0x74 is written too for the frame in between */
    ct_wrf(s_cock.view + 0x54, s_cock.y2 + e->dy);
    ct_wrf(s_cock.pos + 0x74, s_cock.y2 + e->dy - ct_rdf(s_cock.view + 0x58));
    ct_wrf(s_cock.pos + 0x78, s_cock.z2 + e->dz);
    ct_wrf(s_cock.ori + 0x7C, s_cock.yaw2 + e->yaw);
    ct_wrf(s_cock.ori + 0x80, s_cock.p2 + e->pitch);
    float fov = e->focal * 0.001f;   /* the parser's scale (TOC 0x4EA0) and func_0042FDB0's clamp */
    const float lo = ct_rdf(s_cock.lens + 0xA8), hi = ct_rdf(s_cock.lens + 0xAC);
    if (lo > fov) fov = lo;
    else if (fov > hi) fov = hi;
    ct_wrf(s_cock.lens + 0xB0, fov);
}

/* each early return says why, once per reason (MSPR_COCKPIT_TUNE diagnostics) */
#define CT_WHY(...) do { static int _w; if (!_w++) fprintf(stderr, "[cockpit-tune] " __VA_ARGS__); } while (0)

/* site: 0 = an existing view's entry rewritten (0x0037D894), 1 = a new view built (0x0037DD0C) */
extern "C" uint64_t mspr_cock_parsed(uint64_t r1, uint64_t name, uint64_t slot, uint64_t site)
{
    static int calls;
    if (!calls++) fprintf(stderr, "[cockpit-tune] camera-list parse hook running (site %d)\n", (int)site);
    if (!ct_on()) { CT_WHY("parse hook: tuning off\n"); return 0; }
    if (!ct_ea_ok((uint32_t)r1) || !ct_ea_ok((uint32_t)name) || !ct_ea_ok((uint32_t)slot)) {
        CT_WHY("parse hook: bad pointers r1 0x%08X name 0x%08X slot 0x%08X\n", (uint32_t)r1, (uint32_t)name, (uint32_t)slot);
        return 0;
    }
    const uint32_t sp = (uint32_t)r1, n = ct_rd32(sp + 0xA0);
    char type[24];
    memcpy(type, vm_base + sp + 0xC8, sizeof type - 1);   /* the line's camera type (sscanf %s at r1+0xC8) */
    type[sizeof type - 1] = 0;
    if (!strstr(type, "_FORWARD")) return 0;   /* the new-view join is shared with the side/rear views */
    if (n != 2 && n != 3) return 0;
    char raw[64], veh[CT_NAME];
    memcpy(raw, vm_base + (uint32_t)name, sizeof raw - 1);
    raw[sizeof raw - 1] = 0;
    if (!ct_norm_name(raw, veh, sizeof veh)) { CT_WHY("parse hook: vehicle name not readable ('%.16s')\n", raw); return 0; }
    fprintf(stderr, "[cockpit-tune] %s: CAMERA %u %s parsed (site %d)\n", veh, n, type, (int)site);
    if (n == 2) {
        snprintf(s_cock.veh2, sizeof s_cock.veh2, "%s", veh);
        s_cock.y2 = ct_rdf(sp + 0xAC); s_cock.z2 = ct_rdf(sp + 0xA8); s_cock.p2 = ct_rdf(sp + 0x9C); s_cock.yaw2 = ct_rdf(sp + 0xA4);
        return 0;
    }
    if (strcmp(s_cock.veh2, veh) != 0) {
        fprintf(stderr, "[cockpit-tune] %s: no bonnet camera before the cockpit camera, not tunable\n", veh);
        return 0;
    }
    const uint32_t view = ct_rd32((uint32_t)slot + 8);
    if (!ct_ea_ok(view)) { CT_WHY("parse hook: no view at slot 0x%08X\n", (uint32_t)slot); return 0; }
    const uint32_t pos = ct_rd32(view + 4), ori = ct_rd32(view + 8), lens = ct_rd32(view);
    if (!ct_ea_ok(pos) || !ct_ea_ok(ori) || !ct_ea_ok(lens)) {
        CT_WHY("parse hook: view 0x%08X objects pos 0x%08X ori 0x%08X lens 0x%08X not valid\n", view, pos, ori, lens);
        return 0;
    }
    s_cock.ok = 1;
    snprintf(s_cock.veh, sizeof s_cock.veh, "%s", veh);
    s_cock.slot = (uint32_t)slot; s_cock.view = view; s_cock.pos = pos; s_cock.ori = ori; s_cock.lens = lens;
    s_cock.ox = ct_rd32(ori + 0x70); s_cock.roll = ct_rd32(ori + 0x84);
    s_cock.pyaw = ct_rd32(pos + 0x7C); s_cock.proll = ct_rd32(pos + 0x84);
    fprintf(stderr, "[cockpit-tune] %s: cockpit camera at pos 0x%08X ori 0x%08X lens 0x%08X\n", veh, pos, ori, lens);
    ct_entry* e = ct_find(&s_ct, veh, 0);
    if (e) {   /* saved in cockpit_positions.json, or tuned earlier in this session */
        ct_apply(e);
        ct_show(e);
        return lens;
    }
    e = ct_find(&s_ct, veh, 1);
    if (!e) return 0;
    e->x = ct_rdf(sp + 0xB0);
    e->dy = ct_rdf(sp + 0xAC) - s_cock.y2;
    e->dz = ct_rdf(sp + 0xA8) - s_cock.z2;
    e->pitch = ct_rdf(sp + 0x9C) - s_cock.p2;
    e->yaw = ct_rdf(sp + 0xA4) - s_cock.yaw2;
    e->focal = ct_rdf(sp + 0xB4);
    ct_show(e);
    return 0;
}

static int ct_focused(void)
{
    HWND fg = GetForegroundWindow();
    DWORD pid = 0;
    if (!fg) return 0;
    GetWindowThreadProcessId(fg, &pid);
    return pid == GetCurrentProcessId();
}

static int ct_save(void)
{
    static char js[CT_MAX * 128 + 64];
    const size_t w = ct_write_json(&s_ct, js, sizeof js);
    if (w >= sizeof js) return 0;
    char tmp[1100];
    snprintf(tmp, sizeof tmp, "%s.tmp", s_ct_path);
    FILE* f = fopen(tmp, "wb");
    if (!f) return 0;
    const int ok = fwrite(js, 1, w, f) == w;
    if (fclose(f) != 0 || !ok || !MoveFileExA(tmp, s_ct_path, MOVEFILE_REPLACE_EXISTING)) { remove(tmp); return 0; }
    for (int i = 0; i < s_ct.n; i++) s_ct.e[i].saved = 1;
    return 1;
}

/* The camera manager (r30 at the hook, the object whose +0xA58 rate the update copies) selects its current camera
 * by the u16 at +0x95A; camera i's slot is mgr + 0x1A4 + i * 0x30 (the per-frame update at 0x00376178 reads the type
 * at +0x1A0 + i * 0x30 + 4; the parser is handed mgr + 0x174 + n * 0x30 (+ set * 0x1E0) and writes the type at +0).
 * The keys act only while that slot is the cockpit camera's. */
static int ct_active(uint32_t mgr)
{
    if (!ct_ea_ok(mgr)) return 0;
    const uint32_t i = ct_rd32(mgr + 0x958) & 0xFFFFu;   /* the u16 at +0x95A */
    const int on = i < 64 && mgr + 0x1A4u + i * 0x30u == s_cock.slot;
    static int last = -1;
    if (on != last) {
        fprintf(stderr, "[cockpit-tune] camera index %u (manager 0x%08X, slot 0x%08X, cockpit slot 0x%08X): %s\n", i, mgr,
                mgr + 0x1A4u + i * 0x30u, s_cock.slot, on ? "cockpit view, keys on" : "not the cockpit view, keys off");
        last = on;
    }
    return on;
}

static int ct_key(int vk) { return (GetAsyncKeyState(vk) & 0x8000) != 0; }

extern "C" uint64_t mspr_cock_tick(uint64_t mgr)
{
    static int calls;
    if (!calls++) fprintf(stderr, "[cockpit-tune] camera update hook running (manager 0x%08X)\n", (uint32_t)mgr);
    if (!ct_on()) { CT_WHY("update hook: tuning off\n"); return 0; }
    if (!s_cock.ok) { CT_WHY("update hook: no cockpit camera recorded (yet): its list was not seen by the parse hook\n"); return 0; }
    static LARGE_INTEGER freq, last;
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    if (!freq.QuadPart) QueryPerformanceFrequency(&freq);
    const float dt = last.QuadPart ? (float)((double)(now.QuadPart - last.QuadPart) / (double)freq.QuadPart) : 0.0f;
    last = now;
    if (!ct_active((uint32_t)mgr)) return 0;   /* ct_active logs each change */
    if (!ct_focused()) { CT_WHY("update hook: game window not in front, keys ignored (said once)\n"); return 0; }
    /* Free flight: I/K forward/back and J/L strafe along the camera's heading, Num+/Num- straight up/down,
     * . / , pitch, M / N turn, O / U focal, Shift x5, Num0 x0.2, F2 save. None is a default game key
     * (pad_keyboard_map.h: W A S D, arrows, Space, Enter, Ctrl, Q, E, P, C; the player's settings.ini adds X and the
     * digit-row 1 and 2, not the keypad). */
    ct_input in;
    in.fwd = ct_key('I') - ct_key('K');
    in.left = ct_key('J') - ct_key('L');
    in.up = (ct_key('T') || ct_key(VK_ADD)) - (ct_key('G') || ct_key(VK_SUBTRACT));
    in.pitch = ct_key(VK_OEM_PERIOD) - ct_key(VK_OEM_COMMA);
    in.yaw = ct_key('M') - ct_key('N');
    in.focal = ct_key('O') - ct_key('U');
    const float mul = ct_key(VK_SHIFT) ? CT_FAST : ct_key(VK_NUMPAD0) ? CT_FINE : 1.0f;
    static int f2_was;
    const int f2 = ct_key(VK_F2), save = f2 && !f2_was;
    f2_was = f2;
    int changed = 0, focal = in.focal != 0;
    if (s_wrote_ok && ct_live()) {   /* does the game rewrite what we wrote? (said at most 8 times) */
        const float got[5] = { ct_rdf(s_cock.pos + 0x70), ct_rdf(s_cock.view + 0x54), ct_rdf(s_cock.pos + 0x78),
                               ct_rdf(s_cock.ori + 0x7C), ct_rdf(s_cock.ori + 0x80) };
        static const char* const nm[5] = { "pos x +0x70", "view eye height +0x54", "pos z +0x78", "orient yaw +0x7C", "orient pitch +0x80" };
        static int said;
        for (int k = 0; k < 5; k++)
            if (fabsf(got[k] - s_wrote[k]) > 1e-4f && said < 8) {
                said++;
                fprintf(stderr, "[cockpit-tune] the game changed %s: we wrote %.4f, now %.4f\n", nm[k], s_wrote[k], got[k]);
            }
    }
    if (in.fwd || in.left || in.up || in.pitch || in.yaw || in.focal) {
        static int moves;   /* the first moves log the stored position fields, to see which axis each key changes */
        if (moves < 40 && !(moves++ & 3))
            fprintf(stderr, "[cockpit-tune] keys fwd %d left %d up %d: stored x %.3f y %.3f z %.3f yaw %.2f pitch %.2f\n",
                    in.fwd, in.left, in.up, ct_rdf(s_cock.pos + 0x70), ct_rdf(s_cock.view + 0x54), ct_rdf(s_cock.pos + 0x78),
                    ct_rdf(s_cock.ori + 0x7C), ct_rdf(s_cock.ori + 0x80));
        if (!ct_live()) return 0;   /* ct_live logs it */
        ct_entry* ce = ct_find(&s_ct, s_cock.veh, 1);
        if (!ce) { CT_WHY("update hook: vehicle table full\n"); return 0; }
        if (ct_fly(ce, &in, s_cock.yaw2 + ce->yaw, dt, mul)) { ce->saved = 0; changed = 1; }
    }
    static float shown;   /* the readout is logged at most 4 times a second while moving */
    shown += dt;
    ct_entry* e = ct_find(&s_ct, s_cock.veh, 0);
    if (changed && e) {
        ct_apply(e);
        char ro[256];
        ct_readout(e, s_cock.p2, ro, sizeof ro);
        snprintf(rsx_title_suffix, sizeof rsx_title_suffix, " | %s", ro);
        if (shown >= 0.25f) { shown = 0; fprintf(stderr, "[cockpit-tune] %s\n", ro); }
    }
    if (save) {
        const int ok = ct_save();
        fprintf(stderr, "[cockpit-tune] F2: %s %s (%d vehicle(s))\n", ok ? "saved" : "could not write", s_ct_path, s_ct.n);
        if (ok && e) ct_show(e);
        else if (!ok) snprintf(rsx_title_suffix, sizeof rsx_title_suffix, " | cockpit: could not write cockpit_positions.json");
    }
    return changed && focal ? s_cock.lens : 0;
}

/* ---------------------------------------------------------------------------
 * MSPR_DEBUG_FLY=1 (off by default): a debug free-fly camera. F3, with the game window in front, turns
 * it on and off. On: every perspective draw at least 640 wide (the scene) is drawn from the fly view with
 * the game's projection (rsx_draw_set_view_override; the ortho shadow maps and the HUD keep their own
 * matrices, and the light cascade and the scene's extras keep the game's camera). The mouse looks (the
 * cursor is captured while on), W/S/A/D move 6 m/s, Shift x4, Space / Ctrl rise and fall. The math and its
 * tests: fly_cam.h, tests/test_fly_cam.c. The game's sim stop is mspr_fly_sim_step (below), hooked at the entry of
 * the lifted frame step func_008CF1C0 by launcher/pipeline/fly_pause_patch_lifted.py (F3 pauses the race). */
#include "fly_cam.h"
extern "C" void rsx_draw_set_view_override(int (*fn)(void*, const float*, uint32_t, float*, int), void* user);

static int s_fly_env = -1;               /* MSPR_DEBUG_FLY=1 */
static fly_mode s_fly_mode;
static fly_pose s_fly_pose;
static CRITICAL_SECTION s_fly_cs;        /* the pose: the frame thread writes it, the draw thread reads it */
static int s_fly_f3_was;
static int s_fly_captured;
static POINT s_fly_centre;
static LARGE_INTEGER s_fly_last;
static long s_fly_draws;                 /* draws the fly view replaced since it was turned on */

static int fly_view_cb(void* user, const float* vp, uint32_t clip_w, float* out, int scene)
{
    (void)user;
    if (clip_w < 640u) return 0;
    int r = 0;
    EnterCriticalSection(&s_fly_cs);
    if (s_fly_mode.on) {
        if (s_fly_mode.init) {   /* the first perspective draw after F3 gives the pose: the game's camera */
            double m[16];
            fly_view g;
            fly_load(vp, m);
            if (fly_decompose(m, &g)) {
                fly_pose_from_view(&s_fly_pose, &g);
                s_fly_mode.init = 0;
                fprintf(stderr, "[fly] pose from the game's camera (%s, target %u wide): eye %.2f %.2f %.2f yaw %.1f pitch %.1f\n",
                        scene ? "scene" : "draw", clip_w, g.eye[0], g.eye[1], g.eye[2], s_fly_pose.yaw, s_fly_pose.pitch);
            }
        }
        if (!s_fly_mode.init) r = fly_view_vp(&s_fly_pose, vp, out);
    }
    LeaveCriticalSection(&s_fly_cs);
    if (r && !scene) s_fly_draws++;
    return r;
}

static int fly_key(int vk) { return (GetAsyncKeyState(vk) & 0x8000) != 0; }

/* once per presented frame (present_guest_frame): F3 edge, cursor capture, the keys and the mouse */
static void fly_frame(void)
{
    if (s_fly_env < 0) {
        const char* e = getenv("MSPR_DEBUG_FLY");
        s_fly_env = e && e[0] == '1' && !e[1];
        if (s_fly_env) {
            InitializeCriticalSection(&s_fly_cs);
            fprintf(stderr, "[fly] MSPR_DEBUG_FLY=1: F3 in the game window toggles the debug free-fly camera\n");
        }
    }
    if (!s_fly_env) return;
    LARGE_INTEGER freq, now;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&now);
    const double dt = s_fly_last.QuadPart ? (double)(now.QuadPart - s_fly_last.QuadPart) / (double)freq.QuadPart : 0.0;
    s_fly_last = now;
    const int f3 = fly_key(VK_F3);
    const int focused = ct_focused();
    if (f3 && !s_fly_f3_was && focused) {
        EnterCriticalSection(&s_fly_cs);
        fly_toggle(&s_fly_mode);
        const int on = s_fly_mode.on;
        if (on) s_fly_draws = 0;
        LeaveCriticalSection(&s_fly_cs);
        HWND fg = GetForegroundWindow();
        RECT rc;
        if (on) {
            rsx_draw_set_view_override(fly_view_cb, NULL);
            if (fg && GetClientRect(fg, &rc)) {
                s_fly_centre.x = (rc.right - rc.left) / 2; s_fly_centre.y = (rc.bottom - rc.top) / 2;
                ClientToScreen(fg, &s_fly_centre);
                SetCursorPos(s_fly_centre.x, s_fly_centre.y);
                RECT clip = { s_fly_centre.x - 2, s_fly_centre.y - 2, s_fly_centre.x + 2, s_fly_centre.y + 2 };
                ClipCursor(&clip);
                s_fly_captured = 1;
            }
            ShowCursor(FALSE);
            fprintf(stderr, "[fly] on: the game is paused; W/S/A/D move, Shift fast, mouse looks, F3 returns\n");
        } else {
            rsx_draw_set_view_override(NULL, NULL);
            if (s_fly_captured) ClipCursor(NULL);
            s_fly_captured = 0;
            ShowCursor(TRUE);
            rsx_title_suffix[0] = 0;
            fprintf(stderr, "[fly] off: the game resumes (%ld draws flown)\n", s_fly_draws);
        }
    }
    s_fly_f3_was = f3;
    EnterCriticalSection(&s_fly_cs);
    const int moving = s_fly_mode.on && !s_fly_mode.init && focused;
    if (moving) {
        fly_input in;
        memset(&in, 0, sizeof in);
        in.fwd = fly_key('W') - fly_key('S');
        in.strafe = fly_key('D') - fly_key('A');
        in.up = fly_key(VK_SPACE) - fly_key(VK_CONTROL);
        in.fast = fly_key(VK_SHIFT);
        POINT p;
        if (s_fly_captured && GetCursorPos(&p)) {
            in.mx = p.x - s_fly_centre.x;
            in.my = p.y - s_fly_centre.y;
            SetCursorPos(s_fly_centre.x, s_fly_centre.y);
        }
        fly_move(&s_fly_pose, &in, dt, 1.0);
        snprintf(rsx_title_suffix, sizeof rsx_title_suffix, " | [fly] on: eye %.1f %.1f %.1f yaw %.0f pitch %.0f",
                 s_fly_pose.eye[0], s_fly_pose.eye[1], s_fly_pose.eye[2], s_fly_pose.yaw, s_fly_pose.pitch);
    }
    LeaveCriticalSection(&s_fly_cs);
}

/* The game's frame step: func_008CF1C0 (1.00 lift, ppu_recomp_004.cpp) receives the step in f1, and the hook at its
 * entry (launcher/pipeline/fly_pause_patch_lifted.py) replaces f1 with this result. While fly mode is on it is 0, so
 * the simulation step is skipped and the frames keep drawing; when F3 turns it off the game's own step passes again
 * and the sim continues from where it stopped. Unset MSPR_DEBUG_FLY: f1 unchanged. tests/test_fly_pause.c. */
extern "C" double mspr_fly_sim_step(double dt)
{
    return s_fly_env == 1 ? fly_sim_step(&s_fly_mode, dt) : dt;
}

/* MSPR_BENCH_AI=1 (race benchmark, off by default): the local human's car is driven by its own AIControls while the
 * race still counts it as the human. The lifted reads of the Competitor's controls kind (+0x1930) in the getter
 * func_00127BC8 and the switch at 0x0012A7D0 go through this (generated/analysis/perf60/tools/
 * bench_ai_patch_lifted.py, which passes the caller's return address); kind 1 (JoyStick) reads as 2 (AI) except
 * for the flyover-skip check, and a mapped read also sets the game's autopilot flag 0x20 at competitor+0x1698
 * (bench_ai.h). MSPR_BENCH=race turns it on too. Unset: the kind is returned unchanged and nothing is written.
 * bench_ai.h, tests/test_bench_ai.c. */
#include "bench_ai.h"
static volatile int s_bench_ai_env = -1;
static volatile int s_bench_ai_log = 0;   /* MSPR_BENCH_AI_LOG=1: each new (caller, kind) pair once, on stderr */
extern "C" uint32_t mspr_bench_ai_ctl(uint32_t kind, uint32_t lr, uint32_t comp)
{
    int on = s_bench_ai_env;
    if (on < 0) {
        const char* e = getenv("MSPR_BENCH_AI");
        on = (e && e[0] == '1' && e[1] == 0) ? 1 : 0;
        if (bench_mode() == BENCH_RACE) on = 1;   /* the race benchmark: the AI drives the player's car */
        const char* l = getenv("MSPR_BENCH_AI_LOG");
        s_bench_ai_log = l && l[0] == '1';
        s_bench_ai_env = on;
        if (on) fprintf(stderr, "[bench-ai] MSPR_BENCH_AI=1: the local human car is driven by its AIControls\n");
    }
    if (s_bench_ai_log) {
        static volatile LONG seen_n;
        static uint64_t seen[256];
        const uint64_t key = ((uint64_t)lr << 8) | (kind & 0xFFu);
        LONG n = seen_n, i;
        for (i = 0; i < n && i < 256; i++) if (seen[i] == key) break;
        if (i == n && n < 256) {
            seen[n] = key; seen_n = n + 1;
            fprintf(stderr, "[bench-ai] caller lr=%08X kind=%u -> %u (t=%llu ms)\n", lr, kind, bench_ai_ctl_kind(on, kind, lr),
                    (unsigned long long)GetTickCount64());
        }
    }
    if (s_bench_mode == BENCH_RACE) {   /* the race benchmark's events (bench_run.h) */
        if (lr == BENCH_LR_SKIP) bench_note(&s_bench_fly_qpc, "pre-race flyover (its skip check)");
        else if (bench_is_race_lr(lr)) bench_note(&s_bench_race_qpc, "race start (the race reads the player's controls)");
    }
    const uint32_t out = bench_ai_ctl_kind(on, kind, lr);
    if (out != kind && comp) {   /* the game's autopilot flag with it (bench_ai.h): func_0012A100(comp, 1) state */
        uint8_t* p = vm_base + (uint32_t)(comp + 0x1698u);
        const uint32_t f = ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
        const uint32_t nf = bench_ai_flags(on, kind, lr, f);
        if (nf != f) p[3] = (uint8_t)nf;   /* bit 0x20 lives in the low (last) byte of the big-endian word */
    }
    return out;
}

/* ---------------------------------------------------------------------------
 * Guest VM
 * -----------------------------------------------------------------------*/
#ifdef _WIN32
/* Demand-paging for the flat VM: reserve the whole 4 GB guest space, which
 * costs no commit, and commit each 64 KB page on first access. Every 32-bit
 * guest offset is then valid, so a garbage guest pointer reads zero instead of
 * killing the process. Faults outside the arena fall through untouched. */
static LONG WINAPI vm_commit_veh(EXCEPTION_POINTERS* ep)
{
    if (ep->ExceptionRecord->ExceptionCode == EXCEPTION_ACCESS_VIOLATION) {
        ULONG_PTR fault = ep->ExceptionRecord->ExceptionInformation[1];
        uintptr_t base  = (uintptr_t)vm_base;
        if (vm_base && fault >= base && fault < base + VM_SIZE) {
            void* page = (void*)(fault & ~(uintptr_t)0xFFFF);
            if (VirtualAlloc(page, 0x10000, MEM_COMMIT, PAGE_READWRITE))
                return EXCEPTION_CONTINUE_EXECUTION;
        }
    }
    return EXCEPTION_CONTINUE_SEARCH;
}
#endif

static bool alloc_guest_vm(void)
{
#ifdef _WIN32
    AddVectoredExceptionHandler(1, vm_commit_veh);
    /* T150 PS3_TEX_SNAPSHOT_WWATCH=1: the OS tracks writes to the arena (every
     * path: PPU/SPU stores, host memcpy, file reads), so the texture snapshot
     * can skip unchanged textures exactly. Unset: the reservation as before. */
    const char* ww = getenv("PS3_TEX_SNAPSHOT_WWATCH");
    const DWORD wwf = (ww && ww[0] == '1' && !ww[1]) ? MEM_WRITE_WATCH : 0;
    vm_base = (uint8_t*)VirtualAlloc(NULL, VM_SIZE, MEM_RESERVE | wwf, PAGE_READWRITE);
    ppu_vm_size = 0;              /* the whole space is backed; no OOB guard needed */
#else
    /* No vectored exception handlers off Windows, so the arena is committed up
     * front and lazily backed by the OS: only pages the title touches cost
     * anything. It stops below the 0xE0000000 mark, so ppu_vm_size arms the
     * loader's bounds check for what is left. */
    vm_base = (uint8_t*)calloc(1, 0xE0000000u);
    ppu_vm_size = 0xE0000000u;
#endif
    return vm_base != nullptr;
}

/* ---------------------------------------------------------------------------
 * Main
 * -----------------------------------------------------------------------*/
#if defined(PORT_SPU_AVX2)
#include "port_cpu.h"
#endif

static void harness_guest_caller(uint32_t opd, uint64_t a0, uint64_t a1,
                                 uint64_t a2, uint64_t a3, uint64_t a4,
                                 uint64_t a5, uint64_t a6, uint64_t a7)
{
    ppu_guest_call(opd, a0, a1, a2, a3, a4, a5, a6, a7);
}

int main(int argc, char** argv)
{
    if (argc < 2) {
        printf("usage: %s <PPU ELF>\n", argv[0]);
        return 2;
    }
    /* Settings, strongest first: the process environment (the test runner's), settings.ini beside the exe (the
     * in-game PC Settings pages and the launcher write it; docs/SETTINGS.md), motorstorm.cfg (NAME=value lines for
     * what settings.ini has no key for: paths, diagnostics), then the defaults below. settings.ini is read first,
     * so its choices are in the environment before the .cfg and the defaults look. */
    pcmenu_boot(argv[0]);
#ifdef _WIN32
    /* motorstorm.cfg beside the exe, one NAME=value per line, # for comments. A variable already set (in the
     * environment, or by settings.ini) wins; a variable settings.ini owns is skipped here. */
    {
        char dirbuf[MAX_PATH];
        const DWORD n = GetModuleFileNameA(NULL, dirbuf, sizeof dirbuf);
        char* slash = n ? strrchr(dirbuf, '\\') : NULL;
        if (slash) {
            strcpy(slash + 1, "motorstorm.cfg");
            if (FILE* f = fopen(dirbuf, "r")) {
                char line[512];
                while (fgets(line, sizeof line, f)) {
                    char* eq = strchr(line, '=');
                    if (!eq || line[0] == '#') continue;
                    *eq = 0;
                    char* val = eq + 1;
                    char* nl_ = strpbrk(val, "\r\n");
                    if (nl_) *nl_ = 0;
                    char* key = line;
                    while (*key == ' ') key++;
                    for (char* k = key + strlen(key); k > key && (k[-1] == ' ' || k[-1] == '\t'); ) *--k = 0;
                    if (*key && !getenv(key) && !pcmenu_owns_env(key)) _putenv_s(key, val);
                }
                fclose(f);
            }
        }
    }
    /* The settings every measured race run used (the Kk29xx runner arms, e.g. Kk2953), as defaults: without a
     * launcher that sets them, a played game ran none of the tested speed paths. Each applies only when the
     * variable is unset, so a launcher or the runner can still override it. Not here: diagnostics, paths, and
     * choices that belong to the player (RSX_FSR, RSX_HDR, RSX_RES_SCALE, RSX_TEX_PACK, RSX_RT_SHADOW). */
    {
        static const char* const k_defaults[][2] = {
            { "MSPR_PATCH", "drs,vfps,audiothread" },   /* dynamic resolution, variable frame rate, audio thread */
            { "PS3_SIM_PACE", "1" },
            { "PS3_SIM_PACE_HZ", "30" },     /* the original rate (Frame Rate setting: 30 default, 45 and up experimental); vfps is in the patch list above */
            { "MSPR_CAM_MODE", "0" },        /* 0 at the default 30 FPS; the choices above 30 set 1 (camera fix, shake held at 30 Hz) */
            { "MSPR_CAM_COCKPIT", "1" },     /* driver's-eye camera on by default; MSPR_CAM_COCKPIT=0 turns it off (mspr_cam_cockpit_init) */
            { "RSX_PRESENT_INTERVAL", "0" }, /* non-blocking, tear-free mailbox present (FIFO if the GPU has no mailbox); 1 = V-Sync */
            { "PS3_MAIN_CORE", "1" },
            { "PS3_ICALL_FAST", "1" },
            { "PS3_VM_STORE_FAST", "1" }, { "PS3_VM_STORE_INLINE", "1" },
            { "PS3_LWCOND_WAKE", "1:poll_ms=100:heavy_draws=200" },
            { "PS3_FRAME_CLOCK_KICK", "1" },
            { "RSX_VK_PRESENT_ASYNC", "1" },
            { "RSX_VK_ARENA_KEEP", "1" },
            { "RSX_VK_READBACK_SKIP", "1" },
            { "RSX_VK_STAGE_VRAM", "1" },   /* depth snapshots and partial depth clears stay in video memory: +30 %, GPU 18.2 -> 9.0 ms (perf60 Ksvr) */   /* no per-frame host copy of the presented frame unless shots/dump/hash need it: +5.6 %, 4/4 pairs (perf60 Krbs) */   /* oversized arena blocks reused, not freed each frame: +0.7 %, 4/4 BENCH-CFG pairs (perf60 Kakp) */   /* the walker stops waiting for the GPU at each present: +20 % fps BENCH-CFG (4/4 pairs), ~+25 % race (perf60 Kpas, Krpa); one frame more latency */   /* drain woken by the guest's dry reference polls: +1.4 % fps, 4 of 4 BENCH-CFG pairs (perf60 Kfck) */   /* stats_ms=1000 (a [lwc-wake] line a second) is opt-in */
            { "PS3_SPURS_EVENT_SCHED", "1" }, { "PS3_SPURS_EVENT_FALLBACK_MS", "4" }, { "PS3_SPURS_GUEST_MAXCONT", "1" },
            { "PS3_SPU_FP_CACHE", "1" }, { "PS3_SPU_MFC_FAST", "1" }, { "PS3_SPU_TASK_QUIET", "1" },
            { "PS3_SPU_WWS_AOT", "1" }, { "SPU_INTERP_UNLIFTED", "1" },
            { "PS3_TEX_SNAPSHOT", "1" }, { "PS3_TEX_SNAPSHOT_EPOCH", "1" }, { "PS3_TEX_SNAPSHOT_WWATCH", "1" },
            { "RSX_BIND_DEDUP", "1" }, { "RSX_FP_SCAN_MEMO", "1" }, { "RSX_FP_SPAN", "1" }, { "RSX_GPU_REINTERP", "1" },
            { "RSX_PIPE_MEMO", "1" }, { "RSX_POLY_OFFSET", "1" }, { "RSX_SHADER_CACHE", "3" }, { "RSX_SHADER_WINDOW", "1" },
            { "RSX_SRV_REUSE", "1" }, { "RSX_TEX_BUDGET_MB", "1024" }, { "RSX_TEX_CACHE", "1" }, { "RSX_TEX_SLOTS", "1024" },
            { "RSX_TEX_WWATCH", "1" }, { "RSX_VK_LAZY_SYNC", "1" }, { "RSX_VK_MEM_RECYCLE", "1" },
            { "RSX_VP_COMPACT", "1" }, { "RSX_VP_FAST_FETCH", "1" }, { "RSX_VP_INDEXED", "1" }, { "RSX_VS_MEMO", "1" },
            { "RSX_VTX_DENSE", "1" }, { "RSX_VTX_GPU", "1" }, { "RSX_ZSNAP_ON_WRITE", "1" },
            { "RSX_RT_READBACK", "1" }, { "RSX_RT_READBACK_ASYNC", "1" }, { "RSX_RT_READBACK_EAGER", "1" },
            { "RSX_TP_PRELOAD", "1" },
            /* world-fixed sun shadows (rsx_shadow_tiles.h), Original and Enhanced: a shadow depends only on the sun and the
             * casters, never on the camera (generated/analysis/shadowtiles/RESULTS.md, Kstf53). RSX_SHADOW_TILES=0 gives the
             * game's own camera-following cascades (testing only: no menu or launcher row). */
            { "RSX_SHADOW_TILES", "1" },   /* texture pack built at the first present; unset in the renderer = off, RSX_TP_PRELOAD=0 turns it off */
            /* the SPU interpreter hands back to lifted code inside relocatable WWS job modules (renderablejob ran
             * interpreted to the end of every job once it fell back): 31.8 -> 38.7 fps in a race A/B
             * (Kksr48/52 vs Kksr50/54, criticalpath60). PS3_SPU_INTERP_REJOIN_RELOC=0 turns it off. */
            { "PS3_SPU_INTERP_REJOIN_RELOC", "1" },
            /* the drain's resume check is relocation-aware too (rj60: 0 unwinds, 0 misses, state byte-identical to the interpreter) */
            { "PS3_SPU_DRAIN_RESUME_RELOC", "1" },
            /* shader cache beside the exe (<exe dir>\shader_cache): the first run fills it, later runs skip the compile.
             * Derived from the game's programs: never commit, ship or upload it. PS3RECOMP_SPIRV_CACHE=0 turns it off. */
            { "PS3RECOMP_SPIRV_CACHE", "auto" },
            /* the start-up shader replay translates on worker threads: cold cache 13 s -> 2 s, warm 1.7 s -> 0.3 s
             * (Kk3006/Kk3007). Either set to 0 turns it off (the replay is then one shader at a time). */
            { "RSX_SHADER_REPLAY_PARALLEL", "1" }, { "RSX_SHADER_GLSLANG_PARALLEL", "1" },
        };
        for (const auto& kv : k_defaults)
            if (!getenv(kv[0])) _putenv_s(kv[0], kv[1]);
    }
    /* MotorStorm's main thread polls its SPU jobs with usleep(200-250); the high-resolution timer wakes it about
     * 2x late. Default (unless set): a spin tail to the deadline for the main thread only, every other thread on
     * the timer (Kk2948 -> Kk2949: late sim steps 17% -> 12%). */
    if (!getenv("PS3_USLEEP_SPIN")) _putenv_s("PS3_USLEEP_SPIN", "2");
    if (!getenv("PS3_USLEEP_SPIN_MAIN_ONLY")) _putenv_s("PS3_USLEEP_SPIN_MAIN_ONLY", "1");
    /* MotorStorm's SPUs never build the RSX command stream (no resync has ever landed on an SPU block): the
     * per-DMA record of SPU pushbuffers is only a cost (cellGcmSys.c, PS3_GCM_SPU_PUSHBUF). */
    if (!getenv("PS3_GCM_SPU_PUSHBUF")) _putenv_s("PS3_GCM_SPU_PUSHBUF", "0");
    /* Persistent host threads for SPU task runs (spu_task_pool.h): without it every run creates and destroys a
     * thread with a 256 MB stack reservation. The pool never queues, so no run waits for a worker. Every
     * measured race run (Kk2xxx) already had it on. */
    if (!getenv("PS3_SPU_TASK_POOL")) _putenv_s("PS3_SPU_TASK_POOL", "1");
    /* Windows power throttling ("efficiency mode") off for the whole process unless PS3_POWER_THROTTLE=1: the
     * scheduler may otherwise put its threads on low clocks or efficiency cores when the window is not in front,
     * and ignore its 1 ms timer resolution when the window is hidden -- the usleep wake-ups above then stretch. */
    if (!getenv("PS3_POWER_THROTTLE") || getenv("PS3_POWER_THROTTLE")[0] != '1') {
        PROCESS_POWER_THROTTLING_STATE pt = {};
        pt.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION;
        pt.ControlMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED | PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION;
        pt.StateMask = 0;   /* controlled, and off */
        if (!SetProcessInformation(GetCurrentProcess(), ProcessPowerThrottling, &pt, sizeof pt))
            fprintf(stderr, "[power] SetProcessInformation(ProcessPowerThrottling) failed (%lu)\n", GetLastError());
    }
#endif
#if defined(PORT_SPU_AVX2)
    /* The lifted SPU sources were built with -mavx2 (PORT_SPU_AVX2): stop here
     * with a reason rather than fault on the first SPU AVX instruction. */
    if (!port_cpu_has_avx2()) {
        fprintf(stderr, "This build needs a CPU and OS with AVX2 enabled. Rebuild with -DPORT_SPU_AVX2=OFF.\n");
        return 3;
    }
#endif

#ifdef _WIN32
#pragma comment(lib, "winmm.lib")
    /* 1 ms timer resolution. The default granularity is about 15.6 ms, which
     * inflates every shorter wait the title makes and throttles the whole
     * thing. POSIX timers are already fine-grained. */
    timeBeginPeriod(1);
    setvbuf(stdout, NULL, _IONBF, 0);   /* unbuffered: do not lose prints on a kill */
    /* stdout/stderr through a memory queue and a writer thread (stdio_async.h, PS3_STDIO_ASYNC=0 turns it
     * off): a disk stall in a log write held the RSX present thread for 20-48 s (late Present() Timeouts). */
    stdio_async_start();
#endif

    printf("=== ps3recomp game runner ===\n");

    if (!alloc_guest_vm()) {
        fprintf(stderr, "ERROR: could not allocate the guest address space\n");
        return 1;
    }

    uint32_t entry = ppu_load_elf(argv[1]);
    if (!entry) {
        fprintf(stderr, "ERROR: could not load %s\n", argv[1]);
        return 1;
    }
#ifdef PORT_EXPECT_ENTRY_OPD
    /* The lifted code is one release's; running another release's ELF makes
     * every table and TOC lookup read the wrong data (the 1.00 build run on the
     * 1.03 EBOOT reads address 0 near 0x3BBC80). Refuse it before guest code runs. */
    if (entry != (uint32_t)(PORT_EXPECT_ENTRY_OPD)) {
        fprintf(stderr, "ERROR: %s is not the EBOOT.elf this build was lifted from: "
                "entry OPD 0x%08X, this build expects 0x%08X.\n",
                argv[1], entry, (uint32_t)(PORT_EXPECT_ENTRY_OPD));
        return 1;
    }
#endif
#ifdef _WIN32
    /* PS3_SAMPLE=<ms>: the guest sampling profiler (ppu_loader.cpp); unset, it returns at once.
     * Without this call the linker dropped it and PS3_SAMPLE did nothing in this port (Kk3067). */
    { extern void ps3_sampler_start(void); ps3_sampler_start(); }
#endif

    derive_vfs_root(argv[1]);
    isolate_hdd1(argv[0]);
    printf("[boot] VFS root: %s\n", ppu_vfs_root);

    ppu_recomp_register();   /* lifted function table -> address map */
    ps3_load_prx_modules();  /* this game's lifted system PRX, if it has any */
    ppu_hle_init();          /* firmware import NID -> HLE handlers */
    ppu_sysprx_register();   /* boot-critical CRT */
    ppu_fs_register();       /* cellFs over the game directory */
    dev_skip_intro();        /* PS3_DEV_SKIP_INTRO=1 only */
    mspr_patch_init();       /* MSPR_PATCH only */
    mspr_cam_cockpit_init(); /* MSPR_CAM_COCKPIT=1 only */
    pcmenu_init();          /* PC Settings page functions (used only by its overlay pages) */
    lan_play_init();        /* LAN play: threads and sockets start only when a page asks (Host, Join) */
    if (const char* lh = getenv("PS3_LAN_HOST"); lh && lh[0] == '1') {   /* test hook: host without the page */
        char st[200];
        lan_play_set_host(1);
        lan_play_status(st, sizeof st);
        printf("[lan] %s\n", st);
    }
    cellGcm_fifo_fast_ab = rsx_draw_engine_ab_phase;   /* read only with GCM_FIFO_FAST=ab */
    lv2_init_syscalls();     /* the lv2 syscall table */

    /* Install the guest-callback hook, then start the frame clock. It no-ops
     * until the title registers its vblank and flip handlers during init. */
    g_ps3_guest_caller = harness_guest_caller;
#ifdef _WIN32
    s_main_thread = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, GetCurrentThreadId());
    main_core_setup();
#endif
    CreateThread(NULL, 4u * 1024 * 1024, frame_clock, NULL, 0, NULL);

    printf("\n[boot] dispatching entry OPD 0x%08X (stack top 0x%08X)\n\n",
           entry, STACK_TOP);

    int rc = ppu_run(entry, STACK_TOP);
    printf("\n[boot] ppu_run returned %d (entry function unwound)\n", rc);

    /* A title that called sys_process_exit never reaches this line: that path
     * ends in the host exit(). Getting here means the entry function returned
     * instead, so hand back the status the guest published if it published
     * one. Returning a hardcoded 0 would report success for a run that never
     * got anywhere. */
    return g_sys_process_exit_called ? (int)g_sys_process_exit_code : 0;
}
