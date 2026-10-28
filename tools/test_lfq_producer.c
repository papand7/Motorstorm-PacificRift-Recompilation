/* Tests the independently authored first-push planner against bytes captured
 * from the original firmware. No proprietary binary or trace is embedded. */
#include "../ps3recomp/libs/spurs/lfqueue_producer.h"
#include <assert.h>
#include <string.h>

int main(void)
{
    uint8_t queue[128] = {0};
    lfq_initial_push plan = {0};
    uint8_t original[128];
    memcpy(original, queue, sizeof(queue));
    assert(lfq_plan_initial_push(queue, 4, &plan) == 1);
    assert(memcmp(queue, original, sizeof(queue)) == 0);
    assert(plan.slot == 0 && plan.next_reservation == 1 &&
           plan.next_publication == 1 && plan.recipient == 0xffff);
    assert(memcmp(queue, original, sizeof(queue)) == 0);

    /* The first successful firmware push produced this BE control word. */
    lfq_store_be16(queue + 0x0e, plan.next_reservation);
    lfq_store_be16(queue + 0x08, plan.next_publication);
    const uint8_t first_word[8] = {0, 1, 0, 0, 0, 0, 0, 1};
    assert(memcmp(queue + 8, first_word, sizeof(first_word)) == 0);
    assert(lfq_plan_initial_push(queue, 4, &plan) == 0);
    for (unsigned count = 1; count < 4; ++count) {
        assert(lfq_plan_uncontended_push(queue, 4, &plan) == 1);
        assert(plan.slot == count && plan.next_publication == count + 1);
        lfq_store_be16(queue + 8, plan.next_publication);
        lfq_store_be16(queue + 14, plan.next_reservation);
    }
    assert(lfq_plan_uncontended_push(queue, 4, &plan) == 0); /* full */
    lfq_store_be16(queue, 1); /* one original firmware pop */
    lfq_store_be16(queue + 6, 1);
    assert(lfq_plan_uncontended_push(queue, 4, &plan) == 1);
    assert(plan.slot == 0 && plan.next_publication == 5); /* wrap */

    memset(queue, 0, sizeof(queue));
    queue[5] = 1; /* registered consumer, notification still unverified */
    memcpy(original, queue, sizeof(queue));
    assert(lfq_plan_initial_push(queue, 4, &plan) == 1);
    assert(plan.recipient == 0 && plan.next_consumer_wait == 0x0401);
    lfq_store_be16(queue + 4, plan.next_consumer_wait);
    lfq_store_be16(queue + 8, plan.next_publication);
    lfq_store_be16(queue + 14, plan.next_reservation);
    assert(memcmp(queue, (const uint8_t[]){0,0,0,0,4,1,0,0,
                                            0,1,0,0,0,0,0,1}, 16) == 0);
    assert(lfq_plan_uncontended_push(queue, 4, &plan) == 0);
    const uint8_t second_before[16] = {
        0, 1, 0, 0, 4, 0x22, 0, 1,
        0, 1, 0, 0, 0, 0, 0, 1,
    };
    memcpy(queue, second_before, sizeof(second_before));
    memcpy(original, queue, sizeof(queue));
    assert(lfq_plan_second_registered(queue, 4, &plan) == 1);
    assert(plan.slot == 1 && plan.next_reservation == 2 &&
           plan.next_publication == 2 && plan.next_consumer_wait == 0x0822 &&
           plan.recipient == 0xfffe);
    assert(memcmp(queue, original, sizeof(queue)) == 0);
    lfq_store_be16(queue + 4, plan.next_consumer_wait);
    lfq_store_be16(queue + 8, plan.next_publication);
    lfq_store_be16(queue + 14, plan.next_reservation);
    assert(memcmp(queue, (const uint8_t[]){0,1,0,0,8,0x22,0,1,
                                            0,2,0,0,0,0,0,2}, 16) == 0);
    queue[5] = 0x23;
    assert(lfq_plan_second_registered(queue, 4, &plan) == 0);
    memcpy(queue, second_before, sizeof(second_before));
    queue[5] = 0x21;
    memcpy(original, queue, sizeof(queue));
    assert(lfq_plan_second_early(queue, 4, &plan) == 1);
    assert(plan.slot == 1 && plan.next_reservation == 2 &&
           plan.next_publication == 2 && plan.next_consumer_wait == 0x0421 &&
           plan.recipient == 0xffff);
    assert(memcmp(queue, original, sizeof(queue)) == 0);
    lfq_store_be16(queue + 8, plan.next_publication);
    lfq_store_be16(queue + 14, plan.next_reservation);
    assert(memcmp(queue, (const uint8_t[]){0,1,0,0,4,0x21,0,1,
                                            0,2,0,0,0,0,0,2}, 16) == 0);
    const uint8_t third_before[16] = {
        0,2,0,0,8,0x43,0,2, 0,2,0,0,0,0,0,2,
    };
    memcpy(queue, third_before, sizeof(third_before));
    memcpy(original, queue, sizeof(queue));
    assert(lfq_plan_third_registered(queue, 4, &plan) == 1);
    assert(plan.slot == 2 && plan.next_reservation == 3 &&
           plan.next_publication == 3 && plan.next_consumer_wait == 0x0c43 &&
           plan.recipient == 0xfffe);
    assert(memcmp(queue, original, sizeof(queue)) == 0);
    lfq_store_be16(queue + 4, plan.next_consumer_wait);
    lfq_store_be16(queue + 8, plan.next_publication);
    lfq_store_be16(queue + 14, plan.next_reservation);
    assert(memcmp(queue, (const uint8_t[]){0,2,0,0,0x0c,0x43,0,2,
                                            0,3,0,0,0,0,0,3}, 16) == 0);
    const uint8_t fourth_before[16] = {
        0,3,0,0,0x0c,0x64,0,3, 0,3,0,0,0,0,0,3,
    };
    memcpy(queue, fourth_before, sizeof(fourth_before));
    memcpy(original, queue, sizeof(queue));
    assert(lfq_plan_fourth_registered(queue, 4, &plan) == 1);
    assert(plan.slot == 3 && plan.next_reservation == 4 &&
           plan.next_publication == 4 && plan.next_consumer_wait == 0x1064 &&
           plan.recipient == 0xfffe);
    assert(memcmp(queue, original, sizeof(queue)) == 0);
    lfq_store_be16(queue + 4, plan.next_consumer_wait);
    lfq_store_be16(queue + 8, plan.next_publication);
    lfq_store_be16(queue + 14, plan.next_reservation);
    assert(memcmp(queue, (const uint8_t[]){0,3,0,0,0x10,0x64,0,3,
                                            0,4,0,0,0,0,0,4}, 16) == 0);
    uint16_t expected_waiter = 0x0422;
    for (unsigned count = 1; count <= 64; ++count) {
        memset(queue, 0, sizeof(queue));
        const uint16_t cursor = (uint16_t)(count % 8u);
        const uint16_t waiter = expected_waiter;
        lfq_store_be16(queue, cursor);
        lfq_store_be16(queue + 4, waiter);
        lfq_store_be16(queue + 6, cursor);
        lfq_store_be16(queue + 8, cursor);
        lfq_store_be16(queue + 14, cursor);
        memcpy(original, queue, sizeof(queue));
        assert(lfq_plan_measured_registered(queue, 4, &plan) == 1);
        assert(plan.slot == count % 4u &&
               plan.next_reservation == (count + 1u) % 8u &&
               plan.next_publication == plan.next_reservation &&
               plan.recipient == 0xfffeu);
        if (count == 29) assert(plan.next_consumer_wait == 0x03be);
        if (count == 30) assert(plan.next_consumer_wait == 0x07df);
        if (count == 58) assert(plan.next_consumer_wait == 0x037b);
        if (count == 64) assert(plan.next_consumer_wait == 0x1c41);
        assert(memcmp(queue, original, sizeof(queue)) == 0);
        expected_waiter = (uint16_t)(plan.next_consumer_wait + 0x21u);
    }
    expected_waiter = 0x0422;
    for (unsigned count = 2; count <= 64; ++count) {
        memset(queue, 0, sizeof(queue));
        uint16_t cursor = (uint16_t)(count % 8u);
        lfq_store_be16(queue, cursor);
        lfq_store_be16(queue + 4, expected_waiter);
        lfq_store_be16(queue + 6, cursor);
        lfq_store_be16(queue + 8, cursor);
        lfq_store_be16(queue + 14, cursor);
        memcpy(original, queue, sizeof(queue));
        assert(lfq_plan_measured_registered(queue, 4, &plan) == 1);
        assert(plan.slot == count % 4u &&
               plan.next_publication == (count + 1u) % 8u &&
               plan.recipient == 0xfffeu);
        if (count == 2) assert(plan.next_consumer_wait == 0x0822);
        if (count == 30) assert(plan.next_consumer_wait == 0x03be);
        if (count == 64) assert(plan.next_consumer_wait == 0x1820);
        assert(memcmp(queue, original, sizeof(queue)) == 0);
        expected_waiter = (uint16_t)(plan.next_consumer_wait + 0x21u);
    }
    const struct { uint16_t cursor, waiter, result; int ready; } atomic_cases[] = {
        {2, 0x0842, 0x0842, 0},
        {6, 0x77bd, 0x77bd, 0},
        {6, 0x77a0, 0x03a0, 1},
    };
    for (unsigned i = 0; i < sizeof(atomic_cases)/sizeof(atomic_cases[0]); ++i) {
        memset(queue, 0, sizeof(queue));
        lfq_store_be16(queue, atomic_cases[i].cursor);
        lfq_store_be16(queue + 4, atomic_cases[i].waiter);
        lfq_store_be16(queue + 6, atomic_cases[i].cursor);
        lfq_store_be16(queue + 8, atomic_cases[i].cursor);
        lfq_store_be16(queue + 14, atomic_cases[i].cursor);
        memcpy(original, queue, sizeof(queue));
        assert(lfq_plan_atomic_spu_waiter(queue, 4,
                                           atomic_cases[i].ready, &plan) == 1);
        assert(plan.next_consumer_wait == atomic_cases[i].result &&
               plan.next_publication == (atomic_cases[i].cursor + 1u) % 8u &&
               plan.recipient == (atomic_cases[i].ready ? 0xfffe : 0xffff));
        assert(memcmp(queue, original, sizeof(queue)) == 0);
    }
    queue[5] ^= 1;
    assert(lfq_plan_measured_registered(queue, 4, &plan) == 0);
    assert(lfq_plan_initial_push(queue, 0, &plan) == 0);
    assert(lfq_plan_initial_push(0, 4, &plan) == 0);
    assert(lfq_plan_initial_push(queue, 4, 0) == 0);
    return 0;
}
