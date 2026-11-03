"""T193: patch the harness, runtime test hook and test driver. Run from the motorstorm root."""
import re
R = 'ps3recomp-t193/'

def load(p):
    s = open(R + p, encoding='utf-8', newline='').read()
    return s.replace('\r\n', '\n'), ('\r\n' if '\r\n' in s else '\n')

def save(p, s, nl):
    open(R + p, 'w', encoding='utf-8', newline='').write(s.replace('\n', nl))

def rep(s, old, new, cnt=1):
    assert s.count(old) == cnt, (s.count(old), old[:90])
    return s.replace(old, new)

# ---- runtime: atexit hook for the test processes that use spu_ib_fast_set instead of the environment
s, nl = load('runtime/spu/spu_channels.c')
s = rep(s, '/* Test hook: pretend PS3_FTRACE_SPUJOB is recording with this job-return address (0 = tracing off). */\nvoid spu_ib_fast_test_trace(uint32_t jr) { g_ps3_ft.spujob',
        '/* Test hook: install the exit summary as spu_ib_fast_init does (for processes that switch on with spu_ib_fast_set). */\n'
        'void spu_ib_fast_register_atexit_for_test(void) { static int once; if (!once) { once = 1; atexit(spu_ib_fast_report_atexit); } }\n'
        '/* Test hook: pretend PS3_FTRACE_SPUJOB is recording with this job-return address (0 = tracing off). */\nvoid spu_ib_fast_test_trace(uint32_t jr) { g_ps3_ft.spujob')
s = rep(s, 'void spu_ib_fast_threads(unsigned out[3]) { out[0] = out[1] = out[2] = 0; }\n',
        'void spu_ib_fast_threads(unsigned out[3]) { out[0] = out[1] = out[2] = 0; }\nvoid spu_ib_fast_register_atexit_for_test(void) {}\n')
save('runtime/spu/spu_channels.c', s, nl)

# ---- harness
s, nl = load('tests/test_spu_ib_fast.c')
s = rep(s, '#define SPU_TASK_LO 0x3000u\n', '''/* Counter assertions hold only in -DSPU_IB_FAST_STATS builds; without it the same differential runs with them off
 * (T193: the shipping build's dispatch is compared with the resolver too). */
#ifdef SPU_IB_FAST_STATS
#  define SCHK(c) (c)
#else
#  define SCHK(c) ((void)(c), 1)
#endif
#define SPU_TASK_LO 0x3000u
''')
lines = s.split('\n')
pat = re.compile(r'CHECK\((.*?), "')
markers = ['first ordinary branch is one fill', 'repeats are pure cache hits', 'the masked high-bit branch hits',
           'after the epoch moved the first branch refills', 'an entry filled in an older epoch is refilled',
           'expected primary reason #%d', '...and the miss is classified as an epoch miss', 'primary reasons sum to the branches',
           'probe misses = fills + unresolved', 'random mix exercises hits, fills', 'primary reasons are exclusive and complete',
           'probe classes sum to fills', 'reloc mix exercised slots']
done = 0
for k, l in enumerate(lines):
    if any(m in l for m in markers) and 'CHECK(' in l and 'SCHK(' not in l:
        lines[k] = pat.sub(lambda m: 'CHECK(SCHK(' + m.group(1) + '), "', l, count=1)
        done += 1
assert done == len(markers), done
s = '\n'.join(lines)
chunk = open('generated/analysis/t193/tools/tele_chunk.c', encoding='utf-8').read().replace('\r\n', '\n')
s = rep(s, '\nint main(int argc, char** argv)\n', '\n' + chunk + '\nint main(int argc, char** argv)\n')
s = rep(s, '    if (!strcmp(mode, "envinit")) return envinit();\n', '''    if (!strcmp(mode, "envinit")) return envinit();
#if defined(SPU_IB_FAST_STATS) && !defined(T191_RUNTIME) && !defined(T192_RUNTIME)
    {   int tr = -1;
        if (!strcmp(mode, "tele_threads") && argc > 6) tr = tele_threads(argv[2], (unsigned)atoi(argv[3]), atoi(argv[4]), atoi(argv[5]), atol(argv[6]));
        else if (!strcmp(mode, "tele_idle") && argc > 2) tr = tele_idle(argv[2]);
        else if (!strcmp(mode, "tele_overflow") && argc > 2) tr = tele_overflow(argv[2]);
        else if (!strcmp(mode, "tele_reinit") && argc > 3) tr = tele_reinit(argv[2], atoi(argv[3]));
        else if (!strcmp(mode, "tele_run") && argc > 5) tr = tele_run(argv[2], (unsigned)atoi(argv[3]), atoi(argv[4]), atoi(argv[5]));
        if (tr >= 0) { printf("%s: %llu checks, %llu failures\\n", mode, checks, failures); return failures ? 1 : 0; } }
#endif
''')
# bench: optional interval reporter (reporting-overhead arm)
s = rep(s, '''        spu_ib_fast_set(getenv("BENCH_FAST") && getenv("BENCH_FAST")[0] == '1');\n''',
        '''        spu_ib_fast_set(getenv("BENCH_FAST") && getenv("BENCH_FAST")[0] == '1');
#if defined(SPU_IB_FAST_STATS) && !defined(T191_RUNTIME) && !defined(T192_RUNTIME)
        if (getenv("BENCH_TELE_MS")) spu_ib_fast_telemetry_configure((unsigned)atoi(getenv("BENCH_TELE_MS")), getenv("BENCH_TELE_FILE"));
#endif
''')
save('tests/test_spu_ib_fast.c', s, nl)
print('ok')
