/* AVX2 usability check for PORT_SPU_AVX2 builds.
 *
 * AVX2 may be executed only if the CPU reports it (CPUID leaf 7 EBX bit 5),
 * the CPU has AVX and OSXSAVE (leaf 1 ECX bits 28 and 27), and the OS saves
 * XMM and YMM state on context switch (XCR0 bits 1 and 2). XGETBV is executed
 * only after OSXSAVE is confirmed; it faults otherwise. Plain CPUID, so no
 * compiler-rt: __builtin_cpu_supports needs __cpu_model, which clang-cl does
 * not link.
 *
 * port_avx2_usable() takes its CPUID/XGETBV sources as parameters so the
 * decision can be tested without the hardware it rejects
 * (port/tests/test_port_cpu.c). */
#ifndef PORT_CPU_H
#define PORT_CPU_H

#if defined(_MSC_VER)
#include <intrin.h>
#else
#include <cpuid.h>
#endif

typedef void (*port_cpuid_fn)(unsigned leaf, unsigned sub, unsigned r[4]);
typedef unsigned long long (*port_xgetbv_fn)(void);

static int port_avx2_usable(port_cpuid_fn cpuid, port_xgetbv_fn xgetbv0)
{
    unsigned r[4];
    cpuid(0, 0, r);
    if (r[0] < 7) return 0;
    cpuid(1, 0, r);
    if ((r[2] & (1u << 27)) == 0 || (r[2] & (1u << 28)) == 0) return 0;
    if ((xgetbv0() & 6u) != 6u) return 0;
    cpuid(7, 0, r);
    return (r[1] & (1u << 5)) != 0;
}

static void port_cpuid(unsigned leaf, unsigned sub, unsigned r[4])
{
#if defined(_MSC_VER)
    int v[4];
    __cpuidex(v, (int)leaf, (int)sub);
    for (int i = 0; i < 4; i++) r[i] = (unsigned)v[i];
#else
    __cpuid_count(leaf, sub, r[0], r[1], r[2], r[3]);
#endif
}

static unsigned long long port_xgetbv0(void)
{
#if defined(_MSC_VER) && !defined(__clang__)
    return _xgetbv(0);
#else
    unsigned lo, hi;
    __asm__ volatile("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0));
    return ((unsigned long long)hi << 32) | lo;
#endif
}

static int port_cpu_has_avx2(void)
{
    return port_avx2_usable(port_cpuid, port_xgetbv0);
}

#endif
