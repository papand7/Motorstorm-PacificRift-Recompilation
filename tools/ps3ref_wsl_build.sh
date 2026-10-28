#!/usr/bin/env bash
set -euo pipefail

# Run from Ubuntu WSL. Toolchain sources, installs, and logs stay outside the
# distributable project tree by default.
ref_root="${PS3REF_ROOT:-$HOME/ps3ref}"
export PS3DEV="$ref_root/install"
export PSL1GHT="$PS3DEV"
export PATH="$PS3DEV/bin:$PS3DEV/ppu/bin:$PS3DEV/spu/bin:$PATH"

if [[ ! -x "$ref_root/ps3toolchain/toolchain.sh" ]]; then
  echo "Missing official ps3toolchain checkout: $ref_root/ps3toolchain" >&2
  exit 1
fi

mkdir -p "$PS3DEV" "$ref_root/logs"
cd "$ref_root/ps3toolchain"
log="$ref_root/logs/toolchain-$(printf '%s-' "$@" | sed 's/-$//').log"
echo "Build log: $log"
if ./toolchain.sh "$@" >"$log" 2>&1; then
  tail -n 25 "$log"
else
  result=$?
  tail -n 100 "$log" >&2
  exit "$result"
fi
