/* MP3 frame decoding for the MultiStream codec replacement. See flash_mp3_core.h. */
#define MINIMP3_IMPLEMENTATION
#include "third_party/minimp3/minimp3.h"
#include "flash_mp3_core.h"
#include <string.h>

/* State block layout (host byte order; only this file reads it):
 *   block 0: "FMP3", version, reserv, free_format_bytes, header[4], 12 zero
 *            bytes, mdct_overlap[0] (288 floats), the even entries of
 *            qmf_state (480 floats), reserv_buf (511 bytes)
 *   block 1: mdct_overlap[1], the odd entries of qmf_state
 * minimp3 keeps a mono stream's synthesis state in the even entries only (it
 * never updates the odd ones for one channel), so a mono stream needs block 0
 * alone; the mixer saves block 1 only for stereo streams. */
#define B0_OVL   32u
#define B0_QMF   (B0_OVL + 288u * 4u)
#define B0_RES   (B0_QMF + 480u * 4u)
#define B1_QMF   (288u * 4u)
#define FMP3_STATE_VERSION 1u

typedef char fmp3_layout_check0[(B0_RES + 511u <= FMP3_BLOCK0_BYTES) ? 1 : -1];
typedef char fmp3_layout_check1[(B1_QMF + 480u * 4u <= FMP3_BLOCK1_BYTES) ? 1 : -1];
typedef char fmp3_layout_check2[(sizeof(((mp3dec_t*)0)->qmf_state) == 960u * 4u) ? 1 : -1];

static void st_put32(uint8_t* p, uint32_t v) { memcpy(p, &v, 4); }
static uint32_t st_get32(const uint8_t* p) { uint32_t v; memcpy(&v, p, 4); return v; }

static void unpack(mp3dec_t* d, const uint8_t* b0, const uint8_t* b1)
{
    memset(d, 0, sizeof *d);
    if (memcmp(b0, "FMP3", 4) != 0 || st_get32(b0 + 4) != FMP3_STATE_VERSION)
        return;                                   /* a new stream (zero block) or foreign bytes: fresh state */
    d->reserv = (int)st_get32(b0 + 8);
    d->free_format_bytes = (int)st_get32(b0 + 12);
    if (d->reserv < 0 || d->reserv > (int)sizeof d->reserv_buf) d->reserv = 0;
    memcpy(d->header, b0 + 16, 4);
    memcpy(d->mdct_overlap[0], b0 + B0_OVL, 288u * 4u);
    memcpy(d->reserv_buf, b0 + B0_RES, sizeof d->reserv_buf);
    for (unsigned i = 0; i < 480u; i++) memcpy(&d->qmf_state[2 * i], b0 + B0_QMF + 4u * i, 4);
    if (b1) {
        memcpy(d->mdct_overlap[1], b1, 288u * 4u);
        for (unsigned i = 0; i < 480u; i++) memcpy(&d->qmf_state[2 * i + 1], b1 + B1_QMF + 4u * i, 4);
    }
}

static void pack(const mp3dec_t* d, uint8_t* b0, uint8_t* b1)
{
    memcpy(b0, "FMP3", 4);
    st_put32(b0 + 4, FMP3_STATE_VERSION);
    st_put32(b0 + 8, (uint32_t)d->reserv);
    st_put32(b0 + 12, (uint32_t)d->free_format_bytes);
    memcpy(b0 + 16, d->header, 4);
    memset(b0 + 20, 0, B0_OVL - 20u);
    memcpy(b0 + B0_OVL, d->mdct_overlap[0], 288u * 4u);
    for (unsigned i = 0; i < 480u; i++) memcpy(b0 + B0_QMF + 4u * i, &d->qmf_state[2 * i], 4);
    memcpy(b0 + B0_RES, d->reserv_buf, sizeof d->reserv_buf);
    b0[B0_RES + 511u] = 0;
    if (b1) {
        memcpy(b1, d->mdct_overlap[1], 288u * 4u);
        for (unsigned i = 0; i < 480u; i++) memcpy(b1 + B1_QMF + 4u * i, &d->qmf_state[2 * i + 1], 4);
    }
}

int fmp3_frame_info(const uint8_t* h, int* channels, int* samples, int* hz)
{
    static const uint16_t kbps[2][15] = {
        {0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160},      /* MPEG-2/2.5 L3 */
        {0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320},  /* MPEG-1 L3 */
    };
    static const uint16_t rates[3] = {44100, 48000, 32000};
    if (h[0] != 0xFF || (h[1] & 0xE0) != 0xE0) return 0;
    const int ver = (h[1] >> 3) & 3;          /* 3: MPEG-1, 2: MPEG-2, 0: MPEG-2.5 */
    const int layer = (h[1] >> 1) & 3;        /* 1: Layer III */
    const int bri = h[2] >> 4, sri = (h[2] >> 2) & 3, pad = (h[2] >> 1) & 1;
    if (ver == 1 || layer != 1 || bri == 0 || bri == 15 || sri == 3) return 0;
    const int mpeg1 = ver == 3;
    const int rate = rates[sri] >> (mpeg1 ? 0 : ver == 2 ? 1 : 2);
    const int n = mpeg1 ? 1152 : 576;
    if (channels) *channels = ((h[3] >> 6) & 3) == 3 ? 1 : 2;
    if (samples) *samples = n;
    if (hz) *hz = rate;
    return (int)(n / 8 * 1000u * kbps[mpeg1][bri] / (unsigned)rate) + pad;
}

static void put_be16(uint8_t* p, int16_t v) { p[0] = (uint8_t)((uint16_t)v >> 8); p[1] = (uint8_t)v; }

int fmp3_decode_frame(uint8_t* blk0, uint8_t* blk1, const uint8_t* frame, int len,
                      uint8_t* out, uint32_t stride, int channels, int samples)
{
    static _Thread_local mp3dec_t dec;
    static _Thread_local int16_t pcm[MINIMP3_MAX_SAMPLES_PER_FRAME];
    mp3dec_frame_info_t info;
    memset(&info, 0, sizeof info);
    uint8_t* b1 = channels == 2 ? blk1 : NULL;
    unpack(&dec, blk0, b1);
    const int n = mp3dec_decode_frame(&dec, frame, len, pcm, &info);
    pack(&dec, blk0, b1);
    const int ok = n == samples && info.channels >= 1;
    for (int c = 0; c < channels; c++) {
        uint8_t* o = out + (size_t)c * stride;
        if (!ok) { memset(o, 0, (size_t)samples * 2); continue; }
        const int src_ch = c < info.channels ? c : 0;
        for (int i = 0; i < samples; i++)
            put_be16(o + 2 * i, pcm[i * info.channels + src_ch]);
    }
    return ok;
}
