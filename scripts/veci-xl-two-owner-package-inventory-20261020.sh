#!/bin/sh
# Two-owner XL migration: collect only APK metadata and original archive discovery.
# Read-only; no apk add/del, no binaries copied, no customer files touched.
set -eu
LC_ALL=C; export LC_ALL
[ "$(id -u)" = 0 ] || { echo XL_OWNER_INVENTORY=root_required; exit 1; }
command -v apk >/dev/null 2>&1 || { echo XL_OWNER_INVENTORY=apk_missing; exit 1; }
for package in veci-telco-xl-native veci-telco-indonesia; do
 apk info -e "$package" >/dev/null 2>&1 || {
  echo "XL_OWNER_INVENTORY=required_package_missing:$package"
  exit 1
 }
 printf 'XL_OWNER_PACKAGE=%s\n' "$package"
 printf 'XL_OWNER_DEPENDENCIES_BEGIN=%s\n' "$package"
 apk info -R "$package" 2>/dev/null | sed -n '1,50p' || :
 printf 'XL_OWNER_DEPENDENCIES_END=%s\n' "$package"
 printf 'XL_OWNER_MANIFEST_BEGIN=%s\n' "$package"
 # Only paths, not file contents. Limit output deliberately on tiny router.
 list="$(apk info -L "$package" 2>/dev/null)" || {
  echo XL_OWNER_INVENTORY=manifest_query_failed
  exit 1
 }
 entries="$(printf '%s\n' "$list" | wc -l | tr -d '[:space:]')"
 case "$entries" in ''|*[!0-9]*) echo XL_OWNER_INVENTORY=manifest_size_invalid; exit 1 ;; esac
 [ "$entries" -le 160 ] || {
  echo "XL_OWNER_MANIFEST_COUNT=$entries"
  echo XL_OWNER_INVENTORY=manifest_too_large
  exit 1
 }
 printf '%s\n' "$list"
 printf 'XL_OWNER_MANIFEST_END=%s\n' "$package"
 echo "XL_OWNER_MANIFEST_COUNT_$package=$entries"
done
# Specific local archive candidate folders only; no filesystem-wide traversal.
found=0
for directory in /tmp /var/cache/apk /var/cache/apk/archives /root; do
 [ -d "$directory" ] && [ ! -L "$directory" ] || continue
 for pattern in "$directory"/veci-telco-xl-native*.apk "$directory"/veci-telco-indonesia*.apk; do
  [ -f "$pattern" ] && [ ! -L "$pattern" ] || continue
  size="$(wc -c < "$pattern" | tr -d '[:space:]')"
  [ "$size" -gt 0 ] && [ "$size" -le 1048576 ] || continue
  printf 'XL_OWNER_ORIGINAL_APK_CANDIDATE=%s\n' "$pattern"
  printf 'XL_OWNER_ORIGINAL_APK_SHA256=%s\n' "$(sha256sum "$pattern" | cut -d ' ' -f 1)"
  found=$((found + 1))
 done
done
echo "XL_OWNER_ORIGINAL_APK_CANDIDATES=$found"
echo XL_OWNER_INVENTORY=pass
echo XL_OWNER_MUTATION=none
echo XL_OWNER_INSTALL=not_attempted
