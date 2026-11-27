/* MotorStorm: Pacific Rift -- MultiStream's MP3 codec without PS3 firmware.
 *
 * MultiStream (the game's own audio engine: a PPU update thread plus an SPU
 * mixer task, lifted image 283218738) decodes its MP3 streams with a codec
 * the PS3 system software provides, /dev_flash/sys/external/flashMP3.pic.
 * Without that file the PPU logs "mp3 failed to load MP3 codec", the mixer
 * branches into an empty local store and every sound in the game is lost.
 * This file replaces the codec with an independent implementation, so no
 * firmware file is needed. Nothing here is taken from the firmware codec.
 *
 * How the game uses the codec (observed; notes and captures in the private
 * generated/analysis/audio_fw):
 *   PPU: cellFsOpen + lseek + read of the whole file into a buffer, then a
 *     small parser takes the SPU ELF's section headers (machine 0x17; the
 *     allocated sections' lowest file offset, end, lowest address; e_entry)
 *     into a descriptor the mixer reads.
 *   SPU mixer: DMAs the image to local store (LS address = 0x19780 + section
 *     address) whenever it needs the codec (the LS area is shared with its
 *     other decoders) and calls the entry with
 *       r3  LS address of one MP3 frame (the frame header first)
 *       r4  LS address of a word: bytes consumed (out)
 *       r5  LS address of a word: output bytes per channel (out)
 *       r6  LS work area (0x5800 bytes); the PCM goes to r6 + 0x900
 *       r7..r11  LS buffers holding the stream's decoder state; the mixer
 *           saves and restores them per stream around every call (channel 0
 *           block r9 .. r9 + 0x1380, channel 1 block r10 .. r10 + 0x1380)
 *       r12 LS address of a word, a ring position that advances with every
 *           frame: (value + 12) & 15
 *     and expects back r3 = LS address of the PCM (r6 + 0x900; 0 means no
 *     frame, -1 an error), *r4 = the frame length, *r5 = 0x900, and the PCM as
 *     1152 signed 16-bit big-endian samples per channel, channel c at
 *     r3 + c * 0x1000. One MPEG-1 Layer III frame per call.
 *
 * The replacement:
 *   - serves a small self-made SPU ELF for the codec path when the firmware
 *     file is missing (ps3emu/vfs_builtin.h). Its only section, at address
 *     0x80, is a stop instruction and a signature; the mixer loads it to LS
 *     0x19800 and calls LS 0x19800;
 *   - answers that call on the host (spu_branch_hook.h): decodes the frame
 *     with minimp3 (flash_mp3_core.c) and writes the outputs above. The
 *     decoder state is kept in the stream's own state blocks (channel 0 at r9,
 *     channel 1 at r10 for stereo), which the mixer saves and restores with
 *     the stream -- also when it goes back to an earlier saved state and
 *     decodes a frame again. An all-zero block is a new stream. Nothing is
 *     kept on the host between calls.
 *
 *   MSPR_FMP3_HLE=0   off: no stand-in, no hook (the firmware file is needed).
 *   MSPR_FMP3_HLE=1   default: the stand-in replaces a missing firmware file.
 *   MSPR_FMP3_HLE=2   the stand-in is used even if the firmware file exists.
 *   MSPR_FMP3_STATS=s print a summary every s seconds.
 *   MSPR_FMP3_REPLAY=<file>  (with the firmware codec) record every codec call
 *       compactly for tests/flash_mp3_replay.c: the frame, the output, hashes
 *       of the state blocks. MSPR_FMP3_REPLAY_MAX calls (default 6000).
 *
 * Game-specific; the generic pieces are runtime/spu/spu_branch_hook.h and
 * include/ps3emu/vfs_builtin.h. */
#include "spu_context.h"
#include "spu_helpers.h"
#include "spu_branch_hook.h"
#include "ps3emu/vfs_builtin.h"
#include "flash_mp3_core.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#define FMP3_MIXER_IMAGE   283218738
#define FMP3_STANDIN_ENTRY 0x19800u   /* LS 0x19780 + the stand-in's section address 0x80 */
#define FMP3_FW_ENTRY      0x20C20u   /* LS 0x19780 + the firmware file's e_entry (replay capture) */
#define FMP3_PCM_OFFSET    0x900u
#define FMP3_CH_STRIDE     0x1000u
#define FMP3_STATE_BLOCK   0x1380u

