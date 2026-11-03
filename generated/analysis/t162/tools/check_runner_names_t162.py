"""T162: names a generated runner reads but never defines (the generators cut slices out of run_t161.py).
  py -3 check_runner_names_t162.py <runner.py>...   Exit 1 if any is undefined. Offline; imports nothing from the runner."""
import ast, builtins, sys
bad = 0
for f in sys.argv[1:]:
    tree = ast.parse(open(f, encoding='utf-8').read())
    defined = set(dir(builtins)) | {'__file__', '__name__'}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            defined.add(n.name)
        if isinstance(n, ast.FunctionDef):
            a = n.args
            defined |= {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
            defined |= {x.arg for x in (a.vararg, a.kwarg) if x}
        elif isinstance(n, ast.Lambda):
            a = n.args
            defined |= {x.arg for x in a.args + a.kwonlyargs}
            defined |= {x.arg for x in (a.vararg, a.kwarg) if x}
        elif isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load):
            defined.add(n.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            defined |= {(x.asname or x.name).split('.')[0] for x in n.names}
        elif isinstance(n, ast.ExceptHandler) and n.name:
            defined.add(n.name)
    missing = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} - defined)
    print(f, 'undefined:', missing or 'none')
    bad += bool(missing)
sys.exit(1 if bad else 0)
