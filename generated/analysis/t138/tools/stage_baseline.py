"""T138: stage the pre-T138 versions of the files T138 changed, so commit 1 records the workspace as found.

The originals are reconstructed by inverting T138's edits (audit, its test, hook) or from the exact text read
before editing (README.md, docs/ROADMAP.md, .gitignore). Files new in T138 are left out of the index.
Run from the workspace root after `git add` of the project paths.
"""
import subprocess
from pathlib import Path

ROOT = Path.cwd()
NEW = ['CONTRIBUTING.md', 'SECURITY.md', '.github/workflows/ci.yml', 'tools/check_docs.py',
       'docs/ARCHITECTURE.md', 'docs/BUILDING.md', 'docs/DEVELOPMENT.md', 'docs/AGENT_WORKFLOW.md',
       'docs/media/banner.svg']


def stage(path, text):
    oid = subprocess.run(['git', 'hash-object', '-w', '--stdin'], input=text.encode('utf-8'),
                         capture_output=True, check=True).stdout.decode().strip()
    subprocess.run(['git', 'update-index', '--add', '--cacheinfo', f'100644,{oid},{path}'], check=True)


def unedit(path, pairs):
    t = (ROOT / path).read_text(encoding='utf-8')
    for new, old in pairs:
        assert t.count(new) == 1, (path, new[:60])
        t = t.replace(new, old)
    return t


audit = (ROOT / 'tools/audit_public.py').read_text(encoding='utf-8')
a = audit.index('# --private-reports (the private project repository only')
b = audit.index('def inspect_blob(')
audit = audit[:a] + audit[b:]
for new, old in [
    ('def inspect_blob(name: str, data: bytes, *, symlink: bool = False,\n                 private_reports: bool = False) -> list[str]:',
     'def inspect_blob(name: str, data: bytes, *, symlink: bool = False) -> list[str]:'),
    ('    report = private_reports and bool(PRIVATE_REPORT.match(normalized))\n', ''),
    ('    if report:\n        reasons.extend(inspect_private_report(normalized, data))\n    elif any(',
     '    if any('),
    ('def audit_staged(private_reports: bool = False)', 'def audit_staged()'),
    ('        reasons = inspect_blob(name, data, symlink=(mode == "120000"),\n                               private_reports=private_reports)',
     '        reasons = inspect_blob(name, data, symlink=(mode == "120000"))'),
]:
    assert audit.count(new) == 1, new[:60]
    audit = audit.replace(new, old)
a = audit.index('    parser.add_argument("--private-reports"')
b = audit.index('    try:\n        findings =')
audit = audit[:a] + '    args = parser.parse_args()\n' + audit[b:]
audit = audit.replace('audit_staged(args.private_reports) if args.staged', 'audit_staged() if args.staged')
stage('tools/audit_public.py', audit)

test = (ROOT / 'tools/test_audit_public.py').read_text(encoding='utf-8')
a = test.index('    def test_private_reports_only_when_enabled(self):')
b = test.index('    def test_staged_audit_checks_blob_not_worktree(self):')
stage('tools/test_audit_public.py', test[:a] + test[b:])

stage('tools/hooks/pre-commit', unedit('tools/hooks/pre-commit', [
    ('/tools/audit_public.py" --staged --private-reports\nelif', '/tools/audit_public.py" --staged\nelif'),
    ('/tools/audit_public.py" --staged --private-reports\nfi', '/tools/audit_public.py" --staged\nfi')]))

stage('README.md', """# MotorStorm: Pacific Rift PC

Native Windows x64 static recompilation project using [ps3recomp](https://github.com/sp00nznet/ps3recomp). Original PPU/SPU code has been translated and linked locally; startup currently stalls at an unresolved SPURS LFQueue push. See [status](docs/STATUS.md) and [build instructions](docs/BUILD.md).

The public project contains tools and independently written compatibility code only. Users supply their own game files locally. Game and firmware inputs, assets, generated source, and linked game binaries are private and excluded from releases. See [distribution policy](docs/DISTRIBUTION.md) and [third-party licenses](THIRD_PARTY_LICENSES.md).
""")

stage('docs/ROADMAP.md', """# Roadmap

1. **P0 — decrypted executable: complete.** The supplied ELF is hashed separately from the preserved retail SELF and ISO. Its OPD, imports, segments and entry are recorded in `docs/RESEARCH.md`.
2. **P0 — static translation: partial.** PPU code, 26 embedded SPU ELF images and the raw Wws_Job policy module are lifted. Review the PPU lifter's 26 missing-continuation warnings and identify any further dynamically loaded SPU programs.
3. **P0 — Windows x64 compile and link: complete for discovered code.** The native executable links and executes original startup; preserve the current build as a baseline.
4. **P1 — original startup: active.** Trace task 0 in taskset `0x40493480` and event flag `0x40494D80`; identify the exact producer of the missing signal or event, then implement the missing runtime behavior with a targeted regression test. Continue through original graphics, audio, menus and an offline race.
5. **P2 — native networking.** Compare this executable's network calls and version with the [MSPR private server](https://github.com/ZoniBoy00/MSPR-Server); validate lobbies and races before crossplay claims.
6. **P3/P4 — optional mods and graphics upgrades.** Begin after the original offline race works and fidelity can be measured.
""")

gi = """/original/
/generated/
/build/

# User-supplied game and firmware material; local only.
/private/
/firmware/
/game/
/mods/
"""
for ext in ['iso', 'sfo', 'self', 'elf', 'prx', 'sprx', 'psarc', 'pkg', 'rap', 'rif']:
    gi += f'*.{ext}\n*.{ext.upper()}\n'
gi += """*.keys
*.klic

# All lifted code, analysis, local binaries, logs, and release staging.
/release/
/dist/
/out/
/port/recompiled/
/port/spu/
**/generated_spu/
**/recompiled/
**/spu_lifted/
**/fw_spu/
*.bin
*.BIN
"""
for ext in ['o', 'obj', 'a', 'lib', 'dll', 'exe', 'pdb', 'ilk', 'exp', 'so', 'dylib', 'dmg', 'zip', '7z', 'rar', 'log']:
    gi += f'*.{ext}\n'
gi += """
# Local tooling state.
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
.vs/
.vscode/
CMakeFiles/
CMakeCache.txt
.cache/
"""
stage('.gitignore', gi)

subprocess.run(['git', 'rm', '-q', '--cached', '--', *NEW], check=True)
print('baseline staged')