static const char kCodecPath[] = "/dev_flash/sys/external/flashMP3.pic";
static const uint8_t kSig[12] = {'M','S','P','R','F','M','P','3','H','L','E','1'};

/* ---- the stand-in file: a 440-byte SPU ELF written for this project ---- */
static uint8_t s_standin[0x1B8];

static void put32(uint8_t* p, uint32_t v) { p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16); p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v; }
static void put16(uint8_t* p, uint32_t v) { p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v; }
static uint32_t get32(const uint8_t* p) { return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3]; }

static void build_standin(void)
{
    uint8_t* e = s_standin;
    memset(e, 0, sizeof s_standin);
    e[0] = 0x7F; e[1] = 'E'; e[2] = 'L'; e[3] = 'F';
    e[4] = 1; e[5] = 2; e[6] = 1;                  /* ELF32, big-endian, version 1 */
    put16(e + 0x10, 2);                            /* ET_EXEC */
    put16(e + 0x12, 0x17);                         /* EM_SPU */
    put32(e + 0x14, 1);
    put32(e + 0x18, 0x80);                         /* e_entry */
    put32(e + 0x1C, 0x34);                         /* e_phoff */
    put32(e + 0x20, 0x140);                        /* e_shoff */
    put16(e + 0x28, 0x34); put16(e + 0x2A, 0x20); put16(e + 0x2C, 1);
    put16(e + 0x2E, 0x28); put16(e + 0x30, 3); put16(e + 0x32, 2);
    uint8_t* ph = e + 0x34;                        /* PT_LOAD, R+X */
    put32(ph + 0x00, 1); put32(ph + 0x04, 0x100); put32(ph + 0x08, 0x80); put32(ph + 0x0C, 0x80);
    put32(ph + 0x10, 0x20); put32(ph + 0x14, 0x20); put32(ph + 0x18, 5); put32(ph + 0x1C, 0x80);
    uint8_t* text = e + 0x100;                     /* stop 0x3FFF, then the signature */
    put32(text, 0x00003FFFu);
    memcpy(text + 4, kSig, sizeof kSig);
    memcpy(e + 0x120, "\0.text\0.shstrtab", 17);
    uint8_t* sh = e + 0x140 + 0x28;                /* [1] .text: PROGBITS, ALLOC|EXECINSTR */
    put32(sh + 0x00, 1); put32(sh + 0x04, 1); put32(sh + 0x08, 6); put32(sh + 0x0C, 0x80);
    put32(sh + 0x10, 0x100); put32(sh + 0x14, 0x20); put32(sh + 0x20, 16);
    sh += 0x28;                                    /* [2] .shstrtab */
    put32(sh + 0x00, 7); put32(sh + 0x04, 3); put32(sh + 0x10, 0x120); put32(sh + 0x14, 17); put32(sh + 0x20, 1);
}

typedef struct {
    volatile long calls, decoded, silent, errors, nosync, fresh;
    volatile long long ns;
} fmp3_stats;
static fmp3_stats s_st;
static int s_stats_s;

static uint64_t now_ns(void)
{
    LARGE_INTEGER f, c;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return (uint64_t)((double)c.QuadPart * 1e9 / (double)f.QuadPart);
}

static void maybe_print_stats(void)
{
    if (s_stats_s <= 0) return;
    static volatile long long s_next;
    const long long t = (long long)(now_ns() / 1000000000ull);
    if (t < s_next) return;
    if (s_next == 0) { s_next = t + s_stats_s; return; }
    s_next = t + s_stats_s;
    fprintf(stderr, "[fmp3] calls=%ld decoded=%ld silent=%ld errors=%ld nosync=%ld new streams=%ld avg=%.1f us\n",
            s_st.calls, s_st.decoded, s_st.silent, s_st.errors, s_st.nosync, s_st.fresh,
            s_st.calls ? (double)s_st.ns / 1000.0 / (double)s_st.calls : 0.0);
}

static int ls_ok(uint32_t a, uint32_t n) { return a < SPU_LS_SIZE && n <= SPU_LS_SIZE - a; }

