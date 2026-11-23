"""Add a bench mode to test_ovl_entries.c: per-call time of each new entry, interpreted vs lifted.

usage: py -3 edit_ovl_bench.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parent / 'test_ovl_entries.c'
s = p.read_text(encoding='utf-8')
a = '    printf("test_ovl_entries%s: %d failure(s)\\n", mutate ? " (mutation)" : "", fails);'
b = '''    if (argc > 2 && !strcmp(argv[2], "bench")) {
        /* Per-call cost of each entry: interpreted (as the game ran it) vs lifted. */
        for (unsigned e = 0; e < 2; e++) {
            random_state(ovl, 7);
            const int N = 200000;
            LARGE_INTEGER f, t0, t1, t2;
            QueryPerformanceFrequency(&f);
            QueryPerformanceCounter(&t0);
            for (int i = 0; i < N; i++) spu_interp_run_until(&A, E[e].entry, E[e].next);
            QueryPerformanceCounter(&t1);
            for (int i = 0; i < N; i++) E[e].fn(&A);
            QueryPerformanceCounter(&t2);
            printf("bench LS 0x%05X: interpreted %.1f ns a call, lifted %.1f ns a call\\n", E[e].entry,
                   (double)(t1.QuadPart - t0.QuadPart) * 1e9 / f.QuadPart / N,
                   (double)(t2.QuadPart - t1.QuadPart) * 1e9 / f.QuadPart / N);
        }
    }
''' + a
assert s.count(a) == 1
s = s.replace(a, b)
assert s.count('#include <string.h>\n') == 1
s = s.replace('#include <string.h>\n', '#include <string.h>\n#include <windows.h>\n')
old = (" * usage: test_ovl_entries <overlay .bin> [mutate]   (mutate: corrupt the lifted\n"
       " *        result's link register, which must fail every trial) */")
assert s.count(old) == 1
s = s.replace(old, " * usage: test_ovl_entries <overlay .bin> [mutate|bench]   (mutate: corrupt the lifted\n"
                   " *        result's link register, which must fail every trial; bench: time both) */")
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
