/* flash_mp3_core.c: header parsing, the state-block round trip, and (given an
 * MP3 file of whole Layer III frames) bit-identical output between one
 * continuous minimp3 decoder and decoding every frame from the packed state
 * blocks -- the way the game's mixer drives the replacement.
 *
 *   test_flash_mp3_core [frames.mp3 ...]
 * Without files only the built-in checks run (no game data needed). */
#include "../flash_mp3_core.c"   /* one TU: the reference decoder below is the same minimp3 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks;
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; } } while (0)

static int be16(const uint8_t* p) { return (int16_t)((uint16_t)p[0] << 8 | p[1]); }

static int check_file(const char* path)
{
    FILE* f = fopen(path, "rb");
    if (!f) { perror(path); return 1; }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t* d = malloc((size_t)n);
    if (!d || fread(d, 1, (size_t)n, f) != (size_t)n) { fclose(f); return 1; }
    fclose(f);
    static mp3dec_t ref;
    mp3dec_init(&ref);
    static uint8_t b0[FMP3_BLOCK0_BYTES], b1[FMP3_BLOCK1_BYTES], out[0x1000 + 0x900];
    memset(b0, 0, sizeof b0); memset(b1, 0, sizeof b1);
    long off = 0, frames = 0, diffs = 0;
    while (off + 4 <= n) {
        int ch, ns, hz;
        const int len = fmp3_frame_info(d + off, &ch, &ns, &hz);
        if (!len || off + len > n) break;
        int16_t pcm[MINIMP3_MAX_SAMPLES_PER_FRAME];
        mp3dec_frame_info_t info;
        const int rn = mp3dec_decode_frame(&ref, d + off, len, pcm, &info);
        const int ok = fmp3_decode_frame(b0, ch == 2 ? b1 : NULL, d + off, len, out, 0x1000, ch, ns);
        CHECK(ok == (rn == ns));
        for (int c = 0; c < ch; c++)
            for (int i = 0; i < ns; i++) {
                const int r = rn ? pcm[i * info.channels + (c < info.channels ? c : 0)] : 0;
                diffs += be16(out + c * 0x1000 + 2 * i) != r;
            }
        off += len;
        frames++;
    }
    free(d);
    printf("%s: %ld frames, %ld samples differ\n", path, frames, diffs);
    CHECK(frames > 0 && diffs == 0);
    return 0;
}

int main(int argc, char** argv)
{
    int ch, ns, hz;
    static const uint8_t h1[4] = {0xFF, 0xFA, 0x94, 0x60};   /* MPEG-1 L3, CRC, 128 kbps, 48 kHz, joint stereo */
    static const uint8_t h2[4] = {0xFF, 0xFA, 0x54, 0xC0};   /* 64 kbps, 48 kHz, mono */
    static const uint8_t h3[4] = {0xFF, 0xFB, 0x92, 0x00};   /* 128 kbps, 44.1 kHz, padded, stereo */
    static const uint8_t h4[4] = {0xFF, 0xF3, 0x84, 0xC0};   /* MPEG-2 L3, 64 kbps, 24 kHz, mono */
    CHECK(fmp3_frame_info(h1, &ch, &ns, &hz) == 384 && ch == 2 && ns == 1152 && hz == 48000);
    CHECK(fmp3_frame_info(h2, &ch, &ns, &hz) == 192 && ch == 1);
    CHECK(fmp3_frame_info(h3, &ch, &ns, &hz) == 418 && ch == 2 && hz == 44100);
    CHECK(fmp3_frame_info(h4, &ch, &ns, &hz) == 192 && ch == 1 && ns == 576 && hz == 24000);
    static const uint8_t bad[][4] = {{0xFF, 0xFA, 0x04, 0x60}, {0xFF, 0xFA, 0xF4, 0x60}, {0xFF, 0xFA, 0x9C, 0x60},
                                     {0xFF, 0xFC, 0x94, 0x60}, {0xFF, 0xEA, 0x94, 0x60}, {0xFE, 0xFA, 0x94, 0x60}};
    for (unsigned i = 0; i < sizeof bad / sizeof bad[0]; i++) CHECK(fmp3_frame_info(bad[i], &ch, &ns, &hz) == 0);
    /* a frame with empty side info decodes to silence and leaves a valid state */
    static uint8_t frame[384], b0[FMP3_BLOCK0_BYTES], b1[FMP3_BLOCK1_BYTES], out[0x1000 + 0x900];
    memcpy(frame, h1, 4);
    memset(b0, 0, sizeof b0);
    memset(out, 0x55, sizeof out);
    CHECK(fmp3_decode_frame(b0, b1, frame, 384, out, 0x1000, 2, 1152) == 1);
    CHECK(memcmp(b0, "FMP3", 4) == 0);
    for (int i = 0; i < 0x900; i++) CHECK(out[i] == 0 && out[0x1000 + i] == 0);
    /* foreign bytes in the block are a fresh state, not a crash */
    memset(b0, 0xA5, sizeof b0);
    CHECK(fmp3_decode_frame(b0, b1, frame, 384, out, 0x1000, 2, 1152) == 1);
    CHECK(memcmp(b0, "FMP3", 4) == 0);
    printf("built-in: %u checks PASS\n", checks);
    for (int i = 1; i < argc; i++)
        if (check_file(argv[i])) return 1;
    return 0;
}
