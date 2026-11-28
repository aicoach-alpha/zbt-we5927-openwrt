#!/usr/bin/env bash
# Prepare pinned host-only UCI/libubox for real native source-acceptance tests.
# This is NOT an OpenWrt firmware build; refuses absent core-source evidence.
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd -P)"
# This provisions disposable HOST UCI/libubox fixtures, not router firmware.
# Source hash changes are precisely what these tests must evaluate before a
# new accepted source receipt can be produced. Keep the firmware compilation
# and signing gates in their separate release/build workflows untouched.
if python3 "$repo/rebuild/veci-v2/ci/source-completion-gate.py" >/dev/null; then
  echo 'SOURCE_EVIDENCE_CURRENT_HOST_TOOLS_ONLY'
else
  echo 'SOURCE_EVIDENCE_STALE_HOST_NATIVE_TESTS_ONLY_NO_FIRMWARE_BUILD' >&2
fi
if [ "$#" -ne 1 ]; then echo 'usage: provision-native-uci-tests.sh <disposable-dir>' >&2; exit 2; fi
root="$1"
case "$root" in
  ''|/|/tmp|/home|/etc|/root|/usr|/var) echo INVALID_HOST_TOOLS_ROOT >&2; exit 2 ;;
esac
mkdir -p "$root"
root="$(cd "$root" && pwd -P)"
prefix="$root/prefix"
libubox_commit=a396f38a8568a1d670c240465cd8d24fdfdf6463
uci_commit=74f6277aabffc943d026f406df57c22595134c42
libubox_override=$(printenv VECI_NATIVE_SOURCE_LIBUBOX || :)
uci_override=$(printenv VECI_NATIVE_SOURCE_UCI || :)
clone_pinned() {
  directory="$1"
  remote="$2"
  commit="$3"
  override="$4"
  if [ -n "$override" ]; then
    src="$(cd "$override" && pwd -P)"
    test "$(git -C "$src" rev-parse HEAD)" = "$commit" || exit 4
    echo "$src"
    return 0
  fi
  test ! -e "$directory" || { echo EXISTING_DISPOSABLE_REPO >&2; exit 4; }
  mkdir -p "$directory"
  git -C "$directory" init -q
  git -C "$directory" fetch -q --depth 1 "$remote" "$commit"
  git -C "$directory" checkout -q --detach FETCH_HEAD
  test "$(git -C "$directory" rev-parse HEAD)" = "$commit"
  echo "$directory"
}
lib="$(clone_pinned "$root/libubox-src" https://github.com/openwrt/libubox.git "$libubox_commit" "$libubox_override")"
cmake -S "$lib" -B "$root/libubox-build" \
  -DCMAKE_INSTALL_PREFIX="$prefix" -DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF \
  -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$root/libubox-build" --parallel 2 >/dev/null
cmake --install "$root/libubox-build" >/dev/null
test -x "$prefix/bin/jshn" && test -s "$prefix/share/libubox/jshn.sh" &&
  test -s "$prefix/lib/libubox.so"
ucisrc="$(clone_pinned "$root/uci-src" https://github.com/openwrt/uci.git "$uci_commit" "$uci_override")"
cmake -S "$ucisrc" -B "$root/uci-build" \
  -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_PREFIX_PATH="$prefix" \
  -DCMAKE_INCLUDE_PATH="$prefix/include" -DCMAKE_LIBRARY_PATH="$prefix/lib" \
  -DBUILD_LUA=OFF -DBUILD_STATIC=OFF -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$root/uci-build" --parallel 2 >/dev/null
test -x "$root/uci-build/uci"
old_ld=$(printenv LD_LIBRARY_PATH || :)
export LD_LIBRARY_PATH="$root/uci-build:$prefix/lib:$old_ld"
"$root/uci-build/uci" -V >/dev/null 2>&1
# Environment is read by a following source-test step. Native tests fail,
# never silently skip, if these paths are unavailable.
environment="$root/native-test-env.sh"
{
  printf 'export VECI_HOST_UCI=%q\n' "$root/uci-build/uci"
  printf 'export VECI_LIBUBOX_PREFIX=%q\n' "$prefix"
  printf 'export PATH=%q:$PATH\n' "$prefix/bin"
  printf 'export LD_LIBRARY_PATH=%q\n' "$LD_LIBRARY_PATH"
} > "$environment"
echo HOST_NATIVE_TEST_UCI_PINNED_READY
echo HOST_NATIVE_TEST_LIBUBOX_PINNED_READY
echo NO_FIRMWARE_IMAGE_COMPILED
