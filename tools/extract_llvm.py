"""Extract the verified LLVM 23.1.3 Windows archive into build/llvm."""

from __future__ import annotations

import hashlib
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build" / "python"))
import zstandard  # noqa: E402

ARCHIVE = ROOT / "build" / "clang-llvm-23.1.3-windows.tar.zst"
DEST = ROOT / "build" / "llvm"
EXPECTED = "7e69dc07a4536b79ff24a651a2611990bf8eaab17ea560f1092707c4f31ba01d"


def main() -> None:
    digest = hashlib.sha256()
    with ARCHIVE.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != EXPECTED:
        raise ValueError("LLVM archive SHA-256 mismatch")

    DEST.mkdir(parents=True, exist_ok=True)
    count = 0
    total = 0
    with ARCHIVE.open("rb") as source:
        frame = zstandard.get_frame_parameters(source.read(18))
        source.seek(0)
        print(f"Zstd window: {frame.window_size} bytes", flush=True)
        with zstandard.ZstdDecompressor(max_window_size=max(frame.window_size, 1 << 27)).stream_reader(source) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as archive:
                for member in archive:
                    relative = PurePosixPath(member.name)
                    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                        raise ValueError(f"Unsafe path in archive: {member.name!r}")
                    target = DEST.joinpath(*relative.parts)
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    elif member.isfile():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        payload = archive.extractfile(member)
                        if payload is None:
                            raise ValueError(f"Missing payload: {member.name}")
                        with target.open("wb") as output:
                            shutil.copyfileobj(payload, output)
                        count += 1
                        total += member.size
                    elif member.issym() or member.islnk():
                        raise ValueError(f"Unexpected link in Windows archive: {member.name}")
    print(f"Extracted {count} files, {total} bytes into {DEST}")


if __name__ == "__main__":
    main()
