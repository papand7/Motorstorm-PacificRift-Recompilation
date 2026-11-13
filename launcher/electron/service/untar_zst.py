"""Unpack a .tar.zst whose zstd window is larger than the system's tar.exe accepts (LLVM's Windows release).

    python untar_zst.py <archive.tar.zst> <dest> [strip]

Python 3.14's compression.zstd with window_log_max 31; members are checked to stay inside <dest>; links refused.
"""
import sys
import tarfile
from pathlib import Path, PurePosixPath
from compression import zstd


def main():
    archive, dest = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    strip = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    n = 0
    with open(archive, 'rb') as raw:
        with zstd.ZstdFile(raw, options={zstd.DecompressionParameter.window_log_max: 31}) as z:
            with tarfile.open(fileobj=z, mode='r|') as tar:
                for m in tar:
                    parts = PurePosixPath(m.name).parts[strip:]
                    if not parts or '..' in parts or PurePosixPath(m.name).is_absolute():
                        continue
                    target = dest.joinpath(*parts)
                    if m.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    elif m.isfile():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with tar.extractfile(m) as src, open(target, 'wb') as out:
                            while chunk := src.read(4 << 20):
                                out.write(chunk)
                        n += 1
                    elif m.issym() or m.islnk():
                        raise SystemExit(f'unexpected link in the archive: {m.name}')
                    if n and n % 500 == 0:
                        print(f'{n} files', flush=True)
    print(f'unpacked {n} files into {dest}')


if __name__ == '__main__':
    main()