static int fmp3_hle_hook(spu_context* ctx, void* user)
{
    (void)user;
    uint8_t* ls = ctx->ls;
    if (memcmp(ls + FMP3_STANDIN_ENTRY + 4, kSig, sizeof kSig) != 0)
        return 0;                         /* not the stand-in: ordinary dispatch */
    const uint64_t t0 = now_ns();
    const uint32_t in = ctx->gpr[3]._u32[0] & SPU_LS_MASK, p_used = ctx->gpr[4]._u32[0] & SPU_LS_MASK,
                   p_out = ctx->gpr[5]._u32[0] & SPU_LS_MASK, work = ctx->gpr[6]._u32[0] & SPU_LS_MASK,
                   blk0 = ctx->gpr[9]._u32[0] & SPU_LS_MASK, blk1 = ctx->gpr[10]._u32[0] & SPU_LS_MASK,
                   p_ring = ctx->gpr[12]._u32[0] & SPU_LS_MASK;
    const uint32_t pcm = work + FMP3_PCM_OFFSET;
    uint32_t ret = 0xFFFFFFFFu, used = 0, outb = 0;
    InterlockedIncrement(&s_st.calls);
    int ch = 0, ns = 0, hz = 0;
    const int len = ls_ok(in, 4) ? fmp3_frame_info(ls + in, &ch, &ns, &hz) : 0;
    if (!ls_ok(p_used, 4) || !ls_ok(p_out, 4) || !ls_ok(p_ring, 4) ||
        !ls_ok(blk0, FMP3_BLOCK0_BYTES) || !ls_ok(blk1, FMP3_BLOCK1_BYTES) ||
        !ls_ok(pcm, FMP3_CH_STRIDE + 2 * FMP3_MAX_SAMPLES)) {
        InterlockedIncrement(&s_st.errors);
    } else if (!len || !ls_ok(in, (uint32_t)len)) {
        InterlockedIncrement(&s_st.nosync);       /* no frame here: the error return, nothing written */
    } else {
        if (memcmp(ls + blk0, "FMP3", 4) != 0) InterlockedIncrement(&s_st.fresh);
        const int ok = fmp3_decode_frame(ls + blk0, ls + blk1, ls + in, len, ls + pcm, FMP3_CH_STRIDE, ch, ns);
        InterlockedIncrement(ok ? &s_st.decoded : &s_st.silent);
        used = (uint32_t)len;
        outb = (uint32_t)ns * 2u;
        ret = pcm;
        put32(ls + p_ring, (get32(ls + p_ring) + 12u) & 15u);
    }
    if (ls_ok(p_used, 4)) put32(ls + p_used, used);
    if (ls_ok(p_out, 4)) put32(ls + p_out, outb);
    ctx->gpr[3] = spu_make_preferred_u32(ret);
    InterlockedExchangeAdd64(&s_st.ns, (long long)(now_ns() - t0));
    maybe_print_stats();
    return 1;
}

/* ---- replay capture of the firmware codec (MSPR_FMP3_REPLAY) ---- */
static FILE* s_rep;
static long s_rep_max = 6000;
static volatile long s_rep_n;

static uint64_t fnv64(const uint8_t* p, uint32_t n)
{
    uint64_t h = 1469598103934665603ull;
    for (uint32_t i = 0; i < n; i++) { h ^= p[i]; h *= 1099511628211ull; }
    return h;
}

/* Record layout (little-endian): magic 'FMR1', call index, lr, r3..r12, ring
 * before/after, return, *r4, *r5, flags (bit 0: channel-0 block all zero
 * before), 4 x fnv64 (ch0 before/after, ch1 before/after), then 2048 input
 * bytes from r3 and 2 x 0x900 output bytes (ret, ret + 0x1000). */
