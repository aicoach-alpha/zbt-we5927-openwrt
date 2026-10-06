#!/bin/sh
set -eu

if [ "$#" -ne 3 ]; then
	echo "usage: $0 <raw-sysupgrade.bin> <output-sysupgrade.bin> <host-fwtool>"
	exit 2
fi

src="$1"
out="$2"
fwtool="$3"
tmp_meta="$(mktemp)"
tmp_check="$(mktemp)"
trap 'rm -f "$tmp_meta" "$tmp_check"' EXIT

cat >"$tmp_meta" <<'EOF'
{"metadata_version":"1.1","compat_version":"1.0","supported_devices":["zbtlink,zbt-we5927","zbt-we5927"],"version":{"dist":"OpenWrt","version":"25.12.5","revision":"r33051-f5dae5ece4","target":"ramips/mt76x8","board":"zbtlink_zbt-we5927"}}
EOF

cp "$src" "$out"

# Some local build paths produced a raw image without the fwtool trailer.
# Append metadata only when no usable metadata trailer is already present.
: >"$tmp_check"
"$fwtool" -i "$tmp_check" "$out" >/dev/null 2>&1 || true
if [ ! -s "$tmp_check" ]; then
	"$fwtool" -I "$tmp_meta" "$out"
fi

: >"$tmp_check"
"$fwtool" -i "$tmp_check" "$out" >/dev/null 2>&1 || true
[ -s "$tmp_check" ] || {
	echo "ERROR: metadata trailer still missing" >&2
	exit 1
}

echo "Finalized: $out"
sha256sum "$out"
