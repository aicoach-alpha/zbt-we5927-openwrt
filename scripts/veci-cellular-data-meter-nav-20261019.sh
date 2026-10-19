#!/bin/sh
# Add Data Meter shortcut to VeCI Cellular view only.
set -eu
FILE=/www/veci/js/pages/cellular.js
BACKUP=/tmp/veci-cellular-before-meter-link.js
[ "$(id -u)" = 0 ] || { echo VECI_METER_NAV=root_required; exit 1; }
[ -f "$FILE" ] && [ ! -L "$FILE" ] || { echo VECI_METER_NAV=missing_source; exit 1; }
if grep -Fq 'href="/veci/data-meter.html"' "$FILE"; then
  echo VECI_METER_NAV=already_present
  exit 0
fi
[ "$(grep -Fc 'root.innerHTML = `' "$FILE")" -eq 1 ] || { echo VECI_METER_NAV=unexpected_template; exit 1; }
[ ! -e "$BACKUP" ] || { echo VECI_METER_NAV=backup_exists; exit 1; }
cp -p "$FILE" "$BACKUP"
TMP=/tmp/veci-cellular-meter-nav.$$
trap 'rm -f "$TMP"' EXIT
awk '
{ print }
index($0,"root.innerHTML = `") {
 print "                        <div class=\"veci-meter-entry\"><a class=\"button button-secondary\" href=\"/veci/data-meter.html\">Data Meter · Pemakaian Internet</a></div>"
}' "$FILE" > "$TMP"
grep -Fq 'href="/veci/data-meter.html"' "$TMP" || { echo VECI_METER_NAV=build_failed; exit 1; }
cat "$TMP" > "$FILE"
echo VECI_METER_NAV=installed
echo VECI_METER_NAV_BACKUP="$BACKUP"
echo VECI_METER_NAV_URL=https://192.168.1.1/veci/data-meter.html
