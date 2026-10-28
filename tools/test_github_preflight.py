#!/usr/bin/env python3
"""Synthetic tests for tools/github_preflight.py (temporary repositories, no network, no push)."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

TOOL = Path(__file__).resolve().parent / "github_preflight.py"
NOREPLY = "1+test@users.noreply.github.com"


def git(repo, *args, email=NOREPLY):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL=email, GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL=email)
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def preflight(repo, *extra):
    p = subprocess.run([sys.executable, str(TOOL), "--repo", str(repo), "--remote", "private", "--branch", "main",
                        "--expect", "example/private-test", "--offline", *extra], capture_output=True, text=True)
    return p.returncode, p.stdout


def commit(repo, name, data, email=NOREPLY):
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_bytes(data)
    git(repo, "add", name, email=email)
    git(repo, "commit", "-q", "-m", name, email=email)


def main() -> int:
    failures = 0

    def check(label, cond, out=""):
        nonlocal failures
        print(("ok   " if cond else "FAIL ") + label)
        if not cond:
            failures += 1
            print(out)

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "r"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "remote", "add", "private", "https://github.com/example/private-test.git")
        commit(repo, "src/a.c", b"int a;\n")
        rc, out = preflight(repo)
        check("clean branch passes", rc == 0 and "RESULT PASS" in out, out)
        check("never pushes, only prints the command", "push command" in out, out)

        git(repo, "remote", "add", "origin", "https://github.com/sp00nznet/ps3recomp.git")
        rc, out = preflight(repo)
        check("public upstream with a push URL fails", rc == 1 and "not DISABLED" in out, out)
        git(repo, "remote", "set-url", "--push", "origin", "DISABLED")
        rc, out = preflight(repo)
        check("public upstream with push DISABLED passes", rc == 0, out)

        rc, out = subprocess.run([sys.executable, str(TOOL), "--repo", str(repo), "--remote", "origin", "--branch",
                                  "main", "--offline"], capture_output=True, text=True).returncode, ""
        check("pushing to the public remote is refused", rc == 1)

        rc, out = preflight(repo, "--expect", "someone/else")
        check("wrong destination fails", rc == 1 and "expected someone/else" in out, out)

        commit(repo, "data/x.bin", b"\x00\x01")
        rc, out = preflight(repo)
        check("binary/private file type fails", rc == 1 and "data/x.bin" in out, out)
        git(repo, "rm", "-q", "data/x.bin")
        git(repo, "commit", "-q", "-m", "rm")
        rc, out = preflight(repo)
        check("a file removed later still fails (history is scanned)", rc == 1 and "data/x.bin" in out, out)

        repo2 = Path(tmp) / "r2"
        repo2.mkdir()
        git(repo2, "init", "-q", "-b", "main")
        git(repo2, "remote", "add", "private", "https://github.com/example/private-test.git")
        commit(repo2, "notes.md", b"replace C:\\Users\\<name>\\... and C:\\Users\\someone\\x\n")
        rc, out = preflight(repo2)
        check("placeholder user paths pass", rc == 0, out)
        commit(repo2, "notes2.md", b"see C:/Users/jdoe/Desktop/x\n")
        rc, out = preflight(repo2)
        check("real local user path fails", rc == 1 and "local user path" in out, out)

        repo3 = Path(tmp) / "r3"
        repo3.mkdir()
        git(repo3, "init", "-q", "-b", "main")
        git(repo3, "remote", "add", "private", "https://github.com/example/private-test.git")
        commit(repo3, "a.txt", b"x\n", email="someone@example.com")
        rc, out = preflight(repo3)
        check("personal e-mail fails by default", rc == 1 and "e-mail" in out, out)
        rc, out = preflight(repo3, "--allow-email")
        check("personal e-mail accepted with --allow-email", rc == 0, out)
        commit(repo3, "k.txt", b"token ghp_" + b"A" * 36 + b"\n")
        rc, out = preflight(repo3, "--allow-email")
        check("credential pattern fails", rc == 1 and "credential pattern" in out, out)

    print("github_preflight tests:", "PASS" if not failures else f"{failures} FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
