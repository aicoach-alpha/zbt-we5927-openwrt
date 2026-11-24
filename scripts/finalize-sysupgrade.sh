#!/bin/sh
# Verify and copy an already metadata-complete image. Never invent metadata.
# Source pin: OpenWrt 25.12.6 / ramips/mt76x8 / zbtlink,zbt-we5927.
set -eu
if [ "$#" -ne 3 ]; then
  echo "usage: $0 <metadata-complete-sysupgrade.bin> <new-output.bin> <host-fwtool>" >&2
  exit 2
fi
src="$1"
out="$2"
fwtool="$3"
[ "$src" != "$out" ] || { echo 'source_equals_destination' >&2; exit 2; }
[ -f "$src" ] && [ ! -L "$src" ] && [ ! -e "$out" ] && [ ! -L "$out" ] ||
  { echo 'invalid_source_or_existing_destination' >&2; exit 2; }
[ -x "$fwtool" ] || { echo 'host_fwtool_missing' >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo 'python3_required' >&2; exit 2; }
tmp_meta="$(mktemp)"
trap 'rm -f "$tmp_meta"' EXIT HUP INT TERM
# Incomplete or malformed metadata MUST fail. Never append a generic board,
# stale OpenWrt revision or unverified compatibility claim to a raw binary.
"$fwtool" -i "$tmp_meta" "$src" >/dev/null 2>&1 ||
  { echo 'fwtool_metadata_missing_or_invalid' >&2; exit 3; }
python3 - "$tmp_meta" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1])
meta=json.loads(p.read_text(encoding="utf-8"))
version=meta.get("version") or {}
assert version.get("target") == "ramips/mt76x8", "target mismatch"
assert version.get("version") == "25.12.6", "release mismatch"
assert "zbtlink,zbt-we5927" in meta.get("supported_devices", []), "board mismatch"
print("PINNED_BOARD_AND_VERSION_METADATA=PASS")
PY
bytes="$(wc -c < "$src")"
[ "$bytes" -gt 0 ] && [ "$bytes" -le 7995392 ] ||
  { echo "firmware_partition_overflow_or_empty:$bytes" >&2; exit 3; }
cp "$src" "$out"
cmp -s "$src" "$out" || { rm -f "$out"; echo 'copy_mismatch' >&2; exit 3; }
echo "METADATA_VERIFIED_IMAGE_COPIED_NO_SIGNING_NO_FLASH=$out"
sha256sum "$out"
