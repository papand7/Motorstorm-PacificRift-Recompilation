MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
import pathlib
A = pathlib.Path((MS_ROOT + r'\generated\analysis'))
s = (A / 't99/tools/tu_t99.cmd').read_text()
s = s.replace('ps3recomp-t99', 'ps3recomp-t102').replace(r'analysis\t99\logs', r'analysis\t102\logs')
llvm = (MS_ROOT + r'\build\llvm')
i = s.index(llvm)
end = 'echo cellGcmSys.c rc=%ERRORLEVEL%'
j = s.index(end) + len(end)
s = s[:i] + s[j:]          # only rsx_d3d12_backend.c changes in T102
assert 't99' not in s and s.count('clang-cl.exe') == 1
(A / 't102/tools/tu_t102.cmd').write_text(s)
r = (A / 't99/tools/run_suite_t99.py').read_text()
r2 = r.replace("test_rsx_frame_perf'''", "test_rsx_frame_perf test_vp_expand'''")
assert r2 != r
(A / 't102/tools/run_suite_t102.py').write_text(r2)
c = (A / 't99/tools/run_suite_t99.cmd').read_text().replace('t99', 't102')
(A / 't102/tools/run_suite_t102.cmd').write_text(c)
print(c)
