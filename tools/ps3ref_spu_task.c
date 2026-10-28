// One-shot task execution diagnostic. Its PPU-provided argument names a
// 16-byte marker in guest memory; this is not an LFQueue notification model.
#include <spu_mfcio.h>
#include <spu_intrinsics.h>

static unsigned long long marker[2] __attribute__((aligned(16))) = {
    0x4c46513011223344ULL, 0x5566778899aabbccULL
};
#ifdef TEST_SPU_WAITER
static unsigned char queue_line[128] __attribute__((aligned(128)));
static volatile unsigned long long marker_target;
static unsigned int wait_codes[4] __attribute__((aligned(16)));
#endif

__attribute__((noreturn)) int main(vector unsigned long long task_arg)
{
    unsigned long long marker_ea = spu_extract(task_arg, 0);
    unsigned long long queue_ea = spu_extract(task_arg, 1);
#ifdef TEST_SPU_WAITER
    marker_target = marker_ea;
    // Controlled reproduction of the observed guest waiter registration.
    // This experiment does not establish the full SPU LFQueue pop protocol.
    unsigned status;
    do {
        mfc_getllar(queue_line, queue_ea, 0, 0);
        (void)mfc_read_atomic_status();
        queue_line[4] = 0;
        queue_line[5] = 1;
        mfc_putllc(queue_line, queue_ea, 0, 0);
        status = mfc_read_atomic_status();
    } while (status != 0);
    // Probe whether a startup-pending task signal satisfies the first wait.
    // The PPU snapshot before PushBody decides whether the second call blocks.
    unsigned first_code;
    unsigned second_code;
    __asm__ volatile("il $3, 2\n\tila $5, 0xa70\n\tbisl $0, $5\n\tori %0, $3, 0"
                     : "=r"(first_code) :: "memory");
#ifdef TEST_SPU_WAIT_OBJECT
    // The original task's bounded native trace has queue EA + 5 in the
    // SPURS task wait-object slot immediately before its wait syscall.
    // This private diagnostic tests that observed registration dependency.
    *(volatile unsigned int *)0x2FDC = (unsigned int)queue_ea + 5;
#endif
    __asm__ volatile("il $3, 2\n\tila $5, 0xa70\n\tbisl $0, $5\n\tori %0, $3, 0"
                     : "=r"(second_code) :: "memory");
    marker_ea = marker_target;
    wait_codes[0] = first_code;
    wait_codes[1] = second_code;
    mfc_put(wait_codes, marker_ea + 16, 16, 1, 0, 0);
    mfc_write_tag_mask(2);
    mfc_read_tag_status_all();
#endif
    mfc_put(marker, marker_ea, 16, 0, 0, 0);
    mfc_write_tag_mask(1);
    mfc_read_tag_status_all();
    // A SPURS task exits through the taskset policy module, not the default
    // SPU C runtime STOP. The documented task syscall gate is LS 0xA70;
    // syscall 0 is EXIT. This call is limited to the isolated reference test.
    __asm__ volatile("il $3, 0\n\tila $5, 0xa70\n\tbisl $0, $5" ::: "memory");
    for (;;) { }
}
