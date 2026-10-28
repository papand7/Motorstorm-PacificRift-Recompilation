// Isolated PS3 firmware behavior probe. Build locally with PSL1GHT; never ship
// the resulting SELF or firmware-derived captures with a public release.
#include <malloc.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <ppu-types.h>
#include <spurs/spurs.h>
#include <sys/process.h>
#include <sys/spu.h>
#include <sys/systime.h>
#include <sys/thread.h>

// PSL1GHT supplies these cellSpurs import NIDs but omits their declarations.
// The arguments follow the public RPCS3 interface declarations. The taskset
// itself is initialized by firmware; this probe never writes its internals.
extern int spursCreateTaskset(Spurs *, void *, uint64_t, const uint8_t[8], unsigned);
extern int spursShutdownTaskset(void *);
extern int spursJoinTaskset(void *);
extern int spursLFQueueInitialize(void *, void *, void *, unsigned, unsigned, unsigned);
extern int spursLFQueuePushBody(void *, const void *, unsigned);
extern int spursLFQueuePopBody(void *, void *, unsigned);
extern int spursLFQueueAttachLv2EventQueue(void *);
extern int spursLFQueueDetachLv2EventQueue(void *);
#ifdef TEST_SPU_TASK
#include "spu_bin.h"
extern int spursCreateTask(void *, unsigned *, const void *, void *, unsigned,
                           const void *, const void *);
#ifdef TEST_DIRECT_TASK_SIGNAL
extern int spursSendSignal(void *, unsigned);
#endif
static uint8_t spu_marker[32] __attribute__((aligned(16)));
static uint64_t task_args[2] __attribute__((aligned(16)));
#ifdef TEST_SPU_CONTEXT
/* Diagnostic over-allocation: a full 256 KiB LS image plus register save
 * metadata may exceed 0x40000 even though task creation accepts that size. */
static uint8_t task_context[0x41000] __attribute__((aligned(128)));
#ifdef TEST_SPU_LS_PATTERN
/* Diagnostic input only. Firmware task creation validates the pattern. */
static uint64_t task_ls_pattern[2] __attribute__((aligned(16))) = {
    0x0000000000000000ULL, 0x0000000000000001ULL
};
#endif
#endif
#endif

SYS_PROCESS_PARAM(1001, 0x10000);

static uint8_t taskset_storage[0x10000] __attribute__((aligned(128)));
static uint8_t queue_storage[128] __attribute__((aligned(128)));
static uint8_t ring_storage[4 * 32] __attribute__((aligned(128)));
static uint8_t item[32] __attribute__((aligned(16)));

#ifdef TEST_PPU_WAITER
static volatile int waiter_done;
static uint8_t waiter_item[32] __attribute__((aligned(16)));
static void ppu_waiter(void *unused)
{
    (void)unused;
    int result = spursLFQueuePopBody(queue_storage, waiter_item, 3);
    printf("REF ppu_waiter_pop=%08x\n", (unsigned)result);
    waiter_done = 1;
    sysThreadExit((uint64_t)(unsigned)result);
}
#endif

static void dump_bytes(const char *label, const void *data, unsigned length)
{
    const uint8_t *bytes = (const uint8_t *)data;
    printf("%s", label);
    for (unsigned i = 0; i < length; ++i) {
        if ((i & 15) == 0) printf("\n%02x: ", i);
        printf("%02x", bytes[i]);
    }
    printf("\n");
    fflush(stdout);
}

