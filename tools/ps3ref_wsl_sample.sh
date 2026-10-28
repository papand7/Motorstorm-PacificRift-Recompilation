#!/usr/bin/env bash
set -euo pipefail

ref_root="${PS3REF_ROOT:-$HOME/ps3ref}"
export PS3DEV="$ref_root/install"
export PSL1GHT="$PS3DEV"
export PATH="$PS3DEV/bin:$PS3DEV/ppu/bin:$PS3DEV/spu/bin:$PATH"

sample="${1:-$ref_root/test/spurs}"
if [[ ! -f "$sample/Makefile" ]]; then
  echo "Missing PS3 sample Makefile: $sample" >&2
  exit 1
fi

mkdir -p "$ref_root/logs"
log="$ref_root/logs/sample-$(basename "$sample").log"
echo "Build log: $log"
if make -C "$sample" >"$log" 2>&1; then
  tail -n 25 "$log"
else
  result=$?
  tail -n 100 "$log" >&2
  exit "$result"
fi
