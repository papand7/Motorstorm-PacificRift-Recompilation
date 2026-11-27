/* Offline check of the MultiStream MP3 codec replacement (flash_mp3_core.c)
 * against calls of the original codec recorded with MSPR_FMP3_REPLAY (see
 * flash_mp3_hle.c for the record layout). The recording holds hashes of the
 * per-stream state blocks before and after each call; this test keys its own
 * state blocks by those hashes, so it restores exactly the state the game's
 * mixer restored (new streams, continuations and rewinds alike), decodes the
 * recorded frame and compares the PCM with the original's.
 *
 *   flash_mp3_replay <recording.bin> [--verbose]
 *
 * Prints the overall SNR, the worst calls and the call classes; exits 1 when
 * the SNR is under 60 dB. The recordings come from the user's own game run and
 * stay private. */
#include "../flash_mp3_core.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define REC_BYTES (128 + 2048 + 2 * 0x900)

typedef struct { uint64_t key; uint8_t* b; } slot;
typedef struct { slot* s; size_t cap; } map;

static uint8_t* map_get(map* m, uint64_t key, size_t bytes, int create)
{
    size_t i = (size_t)(key * 0x9E3779B97F4A7C15ull) & (m->cap - 1);
    for (;;) {
        if (m->s[i].b && m->s[i].key == key) return m->s[i].b;
        if (!m->s[i].b) {
            if (!create) return NULL;
            m->s[i].key = key;
            m->s[i].b = (uint8_t*)calloc(1, bytes);
            return m->s[i].b;
        }
        i = (i + 1) & (m->cap - 1);
    }
}

static int16_t be16(const uint8_t* p) { return (int16_t)((uint16_t)p[0] << 8 | p[1]); }

int main(int argc, char** argv)
{
    if (argc < 2) { fprintf(stderr, "usage: %s recording.bin [--verbose]\n", argv[0]); return 2; }
    const int verbose = argc > 2 && strcmp(argv[2], "--verbose") == 0;
    const long dump = argc > 3 && strcmp(argv[2], "--dump") == 0 ? atol(argv[3]) : -1;
    FILE* f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 2; }
    map m0 = {calloc(1u << 16, sizeof(slot)), 1u << 16}, m1 = {calloc(1u << 16, sizeof(slot)), 1u << 16};
    static uint8_t rec[REC_BYTES];
    uint8_t b0[FMP3_BLOCK0_BYTES], b1[FMP3_BLOCK1_BYTES], out[0x1000 + 0x900];
    double sig = 0, err = 0, sig_new = 0, err_new = 0;
    long n = 0, calls_bad = 0, nonmp3 = 0, silent = 0, restored_missing = 0, newstreams = 0, maxdiff_all = 0;
    long hist[6] = {0};   /* max |diff| per call: 0, 1, 2-3, 4-15, 16-255, >255 */
    while (fread(rec, 1, REC_BYTES, f) == REC_BYTES) {
        uint32_t h[32];
        memcpy(h, rec, 128);
        if (h[0] != 0x31524D46u) { fprintf(stderr, "bad record %ld\n", n); return 2; }
        const uint32_t ret = h[15], used = h[16], outb = h[17], zero = h[18];
        uint64_t h0b, h0a, h1b, h1a;
        memcpy(&h0b, &h[20], 8); memcpy(&h0a, &h[22], 8); memcpy(&h1b, &h[24], 8); memcpy(&h1a, &h[26], 8);
        const uint8_t* in = rec + 128;
        const uint8_t* ref = rec + 128 + 2048;
        int ch = 0, ns = 0, hz = 0;
        const int len = fmp3_frame_info(in, &ch, &ns, &hz);
        n++;
        if (!len || ret == 0 || ret == 0xFFFFFFFFu) { nonmp3++; continue; }
        if (used != (uint32_t)len || outb != (uint32_t)ns * 2u)
            fprintf(stderr, "call %u: original used %u out %u, replacement %d %d\n", h[1], used, outb, len, ns * 2);
        /* the state the mixer restored */
        if (zero) { memset(b0, 0, sizeof b0); newstreams++; }
        else {
            const uint8_t* s = map_get(&m0, h0b, sizeof b0, 0);
            if (s) memcpy(b0, s, sizeof b0); else { memset(b0, 0, sizeof b0); restored_missing++; }
        }
        if (ch == 2) {
            const uint8_t* s = map_get(&m1, h1b, sizeof b1, 0);
            if (s) memcpy(b1, s, sizeof b1); else memset(b1, 0, sizeof b1);
        }
        const int ok = fmp3_decode_frame(b0, ch == 2 ? b1 : NULL, in, len, out, 0x1000, ch, ns);
        if (!ok) silent++;
        memcpy(map_get(&m0, h0a, sizeof b0, 1), b0, sizeof b0);
        if (ch == 2) memcpy(map_get(&m1, h1a, sizeof b1, 1), b1, sizeof b1);
        if ((long)h[1] == dump) {
            FILE* o = fopen("fmr_dump.bin", "wb");
            if (o) { fwrite(ref, 1, 0x1200, o); fwrite(out, 1, 0x900, o); fwrite(out + 0x1000, 1, 0x900, o); fwrite(in, 1, 2048, o); fclose(o); }
        }
        long md = 0;
        double cs = 0, ce = 0;
        for (int c = 0; c < ch; c++)
            for (int i = 0; i < ns; i++) {
                const int a = be16(ref + c * 0x900 + 2 * i), b = be16(out + c * 0x1000 + 2 * i);
                const long d = labs((long)a - b);
                if (d > md) md = d;
                cs += (double)a * a;
                ce += (double)(a - b) * (a - b);
            }
        sig += cs; err += ce;
        if (zero) { sig_new += cs; err_new += ce; }
        hist[md == 0 ? 0 : md == 1 ? 1 : md < 4 ? 2 : md < 16 ? 3 : md < 256 ? 4 : 5]++;
        if (md > maxdiff_all) maxdiff_all = md;
        if (md > 16) {
            calls_bad++;
            if (verbose || calls_bad <= 10)
                printf("call %u lr=%05X hdr=%02X%02X%02X%02X new=%u ok=%d maxdiff=%ld frame snr=%.1f dB\n", h[1], h[2],
                       in[0], in[1], in[2], in[3], zero, ok, md, ce > 0 ? 10 * log10((cs + 1e-9) / ce) : 999.0);
        }
    }
    fclose(f);
    const double snr = err > 0 ? 10 * log10(sig / err) : 999.0;
    printf("calls %ld (non-decodable %ld), new streams %ld, unknown restored state %ld, silent outputs %ld\n",
           n, nonmp3, newstreams, restored_missing, silent);
    printf("max|diff| per call: 0:%ld 1:%ld 2-3:%ld 4-15:%ld 16-255:%ld >255:%ld (largest %ld)\n",
           hist[0], hist[1], hist[2], hist[3], hist[4], hist[5], maxdiff_all);
    printf("SNR all %.2f dB; first frames of new streams %.2f dB\n", snr,
           err_new > 0 ? 10 * log10(sig_new / err_new) : 999.0);
    return snr >= 60.0 ? 0 : 1;
}
