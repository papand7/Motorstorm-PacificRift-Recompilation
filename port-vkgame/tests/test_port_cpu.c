/* port_avx2_usable(): each required bit missing must reject AVX2, and XGETBV
 * must not run unless OSXSAVE is set. Also runs the real check on this host.
 *   clang-cl /O2 /I port port\tests\test_port_cpu.c && test_port_cpu.exe */
#include <stdio.h>
#include "port_cpu.h"

static unsigned m_max, m_ecx1, m_ebx7;
static unsigned long long m_xcr0;
static int m_xgetbv_calls;

static void mock_cpuid(unsigned leaf, unsigned sub, unsigned r[4])
{
    (void)sub;
    r[0] = r[1] = r[2] = r[3] = 0;
    if (leaf == 0) r[0] = m_max;
    if (leaf == 1) r[2] = m_ecx1;
    if (leaf == 7) r[1] = m_ebx7;
}

static unsigned long long mock_xgetbv(void) { m_xgetbv_calls++; return m_xcr0; }

static int fails;
static void check(const char* what, int want, int want_xgetbv)
{
    m_xgetbv_calls = 0;
    int got = port_avx2_usable(mock_cpuid, mock_xgetbv);
    if (got != want || (!want_xgetbv && m_xgetbv_calls)) {
        printf("FAIL %s: got %d (xgetbv calls %d)\n", what, got, m_xgetbv_calls);
        fails++;
    }
}

int main(void)
{
    const unsigned OSXSAVE = 1u << 27, AVX = 1u << 28, AVX2 = 1u << 5;
    m_max = 0xD; m_ecx1 = OSXSAVE | AVX; m_xcr0 = 7; m_ebx7 = AVX2;
    check("all present", 1, 1);
    m_max = 6;                  check("max leaf < 7", 0, 0);           m_max = 0xD;
    m_ecx1 = AVX;               check("no OSXSAVE (xgetbv would fault)", 0, 0);
    m_ecx1 = OSXSAVE;           check("no AVX", 0, 1);                 m_ecx1 = OSXSAVE | AVX;
    m_xcr0 = 3;                 check("OS does not save YMM", 0, 1);
    m_xcr0 = 5;                 check("OS does not save XMM", 0, 1);   m_xcr0 = 7;
    m_ebx7 = 0;                 check("no AVX2 bit", 0, 1);
    m_ebx7 = ~AVX2;             check("other leaf-7 bits only", 0, 1); m_ebx7 = AVX2;
    printf("host: AVX2 %s\n", port_cpu_has_avx2() ? "usable" : "not usable");
    printf(fails ? "%d FAILED\n" : "all passed\n", fails);
    return fails != 0;
}