int main(void)
{
    sys_ppu_thread_t thread;
    int ppu_priority = 0;
    int rc = sysSpuInitialize(2, 0);
    printf("REF spu_initialize=%08x\n", (unsigned)rc);
    if (rc) return 1;
    rc = sysThreadGetId(&thread);
    if (rc) return 2;
    rc = sysThreadGetPriority(thread, &ppu_priority);
    if (rc) return 3;

    Spurs *spurs = (Spurs *)memalign(SPURS_ALIGN, sizeof(Spurs));
    if (!spurs) return 4;
    SpursAttribute attr;
    rc = spursAttributeInitialize(&attr, 2, 250, ppu_priority - 1, 1);
    printf("REF spurs_attr=%08x\n", (unsigned)rc);
    if (rc) return 5;
    rc = spursInitializeWithAttribute(spurs, &attr);
    printf("REF spurs_init=%08x\n", (unsigned)rc);
    if (rc) return 6;

    const uint8_t priorities[8] = {8, 8, 8, 8, 8, 8, 8, 8};
    rc = spursCreateTaskset(spurs, taskset_storage, 0, priorities, 1);
    printf("REF taskset_create=%08x\n", (unsigned)rc);
    if (rc) return 7;

    memset(queue_storage, 0, sizeof(queue_storage));
    memset(ring_storage, 0, sizeof(ring_storage));
    for (unsigned i = 0; i < sizeof(item); ++i) item[i] = (uint8_t)(0xA0 + i);
#ifdef TEST_TAGGED_SPURS_OWNER
    rc = spursLFQueueInitialize((void *)((uintptr_t)spurs | 1u), queue_storage,
                                ring_storage, 32, 4, 3);
#else
    rc = spursLFQueueInitialize(taskset_storage, queue_storage, ring_storage, 32, 4, 3);
#endif
    printf("REF lfq_init=%08x\n", (unsigned)rc);
    if (rc) return 8;
#ifdef TEST_SPU_QUEUE_ATTACH
    rc = spursLFQueueAttachLv2EventQueue(queue_storage);
    printf("REF spu_queue_attach=%08x\n", (unsigned)rc);
    if (rc) return 17;
#endif
    dump_bytes("REF queue_before", queue_storage, sizeof(queue_storage));
    dump_bytes("REF ring_before", ring_storage, sizeof(ring_storage));

#ifdef TEST_SPU_TASK
    unsigned task_id = 0xffffffffu;
    memset(spu_marker, 0, sizeof(spu_marker));
    task_args[0] = (uint32_t)(uintptr_t)spu_marker;
#ifdef TEST_SPU_WAITER
    task_args[1] = (uint32_t)(uintptr_t)queue_storage;
#else
    task_args[1] = 0x1122334455667788ULL;
#endif
    printf("REF spu_marker_ea=%08x\n", (unsigned)task_args[0]);
    printf("REF spurs_ea=%08x taskset_ea=%08x queue_ea=%08x\n",
           (unsigned)(uintptr_t)spurs,
           (unsigned)(uintptr_t)taskset_storage,
           (unsigned)(uintptr_t)queue_storage);
#ifdef TEST_SPU_CONTEXT
#ifdef TEST_SPU_LS_PATTERN
    rc = spursCreateTask(taskset_storage, &task_id, spu_bin, task_context,
                         sizeof(task_context), task_ls_pattern, task_args);
#else
    rc = spursCreateTask(taskset_storage, &task_id, spu_bin, task_context,
                         sizeof(task_context), NULL, task_args);
#endif
#else
    rc = spursCreateTask(taskset_storage, &task_id, spu_bin, NULL, 0, NULL, task_args);
#endif
    printf("REF spu_task_create=%08x id=%08x\n", (unsigned)rc, task_id);
    dump_bytes("REF taskset_after_task_create", taskset_storage, 256);
    fflush(stdout);
    // Give the isolated reference scheduler a bounded chance to dispatch the
    // task before this fixture shuts its taskset down. This is diagnostic
    // pacing, not part of the compatibility implementation.
#ifdef TEST_SPU_WAITER
    unsigned waiter_spins = 0;
    while (waiter_spins++ < 200 &&
           !(queue_storage[4] == 0 && queue_storage[5] == 1))
        sysUsleep(1000);
    printf("REF spu_waiter_spins=%u registered=%u\n", waiter_spins,
           queue_storage[4] == 0 && queue_storage[5] == 1);
    dump_bytes("REF queue_with_spu_waiter", queue_storage, sizeof(queue_storage));
    dump_bytes("REF taskset_with_spu_waiter", taskset_storage, 256);
#ifdef TEST_SPU_WAIT_FOR_BLOCK
    unsigned block_spins = 0;
    while (block_spins++ < 200 && !(taskset_storage[0x50] & 0x80))
        sysUsleep(1000);
    printf("REF spu_block_spins=%u waiting=%u\n", block_spins,
           !!(taskset_storage[0x50] & 0x80));
    dump_bytes("REF taskset_blocked", taskset_storage, 256);
    if (!(taskset_storage[0x50] & 0x80)) return 15;
    sysUsleep(100000);
    dump_bytes("REF taskset_blocked_held", taskset_storage, 256);
    dump_bytes("REF spu_marker_blocked_held", spu_marker, sizeof(spu_marker));
    if (!(taskset_storage[0x50] & 0x80) ||
        memcmp(spu_marker, "LFQ0", 4) == 0) return 16;
#endif
#ifdef TEST_SPU_HOLD_NO_PUSH
    sysUsleep(100000);
    dump_bytes("REF spu_marker_held", spu_marker, sizeof(spu_marker));
    dump_bytes("REF spu_wait_codes_held", spu_marker + 16, 16);
    dump_bytes("REF taskset_held", taskset_storage, 256);
    if (memcmp(spu_marker, "LFQ0", 4) == 0) return 14;
    if (taskset_storage[0x50] & 0x80) return 0;
#endif
#ifdef TEST_DIRECT_TASK_SIGNAL
    // Control: ask the original firmware to signal this task without an LFQueue
    // push. This tests the fixture's task lifecycle, not queue notification.
    rc = spursSendSignal(taskset_storage, task_id);
    printf("REF direct_signal_result=%08x\n", (unsigned)rc);
    dump_bytes("REF taskset_after_direct_signal", taskset_storage, 128);
    unsigned direct_spins = 0;
    while (direct_spins++ < 200 && memcmp(spu_marker, "LFQ0", 4) != 0)
        sysUsleep(1000);
    printf("REF direct_signal_spins=%u observed=%u\n", direct_spins,
           memcmp(spu_marker, "LFQ0", 4) == 0);
    dump_bytes("REF taskset_after_direct_wait", taskset_storage, 128);
    dump_bytes("REF spu_marker_after_direct_signal", spu_marker, sizeof(spu_marker));
    return rc ? 18 : (memcmp(spu_marker, "LFQ0", 4) == 0 ? 0 : 19);
#endif
    dump_bytes("REF spu_marker_before_push", spu_marker, sizeof(spu_marker));
    if (!(queue_storage[4] == 0 && queue_storage[5] == 1)) return 12;
#ifdef TEST_SPU_INTERIM_STATES
    const struct { uint16_t cursor, waiter; } interim[] = {
        {2, 0x0842}, {6, 0x77bd},
    };
    for (unsigned i = 0; i < sizeof(interim)/sizeof(interim[0]); ++i) {
        uint16_t cursor = interim[i].cursor;
        memset(queue_storage, 0, 16);
        queue_storage[1] = queue_storage[7] = queue_storage[9] =
            queue_storage[15] = (uint8_t)cursor;
        queue_storage[4] = (uint8_t)(interim[i].waiter >> 8);
        queue_storage[5] = (uint8_t)interim[i].waiter;
        rc = spursLFQueuePushBody(queue_storage, item, 3);
        printf("REF_INTERIM before=%04x rc=%08x waiter=%02x%02x "
               "pub=%02x%02x reserve=%02x%02x item=%d\n",
               interim[i].waiter, (unsigned)rc, queue_storage[4],
               queue_storage[5], queue_storage[8], queue_storage[9],
               queue_storage[14], queue_storage[15],
               memcmp(ring_storage + (cursor % 4u) * 32u, item, 32) == 0);
        if (rc) return 26;
    }
    return 0;
#endif
#if defined(TEST_SPU_CAPTURED_RANGE) || defined(TEST_SPU_CAPTURED_EARLY_RANGE)
    uint16_t next_waiter = 0x0422;
#ifdef TEST_SPU_CAPTURED_EARLY_RANGE
    const unsigned first_count = 2;
    const unsigned last_count = TEST_SPU_CAPTURED_EARLY_RANGE;
#else
    const unsigned first_count = 1;
    const unsigned last_count = TEST_SPU_CAPTURED_RANGE;
#endif
    for (unsigned count = first_count; count <= last_count; ++count) {
        const uint16_t cursor = (uint16_t)(count % 8u); /* depth four */
        const uint16_t waiter = next_waiter;
        memset(queue_storage, 0, 16);
        queue_storage[0] = queue_storage[6] = queue_storage[8] =
            queue_storage[14] = (uint8_t)(cursor >> 8);
        queue_storage[1] = queue_storage[7] = queue_storage[9] =
            queue_storage[15] = (uint8_t)cursor;
        queue_storage[4] = (uint8_t)(waiter >> 8);
        queue_storage[5] = (uint8_t)waiter;
        rc = spursLFQueuePushBody(queue_storage, item, 3);
        const int item_match = memcmp(ring_storage + (cursor % 4u) * 32u,
                                      item, 32) == 0;
        printf("REF_RANGE count=%u rc=%08x pop=%02x%02x waiter=%02x%02x "
               "pub=%02x%02x reserve=%02x%02x slot=%u item=%d\n",
               count, (unsigned)rc, queue_storage[0], queue_storage[1],
               queue_storage[4], queue_storage[5], queue_storage[8],
               queue_storage[9], queue_storage[14], queue_storage[15],
               cursor % 4u, item_match);
        if (rc || !item_match) return 25;
        next_waiter = (uint16_t)((((uint16_t)queue_storage[4] << 8) |
                                   queue_storage[5]) + 0x21u);
    }
    return 0;
#endif
#if defined(TEST_SPU_CAPTURED_SECOND) || defined(TEST_SPU_CAPTURED_SECOND_EARLY) || defined(TEST_SPU_CAPTURED_THIRD) || defined(TEST_SPU_CAPTURED_FOURTH) || defined(TEST_SPU_CAPTURED_COUNT) || defined(TEST_SPU_CAPTURED_EARLY_RECOVERY) || defined(TEST_SPU_CAPTURED_NATIVE_WRAP)
    // Controlled diagnostic: replay the queue control bytes produced by the
    // original MotorStorm SPU after it consumed the first item and registered
    // for a second wait. Firmware still owns initialization and PushBody.
    const uint8_t captured_control[16] = {
        0x00, 0x01, 0x00, 0x00, 0x04, 0x22, 0x00, 0x01,
        0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01,
    };
    uint8_t early_control[16];
    memcpy(early_control, captured_control, sizeof(early_control));
#ifdef TEST_SPU_CAPTURED_SECOND_EARLY
    early_control[5] = 0x21;
#endif
#ifdef TEST_SPU_CAPTURED_THIRD
    const uint8_t third_control[16] = {
        0, 2, 0, 0, 8, 0x43, 0, 2,
        0, 2, 0, 0, 0, 0, 0, 2,
    };
    memcpy(early_control, third_control, sizeof(early_control));
#endif
#ifdef TEST_SPU_CAPTURED_FOURTH
    const uint8_t fourth_control[16] = {
        0, 3, 0, 0, 0x0c, 0x64, 0, 3,
        0, 3, 0, 0, 0, 0, 0, 3,
    };
    memcpy(early_control, fourth_control, sizeof(early_control));
#endif
#ifdef TEST_SPU_CAPTURED_COUNT
    /* Private diagnostic state replay for a count observed in native startup.
     * This alone cannot establish notification or concurrent behavior. */
    const uint16_t count = TEST_SPU_CAPTURED_COUNT;
    const uint16_t cursor = count % 8; /* fixture depth is four */
    const uint16_t waiter = (uint16_t)(count * 0x0400 + count * 0x21 + 1);
    memset(early_control, 0, sizeof(early_control));
    early_control[0] = (uint8_t)(cursor >> 8);
    early_control[1] = (uint8_t)cursor;
    early_control[4] = (uint8_t)(waiter >> 8);
    early_control[5] = (uint8_t)waiter;
    early_control[6] = (uint8_t)(cursor >> 8);
    early_control[7] = (uint8_t)cursor;
    early_control[8] = (uint8_t)(cursor >> 8);
    early_control[9] = (uint8_t)cursor;
    early_control[14] = (uint8_t)(cursor >> 8);
    early_control[15] = (uint8_t)cursor;
#endif
#ifdef TEST_SPU_CAPTURED_EARLY_RECOVERY
    const uint8_t recovery_control[16] = {
        0, 2, 0, 0, 4, 0x22, 0, 2,
        0, 2, 0, 0, 0, 0, 0, 2,
    };
    memcpy(early_control, recovery_control, sizeof(early_control));
#endif
#ifdef TEST_SPU_CAPTURED_NATIVE_WRAP
    const uint8_t native_wrap_control[16] = {
        0, 6, 0, 0, 0x77, 0xa0, 0, 6,
        0, 6, 0, 0, 0, 0, 0, 6,
    };
    memcpy(early_control, native_wrap_control, sizeof(early_control));
#endif
    memcpy(queue_storage, early_control, sizeof(early_control));
    dump_bytes("REF queue_captured_second_before", queue_storage,
               sizeof(queue_storage));
#endif
#else
    sysUsleep(100000);
    dump_bytes("REF spu_marker_after", spu_marker, sizeof(spu_marker));
#endif
#endif
#ifdef TEST_PPU_WAITER
    rc = spursLFQueueAttachLv2EventQueue(queue_storage);
    printf("REF ppu_waiter_attach=%08x\n", (unsigned)rc);
    if (rc) return 11;
    sys_ppu_thread_t waiter_thread;
    rc = sysThreadCreate(&waiter_thread, ppu_waiter, NULL, ppu_priority, 0x4000,
                         THREAD_JOINABLE, "lfq_ppu_waiter");
    printf("REF ppu_waiter_create=%08x\n", (unsigned)rc);
    if (rc) return 10;
    unsigned spins = 0;
    while (spins++ < 100000 && !waiter_done &&
           memcmp(queue_storage, (const uint8_t[16]){0}, 16) == 0)
        sysThreadYield();
    printf("REF ppu_waiter_spins=%u done=%d\n", spins, waiter_done);
    dump_bytes("REF queue_with_ppu_waiter", queue_storage, sizeof(queue_storage));
    rc = spursLFQueuePushBody(queue_storage, item, 3);
    printf("REF push_result=%08x\n", (unsigned)rc);
    dump_bytes("REF queue_after", queue_storage, sizeof(queue_storage));
    dump_bytes("REF taskset_after_push", taskset_storage, 128);
    uint64_t waiter_return = 0;
    int join_result = sysThreadJoin(waiter_thread, &waiter_return);
    printf("REF ppu_waiter_join=%08x return=%016llx\n", (unsigned)join_result,
           (unsigned long long)waiter_return);
    dump_bytes("REF queue_after_join", queue_storage, sizeof(queue_storage));
    dump_bytes("REF ppu_waiter_item", waiter_item, sizeof(waiter_item));
    int detach_rc = spursLFQueueDetachLv2EventQueue(queue_storage);
    printf("REF ppu_waiter_detach=%08x\n", (unsigned)detach_rc);
#else
    rc = spursLFQueuePushBody(queue_storage, item, 3);
    printf("REF push_result=%08x\n", (unsigned)rc);
    dump_bytes("REF queue_after", queue_storage, sizeof(queue_storage));
    dump_bytes("REF ring_after", ring_storage, sizeof(ring_storage));
#ifdef TEST_SPU_WAITER
    unsigned wake_spins = 0;
    while (wake_spins++ < 200 && memcmp(spu_marker, "LFQ0", 4) != 0)
        sysUsleep(1000);
    printf("REF spu_wake_spins=%u observed=%u\n", wake_spins,
           memcmp(spu_marker, "LFQ0", 4) == 0);
    dump_bytes("REF spu_marker_after", spu_marker, sizeof(spu_marker));
    dump_bytes("REF queue_after_spu_wake", queue_storage, sizeof(queue_storage));
    dump_bytes("REF taskset_after_spu_wake", taskset_storage, 128);
    if (memcmp(spu_marker, "LFQ0", 4) != 0) return 13;
#ifdef TEST_SPU_NOTIFY_ONLY
    return 0;
#endif
#endif

    if (rc == 0) {
        for (unsigned push = 1; push < 4; ++push) {
            for (unsigned i = 0; i < sizeof(item); ++i)
                item[i] = (uint8_t)(0xA0 + i + 0x10 * push);
            rc = spursLFQueuePushBody(queue_storage, item, 3);
            printf("REF push_%u_result=%08x\n", push + 1, (unsigned)rc);
            dump_bytes("REF queue_next", queue_storage, sizeof(queue_storage));
            if (rc) break;
        }
        dump_bytes("REF ring_final", ring_storage, sizeof(ring_storage));
        if (rc == 0) {
            uint8_t popped[32] __attribute__((aligned(16))) = {0};
            int pop_rc = spursLFQueuePopBody(queue_storage, popped, 3);
            printf("REF pop_result=%08x\n", (unsigned)pop_rc);
            dump_bytes("REF popped", popped, sizeof(popped));
            dump_bytes("REF queue_after_pop", queue_storage, sizeof(queue_storage));
            if (pop_rc == 0) {
                for (unsigned i = 0; i < sizeof(item); ++i)
                    item[i] = (uint8_t)(0xE0 + i);
                rc = spursLFQueuePushBody(queue_storage, item, 3);
                printf("REF wrap_push_result=%08x\n", (unsigned)rc);
                dump_bytes("REF queue_after_wrap", queue_storage, sizeof(queue_storage));
                dump_bytes("REF ring_after_wrap", ring_storage, sizeof(ring_storage));
            }
        }
    }
#endif

    int shutdown_rc = spursShutdownTaskset(taskset_storage);
    printf("REF taskset_shutdown=%08x\n", (unsigned)shutdown_rc);
    int join_rc = spursJoinTaskset(taskset_storage);
    printf("REF taskset_join=%08x\n", (unsigned)join_rc);
    int finalize_rc = spursFinalize(spurs);
    printf("REF spurs_finalize=%08x\n", (unsigned)finalize_rc);
    fflush(stdout);
    free(spurs);
    return rc == 0 ? 0 : 9;
}
