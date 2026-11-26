/* test_bench_ai.c: MSPR_BENCH_AI controls-kind mapping (bench_ai.h bench_ai_ctl_kind).
 *   - off: every kind (0..5, above 5, all 32-bit values sampled) passes unchanged, bit for bit;
 *   - on: only kind 1 (JoyStick, the local human) becomes kind 2 (AI); 0, 2..5, Limbo and out-of-range stay;
 *   - on: the flyover-skip caller (return address 0x000327A8) still sees kind 1, every other caller sees 2;
 *   - flags: the autopilot bit 0x20 is added exactly when a read is mapped, other bits never change.
 * Build: cl /nologo /W4 tests\test_bench_ai.c /I. && test_bench_ai.exe (or gcc -I. tests/test_bench_ai.c). */
#include "bench_ai.h"
#include <assert.h>
#include <stdio.h>

static const uint32_t LRS[] = { 0x00214678u, 0x00214CE0u, 0x007DD0D4u, 0x007DD10Cu, 0x007DD144u, 0x000316BCu, 0u,
                                 0x000327A4u, 0x000327ACu, 0xFFFFFFFFu };

int main(void)
{
    uint32_t k, i;
    const uint32_t nl = sizeof LRS / sizeof LRS[0];
    for (i = 0; i < nl; i++) {
        for (k = 0; k < 64; k++) assert(bench_ai_ctl_kind(0, k, LRS[i]) == k);
        for (k = 0xFFFFFF00u; k != 0; k++) assert(bench_ai_ctl_kind(0, k, LRS[i]) == k);
        assert(bench_ai_ctl_kind(1, 1, LRS[i]) == 2);
        for (k = 0; k < 64; k++) if (k != 1) assert(bench_ai_ctl_kind(1, k, LRS[i]) == k);
        for (k = 0xFFFFFF00u; k != 0; k++) assert(bench_ai_ctl_kind(1, k, LRS[i]) == k);
        assert(bench_ai_ctl_kind(1, 0x101u, LRS[i]) == 0x101u);   /* only the exact kind, not its low byte */
    }
    for (k = 0; k < 64; k++) {   /* the skip caller: unchanged on and off */
        assert(bench_ai_ctl_kind(1, k, BENCH_AI_LR_SKIP) == k);
        assert(bench_ai_ctl_kind(0, k, BENCH_AI_LR_SKIP) == k);
    }
    printf("test_bench_ai: ok\n");
    return 0;
}
