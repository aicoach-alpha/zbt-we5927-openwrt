#!/bin/sh
# Return ONLY the native OpenWrt host utility for this build tree.
# Never traverse staging_dir/target-* (MIPS binaries cannot run on CI x86_64).
set -eu
[ "$#" -eq 1 ] || { echo 'usage: veci-select-host-fwtool.sh <openwrt-root>' >&2; exit 2; }
root="$1"
[ -d "$root" ] && [ -f "$root/include/toplevel.mk" ] ||
 { echo 'not_openwrt_build_tree' >&2; exit 2; }
[ "$(uname -m)" = x86_64 ] ||
 { echo 'unsupported_ci_host_arch' >&2; exit 3; }
candidate="$root/staging_dir/host/bin/fwtool"
[ -f "$candidate" ] && [ -x "$candidate" ] && [ ! -L "$candidate" ] ||
 { echo 'native_host_fwtool_missing' >&2; exit 3; }
command -v file >/dev/null 2>&1 || { echo 'host_file_utility_missing' >&2; exit 3; }
info="$(file -Lb "$candidate")"
case "$info" in
  *'ELF 64-bit'*'x86-64'*) ;;
  *) echo 'fwtool_wrong_host_arch' >&2; exit 3 ;;
esac
printf '%s\n' "$candidate"
