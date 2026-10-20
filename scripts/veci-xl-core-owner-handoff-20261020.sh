#!/bin/sh
# VeCI XL Core ownership handoff: read-only, no install or service changes.
# Provides exact APK package ownership for the three blocked RPC/ACL paths.
set -eu
LC_ALL=C
export LC_ALL
fail() { echo "XL_CORE_OWNER=$1"; exit 1; }
[ "$(id -u)" = 0 ] || fail root_required
command -v apk >/dev/null 2>&1 || fail apk_missing
count=0
owners=
for record in \
  'RPC_XL:/usr/libexec/rpcd/veci.xl' \
  'RPC_QUOTA:/usr/libexec/rpcd/veci.quota' \
  'OWNER_ACL:/usr/share/rpcd/acl.d/veci-xl-owner.json'; do
  label="${record%%:*}"
  path="${record#*:}"
  [ -f "$path" ] && [ ! -L "$path" ] || fail missing_or_symlink
  entry="$(apk info -W "$path" 2>/dev/null)" || fail apk_owner_lookup_failed
  case "$entry" in
    *' is owned by '*) owner="${entry##* is owned by }" ;;
    *) fail unexpected_owner_format ;;
  esac
  [ -n "$owner" ] || fail owner_missing
  printf 'XL_CORE_%s_OWNER=%s\n' "$label" "$owner"
  owners="$(printf '%s\n%s\n' "$owners" "$owner")"
  count=$((count+1))
done
[ "$count" -eq 3 ] || fail incomplete
distinct="$(printf '%s\n' "$owners" | sed '/^$/d' | sort -u | wc -l | tr -d '[:space:]')"
case "$distinct" in
  1) echo XL_CORE_OWNERSHIP_PLAN=rebuild_existing_owner_package ;;
  2|3) echo XL_CORE_OWNERSHIP_PLAN=rebuild_each_existing_owner_package ;;
  *) fail invalid_owner_count ;;
esac
# Current package status only. Never read subscriber config or secrets.
for package in veci-telco-xl-native veci-telco-indonesia veci-xl-native-overlay veci-xl-core-policy; do
  if apk info -e "$package" >/dev/null 2>&1; then
    echo "XL_CORE_PKG_$package=installed"
  else
    echo "XL_CORE_PKG_$package=not_installed"
  fi
done
echo XL_CORE_OWNER=pass
echo XL_CORE_MUTATION=none
echo XL_CORE_INSTALL=blocked_until_owner_migration
