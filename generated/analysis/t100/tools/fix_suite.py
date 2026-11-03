from pathlib import Path
d = Path(__file__).resolve().parent
c = (d / "run_suite_t100.cmd").read_text()
c = c.replace(r'cd /d "%~dp0..\..\..\..\.."', r'cd /d "%~dp0..\..\..\.."')
c = c.replace(r'generated\analysis\t96\t96i\tools\run_suite_t96i.py', r'generated\analysis\t100\tools\run_suite_t100.py')
assert 'run_suite_t100.py' in c and r'..\..\..\..\..' not in c
(d / "run_suite_t100.cmd").write_text(c)
p = (d / "run_suite_t100.py").read_text().replace("ROOT = HERE.parents[4]", "ROOT = HERE.parents[3]")
assert "parents[3]" in p
(d / "run_suite_t100.py").write_text(p)
print("ok")
