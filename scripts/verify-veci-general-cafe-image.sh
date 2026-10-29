#!/bin/sh
# Offline release candidate gate; does NOT authorize hardware flashing.
set -eu
[ "$#" -eq 3 ] || {
  echo 'usage: verify-veci-general-cafe-image.sh <sysupgrade.bin> <manifest> <host-fwtool>' >&2
  exit 2
}
image="$1"
manifest="$2"
fwtool="$3"
[ -s "$image" ] && [ -s "$manifest" ] && [ -x "$fwtool" ] || {
  echo 'STOP: missing image/manifest/host-fwtool' >&2
  exit 3
}
max_bytes=$((7808 * 1024))
bytes="$(wc -c < "$image" | tr -d ' ')"
case "$bytes" in ''|*[!0-9]*) exit 4;; esac
[ "$bytes" -ge 1048576 ] && [ "$bytes" -le "$max_bytes" ] || {
  echo "STOP: firmware size $bytes outside 1MiB..$max_bytes B limit" >&2
  exit 4
}
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT HUP INT TERM
"$fwtool" -i "$tmp" "$image" >/dev/null 2>&1 && [ -s "$tmp" ] || {
  echo 'STOP: firmware has no readable metadata trailer' >&2
  exit 5
}
python3 - "$tmp" "$manifest" <<'PY'
import json, pathlib, sys
meta=json.loads(pathlib.Path(sys.argv[1]).read_text())
expected={'zbtlink,zbt-we5927','zbt-we5927'}
devices=set(meta.get('supported_devices',[]))
version=meta.get('version',{})
if not devices.intersection(expected) or version.get('target')!='ramips/mt76x8':
    raise SystemExit('STOP: firmware board/target metadata mismatch')
installed={}
for line in pathlib.Path(sys.argv[2]).read_text().splitlines():
    if ' - ' not in line: continue
    name, pkgversion=line.split(' - ',1)
    installed[name]=pkgversion
required=('kernel','base-files','dropbear','rpcd','uhttpd','dnsmasq',
 'firewall4','netifd','veci','veci-default-ui','veci-cellular-we5927',
 'veci-app-catalog-we5927','veci-app-guest','veci-app-voucher',
 'uspot','uspot-www','we5927-lte')
missing=[pkg for pkg in required if pkg not in installed]
if missing:
    raise SystemExit('STOP: missing firmware packages '+','.join(missing))
print('BOARD_METADATA=PASS')
print('BUNDLED_APPS_AND_ROUTER_CORE=PASS')
print('KERNEL_PACKAGE='+installed['kernel'])
PY
sha256sum "$image"
printf 'IMAGE_BYTES=%s\n' "$bytes"
echo CANDIDATE_SOURCE_VALIDATION=PASS
echo FLASH_DECISION=NO_GO_UNTIL_HARDWARE_RECOVERY_AND_UAT
