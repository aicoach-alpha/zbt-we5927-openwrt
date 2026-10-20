#!/bin/sh
# Read-only ownership handoff decision for live XL Core Policy.
# No APK install, service reload, LTE/SMS/VeCI modification.
set -eu
LC_ALL=C; export LC_ALL
[ "$(id -u)" = 0 ] || { echo XL_CORE_PREFLIGHT=root_required; exit 1; }
for dep in veci-telco-xl-native veci-xl-native-overlay rpcd jsonfilter; do
 if apk info -e "$dep" >/dev/null 2>&1; then
  :
 else
  echo XL_CORE_PREFLIGHT=dependency_missing
  echo "XL_CORE_MISSING_PACKAGE=$dep"
  exit 1
 fi
done
ownership=unowned
count=0
for row in \
 'RPC_XL:/usr/libexec/rpcd/veci.xl' \
 'RPC_QUOTA:/usr/libexec/rpcd/veci.quota' \
 'OWNER_ACL:/usr/share/rpcd/acl.d/veci-xl-owner.json' \
 'SESSION_CLEAR:/usr/libexec/veci-xl-session-clear'; do
 name="$(printf '%s' "$row" | cut -d : -f1)"
 path="$(printf '%s' "$row" | cut -d : -f2-)"
 [ -f "$path" ] && [ ! -L "$path" ] || {
  echo "XL_CORE_$name=missing_or_symlink"
  exit 1
 }
 if apk info -W "$path" >/dev/null 2>&1; then
  echo "XL_CORE_$name=package_owned"
  ownership=conflict
 else
  echo "XL_CORE_$name=unowned"
 fi
 count=$((count + 1))
done
[ "$count" -eq 4 ] || exit 1
if [ "$ownership" = conflict ]; then
 echo XL_CORE_PREFLIGHT=ownership_migration_required
 echo XL_CORE_ACTION=do_not_install_core_apk
else
 echo XL_CORE_PREFLIGHT=core_apk_install_candidate
 echo XL_CORE_ACTION=staged_install_possible_after_signature_and_space_check
fi
