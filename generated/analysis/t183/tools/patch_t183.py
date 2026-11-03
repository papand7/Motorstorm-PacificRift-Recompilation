"""Apply the T183 source edits, keeping each file's CRLF endings. One use: fails if a target is not found exactly once."""
import sys
from pathlib import Path
R = Path(sys.argv[1])
def sub(path, pairs):
    p = R / path
    t = p.read_bytes().decode('utf-8')
    for old, new in pairs:
        old, new = old.replace('\n', '\r\n'), new.replace('\n', '\r\n')
        assert t.count(old) == 1, (path, old[:60], t.count(old))
        t = t.replace(old, new)
    p.write_bytes(t.encode('utf-8'))
sub('runtime/spu/spu_workload.c', [
 ('#include "spu_task_pool.h"       /* T156: PS3_SPU_TASK_POOL */\n',
  '#include "spu_task_pool.h"       /* T156: PS3_SPU_TASK_POOL */\n#include "spu_task_log.h"        /* T183: PS3_SPU_TASK_QUIET */\n'),
 ('''    for (int i = 0; i < n_start; i++) {
        fprintf(stderr, "[taskset] start task %u of taskset 0x%08X elf=0x%08X "
                        "(after task %u exited)\\n", start_t[i], taskset_ea, start_elf[i], done_task);
''', '''    for (int i = 0; i < n_start; i++) {
        static unsigned s_tlog_start;
        if (spu_task_log_on(&s_tlog_start))
            fprintf(stderr, "[taskset] start task %u of taskset 0x%08X elf=0x%08X "
                            "(after task %u exited)\\n", start_t[i], taskset_ea, start_elf[i], done_task);
'''),
 ('''                    spurs_pm_build_context(ls, j->taskset_ea, j->taskid, 0, 0);
                    fprintf(stderr, "[taskset] built SpursTasksetContext image=%d "
                            "taskset=0x%08X task=%u\\n", j->image_id,
                            j->taskset_ea, j->taskid); fflush(stderr);
''', '''                    spurs_pm_build_context(ls, j->taskset_ea, j->taskid, 0, 0);
                    static unsigned s_tlog_built;
                    if (spu_task_log_on(&s_tlog_built)) {
                        fprintf(stderr, "[taskset] built SpursTasksetContext image=%d "
                                "taskset=0x%08X task=%u\\n", j->image_id,
                                j->taskset_ea, j->taskid); fflush(stderr);
                    }
'''),
 ('''            fprintf(stderr, "[spu_workload] async image=%d HOST_RUN_ENDED rc=%d "
                    "(guest job completion unverified)\\n", j->image_id, rc);
''', '''            { static unsigned s_tlog_ended;
              if (spu_task_log_on(&s_tlog_ended))
                  fprintf(stderr, "[spu_workload] async image=%d HOST_RUN_ENDED rc=%d "
                          "(guest job completion unverified)\\n", j->image_id, rc); }
'''),
 ('''    pp_note(PP_SPU_DISPATCH);
    fprintf(stderr,
        "[spu_workload] dispatch HIT (async) fp=0x%016llX args=0x%08X image=%d -> spawning thread\\n",
        (unsigned long long)fp, args_ea, image_id);
''', '''    pp_note(PP_SPU_DISPATCH);
    { static unsigned s_tlog_hit;
      if (spu_task_log_on(&s_tlog_hit))
          fprintf(stderr,
              "[spu_workload] dispatch HIT (async) fp=0x%016llX args=0x%08X image=%d -> spawning thread\\n",
              (unsigned long long)fp, args_ea, image_id); }
'''),
])
sub('runtime/spu/spu_channels.c', [
 ('''    uint64_t tagupd_n, mfc_ns;
};
''', '''    uint64_t tagupd_n, mfc_ns;
    uint64_t cpu_cyc, fn_tsc;   /* T183: the entry's on-CPU cycles against its elapsed TSC (ratio = share on CPU) */
};
'''),
 ('''static uint64_t s_tstat_ns, s_tstat_last, s_tstat_seq;
''', '''static uint64_t s_tstat_ns, s_tstat_last, s_tstat_seq;
static __thread uint64_t t_tstat_cyc0, t_tstat_tsc0;

/* This thread's on-CPU cycles, which Windows counts at the TSC rate; 0 elsewhere. */
static uint64_t spu_tstat_thread_cycles(void)
{
#ifdef _WIN32
    ULONG64 c = 0;
    return QueryThreadCycleTime(GetCurrentThread(), &c) ? (uint64_t)c : 0;
#else
    return 0;
#endif
}
static uint64_t spu_tstat_tsc(void)
{
#ifdef _WIN32
    return __rdtsc();
#else
    return 0;
#endif
}
'''),
 ('''    t_tstat = spu_tstat_slot(image);
    return t_tstat ? spu_host_ns() : 0;
''', '''    t_tstat = spu_tstat_slot(image);
    if (t_tstat) { t_tstat_cyc0 = spu_tstat_thread_cycles(); t_tstat_tsc0 = spu_tstat_tsc(); }
    return t_tstat ? spu_host_ns() : 0;
'''),
 ('''    __atomic_fetch_add(&e->fn_ns, fn, __ATOMIC_RELAXED);
''', '''    __atomic_fetch_add(&e->fn_ns, fn, __ATOMIC_RELAXED);
    __atomic_fetch_add(&e->cpu_cyc, spu_tstat_thread_cycles() - t_tstat_cyc0, __ATOMIC_RELAXED);
    __atomic_fetch_add(&e->fn_tsc, spu_tstat_tsc() - t_tstat_tsc0, __ATOMIC_RELAXED);
'''),
 ('''                "other=%llu tagupd=%llu mfc_ns=%llu\\n",
''', '''                "other=%llu tagupd=%llu mfc_ns=%llu cpu_cyc=%llu fn_tsc=%llu\\n",
'''),
 ('''TL(putllc_n), TL(putllc_fail), TL(putlluc_n), TL(other_n), TL(tagupd_n), TL(mfc_ns));
''', '''TL(putllc_n), TL(putllc_fail), TL(putlluc_n), TL(other_n), TL(tagupd_n), TL(mfc_ns), TL(cpu_cyc), TL(fn_tsc));
'''),
])
sub('tests/test_spu_task_stats.py', [
 ('''              'on: mfc time <= entry time <= run time')
''', '''              'on: mfc time <= entry time <= run time')
        if os.name == 'nt':
            check(0 < int(last.get('cpu_cyc', 0)) and 0 < int(last.get('fn_tsc', 0)),
                  'on: the entry reports on-CPU cycles and elapsed TSC')
'''),
])
print('patched')
