#!/bin/sh
# Apply to unpacked veci-data-meter source/staging tree BEFORE APK signing.
# Does not touch a live router.
set -eu
[ "$#" -eq 1 ] || { echo 'usage: sh fix-meter-rpc-argv.sh /path/to/package-root'; exit 2; }
target="$1/usr/libexec/rpcd/veci.meter"
[ -f "$target" ] && [ ! -L "$target" ] || { echo METER_PATCH=missing_target; exit 1; }
if grep -Fq 'case "${1:-}:${2:-}" in' "$target"; then
  echo METER_PATCH=already_applied
  exit 0
fi
[ "$(grep -Fc 'case "$1:$2" in' "$target")" -eq 1 ] || { echo METER_PATCH=unexpected_source; exit 1; }
sed 's/case "\$1:\$2" in/case "${1:-}:${2:-}" in/' "$target" > "$target.fixed"
if ! sh -n "$target.fixed"; then rm -f "$target.fixed"; echo METER_PATCH=syntax_failed; exit 1; fi
cat "$target.fixed" > "$target"
rm -f "$target.fixed"
chmod 0755 "$target"
echo METER_PATCH=pass