static int fmp3_replay_hook(spu_context* ctx, void* user)
{
    (void)user;
    uint8_t* ls = ctx->ls;
    uint32_t r[13];
    for (int i = 0; i < 13; i++) r[i] = ctx->gpr[i]._u32[0];
    const uint32_t lr = r[0] & SPU_LS_MASK, b0 = r[9] & SPU_LS_MASK, b1 = r[10] & SPU_LS_MASK,
                   ring = r[12] & SPU_LS_MASK, in = r[3] & SPU_LS_MASK;
    if (!ls_ok(b0, FMP3_STATE_BLOCK) || !ls_ok(b1, FMP3_STATE_BLOCK) || !ls_ok(ring, 4) || !ls_ok(in, 4))
        return 0;
    uint32_t rec[32];
    memset(rec, 0, sizeof rec);
    rec[0] = 0x31524D46u;
    rec[1] = (uint32_t)s_rep_n;
    rec[2] = lr;
    for (int i = 3; i <= 12; i++) rec[i] = r[i];
    rec[13] = get32(ls + ring);
    int zero = 1;
    for (uint32_t i = 0; i < FMP3_STATE_BLOCK && zero; i++) zero = ls[b0 + i] == 0;
    const uint64_t h0b = fnv64(ls + b0, FMP3_STATE_BLOCK), h1b = fnv64(ls + b1, FMP3_STATE_BLOCK);
    uint8_t input[2048];
    memset(input, 0, sizeof input);
    memcpy(input, ls + in, SPU_LS_SIZE - in < sizeof input ? SPU_LS_SIZE - in : sizeof input);
    spu_call_guest(ctx, ctx->pc, lr);
    const uint32_t ret = ctx->gpr[3]._u32[0];
    rec[14] = get32(ls + ring);
    rec[15] = ret;
    rec[16] = ls_ok(r[4] & SPU_LS_MASK, 4) ? get32(ls + (r[4] & SPU_LS_MASK)) : 0;
    rec[17] = ls_ok(r[5] & SPU_LS_MASK, 4) ? get32(ls + (r[5] & SPU_LS_MASK)) : 0;
    rec[18] = (uint32_t)zero;
    const uint64_t h0a = fnv64(ls + b0, FMP3_STATE_BLOCK), h1a = fnv64(ls + b1, FMP3_STATE_BLOCK);
    memcpy(&rec[20], &h0b, 8); memcpy(&rec[22], &h0a, 8); memcpy(&rec[24], &h1b, 8); memcpy(&rec[26], &h1a, 8);
    uint8_t out[2 * 0x900];
    memset(out, 0, sizeof out);
    const uint32_t ro = ret & SPU_LS_MASK;
    if (ret != 0 && ret != 0xFFFFFFFFu && ls_ok(ro, FMP3_CH_STRIDE + 0x900)) {
        memcpy(out, ls + ro, 0x900);
        memcpy(out + 0x900, ls + ro + FMP3_CH_STRIDE, 0x900);
    }
    if (s_rep && s_rep_n < s_rep_max) {
        fwrite(rec, 4, 32, s_rep);
        fwrite(input, 1, sizeof input, s_rep);
        fwrite(out, 1, sizeof out, s_rep);
        if (++s_rep_n == s_rep_max) { fclose(s_rep); s_rep = NULL; fprintf(stderr, "[fmp3] replay capture complete (%ld calls)\n", s_rep_max); }
    }
    return 1;
}

__attribute__((constructor)) static void mspr_fmp3_init(void)
{
    const char* e = getenv("MSPR_FMP3_REPLAY");
    if (e && *e) {
        s_rep = fopen(e, "wb");
        const char* m = getenv("MSPR_FMP3_REPLAY_MAX");
        if (m) s_rep_max = atol(m);
        if (s_rep) {
            spu_branch_hook_add(FMP3_MIXER_IMAGE, FMP3_FW_ENTRY, fmp3_replay_hook, NULL);
            fprintf(stderr, "[fmp3] recording firmware codec calls to %s (max %ld)\n", e, s_rep_max);
        }
    }
    e = getenv("MSPR_FMP3_HLE");
    const int mode = e && *e ? atoi(e) : 1;
    if ((e = getenv("MSPR_FMP3_STATS"))) s_stats_s = atoi(e);
    if (mode <= 0) {
        fprintf(stderr, "[fmp3] MultiStream MP3 codec replacement off (MSPR_FMP3_HLE=0): the firmware file is needed\n");
        return;
    }
    build_standin();
    ps3_vfs_add_builtin(kCodecPath, s_standin, (uint32_t)sizeof s_standin, mode >= 2);
    spu_branch_hook_add(FMP3_MIXER_IMAGE, FMP3_STANDIN_ENTRY, fmp3_hle_hook, NULL);
    fprintf(stderr, "[fmp3] MultiStream MP3 codec: built-in replacement %s (MSPR_FMP3_HLE=0 off)\n",
            mode >= 2 ? "always" : "when the firmware file is missing");
}
