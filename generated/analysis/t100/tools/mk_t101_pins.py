MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
from pathlib import Path
src = Path((MS_ROOT + r"/ps3recomp-t101/tools/test_t101_pins.py")).read_text()
old = 'SRC = pathlib.Path(__file__).resolve().parents[1] / "libs" / "video" / "rsx_d3d12_backend.c"'
assert old in src
src = src.replace(old, 'SRC = pathlib.Path(__file__).resolve().parents[4] / "ps3recomp-t100/libs/video/rsx_d3d12_backend.c"')
Path(__file__).with_name("t101_pins_on_t100.py").write_text(src)
