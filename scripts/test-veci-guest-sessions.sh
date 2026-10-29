#!/bin/sh
set -eu
repo="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
backend="$repo/source/veci-app-guest/files/usr/libexec/rpcd/veci.app.guest"
frontend="$repo/source/veci-app-guest/files/www/veci-apps/guest.js"
sh -n "$backend"
node --input-type=module --check < "$frontend"
# Only evaluate the pure validation function; no user sessions or networking touched.
eval "$(sed -n '/^valid_client_mac() {/,/^}/p' "$backend")"
valid_client_mac '02:1A:3b:4C:5D:6e'
! valid_client_mac '02:1A:3b:4C:5D:6e;reboot'
! valid_client_mac '02:1A:3b:4C:5D'
! valid_client_mac '--bad-option'
grep -q '"clients": {}' "$backend"
grep -q '"disconnect": { "address": "str" }' "$backend"
grep -q 'client_not_connected_to_guest' "$backend"
grep -q 'uspot client_remove' "$backend"
grep -q "api.call('veci.app.guest', 'disconnect'" "$frontend"
echo 'VECI_GUEST_SESSION_SOURCE_TEST_PASS'
