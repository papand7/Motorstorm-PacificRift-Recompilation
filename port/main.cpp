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
#include "ps3emu/pad_trigger.h"     /* PS3_DEV_SKIP_INTRO: one CROSS press during the intro */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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
#  define rsx_backend_init    rsx_d3d12_backend_init
#  define rsx_backend_present rsx_d3d12_backend_present
#  define rsx_backend_pump    rsx_d3d12_backend_pump_messages
#  define RSX_BACKEND_NAME    "D3D12"
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

static void present_guest_frame(void)
{
    rsx_backend_present();
    /* This thread increments and guest threads read, so interlocked rather
     * than a volatile ++, which on arm64 is neither atomic nor a fence. */
    InterlockedIncrement(&g_frames_presented);
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

static DWORD WINAPI frame_clock(LPVOID)
{
    const char* title = getenv("PS3_TITLE");
    if (!title || !*title) title = "ps3recomp";

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
    const char* kick_env = getenv("PS3_FRAME_CLOCK_KICK");
    const int kick = kick_env && kick_env[0] == '1' && !kick_env[1];
    if (kick) fprintf(stderr, "[frame-clock] PS3_FRAME_CLOCK_KICK=1: idle wait woken by FIFO kicks
");

    for (;;) {
        fcw_mark(FCW_SLEEP);
        if (kick) cellGcm_fifo_kick_wait(4);
        else      Sleep(4);

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
    vm_base = (uint8_t*)VirtualAlloc(NULL, VM_SIZE, MEM_RESERVE, PAGE_READWRITE);
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

    derive_vfs_root(argv[1]);
    isolate_hdd1(argv[0]);
    printf("[boot] VFS root: %s\n", ppu_vfs_root);

    ppu_recomp_register();   /* lifted function table -> address map */
    ps3_load_prx_modules();  /* this game's lifted system PRX, if it has any */
    ppu_hle_init();          /* firmware import NID -> HLE handlers */
    ppu_sysprx_register();   /* boot-critical CRT */
    ppu_fs_register();       /* cellFs over the game directory */
    dev_skip_intro();        /* PS3_DEV_SKIP_INTRO=1 only */
    lv2_init_syscalls();     /* the lv2 syscall table */

    /* Install the guest-callback hook, then start the frame clock. It no-ops
     * until the title registers its vblank and flip handlers during init. */
    g_ps3_guest_caller = harness_guest_caller;
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
