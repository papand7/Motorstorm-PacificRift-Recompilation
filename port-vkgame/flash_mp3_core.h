/* MP3 frame decoding for the MultiStream codec replacement (flash_mp3_hle.c)
 * and its offline replay test. Independent implementation on minimp3 (CC0,
 * third_party/minimp3); no firmware code or data.
 *
 * The decoder state lives in the caller's two state blocks (the guest's
 * per-channel buffers, which the game's mixer saves and restores with each
 * stream): nothing is kept on the host between frames, so a stream that the
 * mixer rewinds to an earlier saved state decodes from that state. An all-zero
 * channel-0 block is a new stream. */
#ifndef FLASH_MP3_CORE_H
#define FLASH_MP3_CORE_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FMP3_MAX_SAMPLES 1152
#define FMP3_BLOCK0_BYTES 3616u   /* used at the start of the channel-0 block */
#define FMP3_BLOCK1_BYTES 3072u   /* used at the start of the channel-1 block (stereo) */

/* Header at p[0..3]. Returns the frame length in bytes (with padding), or 0
 * if it is not a Layer III header with a fixed bitrate. channels: 1 or 2;
 * samples: per channel (1152 MPEG-1, 576 MPEG-2/2.5). */
int fmp3_frame_info(const uint8_t* p, int* channels, int* samples, int* hz);

/* Decode one whole frame of len bytes (fmp3_frame_info's length) with the
 * state in blk0 (and blk1 when channels == 2; may be NULL otherwise), and
 * store the new state there. Writes `channels` planes of `samples` signed
 * 16-bit big-endian samples, plane c at out + c * stride. The planes are zero
 * when the frame cannot be decoded (its bit reservoir reaches into data the
 * stream has not supplied). Returns 1 when audio was decoded, 0 when silence
 * was written. */
int fmp3_decode_frame(uint8_t* blk0, uint8_t* blk1, const uint8_t* frame, int len,
                      uint8_t* out, uint32_t stride, int channels, int samples);

#ifdef __cplusplus
}
#endif

#endif
