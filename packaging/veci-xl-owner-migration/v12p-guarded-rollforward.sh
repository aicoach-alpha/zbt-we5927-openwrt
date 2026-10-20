#!/bin/sh
# VeCI v12p: signed offline feed roll-forward for TWO existing package owners.
# No firmware, other-package, LTE, SMS, or XL-auth changes.
set -eu
umask 077
ACTION="$1"
XL=veci-telco-xl-native
ID=veci-telco-indonesia
FEED=/etc/apk/veci-xl-feed
REPOS=/etc/apk/repositories.d/90-veci-xl-local.list
STAGE=/tmp/veci-xl-v12p
NEW="$STAGE/feed"
BACKUP=/etc/apk/veci-xl-v12p-backup
fail(){ echo "XL_V12P_ERROR=$1"; exit 1; }
safe(){ [ -s "$1" ] && [ -f "$1" ] && [ ! -L "$1" ]; }
sha(){ sha256sum "$1" | cut -d ' ' -f1; }
installed(){
 apk list -I 2>/dev/null | awk -v n="$1-" '$NF=="[installed]" && index($1,n)==1 {print substr($1,length(n)+1)}'
}
others(){
 apk list -I 2>/dev/null | awk -v x="$XL-" -v i="$ID-" '$NF=="[installed]" && index($1,x)!=1 && index($1,i)!=1 {print $1}' | sort
}
field(){
 [ "$(grep -c "^$1=" "$STAGE/release-receipt.txt" || :)" = 1 ] || fail invalid_receipt
 sed -n "s/^$1=//p" "$STAGE/release-receipt.txt"
}
signed(){ apk --no-network --keys-dir /etc/apk/keys verify "$1" >/dev/null || fail untrusted_release; }
restore(){
 echo XL_V12P_ROLLBACK=attempting
 [ -d "$BACKUP/feed" ] && [ -d "$FEED" ] || fail manual_recovery_required
 mv "$FEED" "$STAGE/failed-feed" || fail failed_feed_preservation_failed
 mv "$BACKUP/feed" "$FEED" || fail old_feed_restoration_failed
 ox="$(cat "$BACKUP/native.before")"; oi="$(cat "$BACKUP/indonesia.before")"
 if ! apk --no-network --keys-dir /etc/apk/keys add "$FEED/$XL-$ox.apk" "$FEED/$ID-$oi.apk"; then
  fail rollback_package_install_failed
 fi
 apk --no-network --keys-dir /etc/apk/keys add "$XL" "$ID" || fail rollback_world_normalize_failed
 cp -p "$BACKUP/world.before" /etc/apk/world || fail rollback_world_restore_failed
 [ "$(installed "$XL")" = "$ox" ] && [ "$(installed "$ID")" = "$oi" ] &&
 cmp -s "$BACKUP/world.before" /etc/apk/world &&
 others | cmp -s "$BACKUP/other.before" - || fail rollback_integrity_failed
 echo XL_V12P_ROLLBACK=versions_world_and_feed_restored
}
[ "$(id -u)" = 0 ] || fail root_required
[ -f "$REPOS" ] && [ "$(cat "$REPOS")" = 'ndx file:///etc/apk/veci-xl-feed/Packages.adb' ] || fail unexpected_repository
[ -d "$FEED" ] && [ ! -L "$FEED" ] || fail feed_missing
case "$ACTION" in
 rollback)
   [ -d "$BACKUP" ] || fail rollback_snapshot_missing
   [ -d "$STAGE" ] || mkdir -m 700 "$STAGE"
   restore
   exit 0 ;;
 apply) ;;
 *) fail unsupported_action ;;
esac
[ -d "$NEW" ] && [ ! -L "$NEW" ] && safe "$STAGE/release-receipt.txt" || fail release_not_staged
nv="$(field native_version)"; iv="$(field indonesia_version)"
nh="$(field native_sha256)"; ih="$(field indonesia_sha256)"; ndx="$(field index_sha256)"
for ver in "$nv" "$iv"; do
 printf '%s\n' "$ver" | grep -Eq '^[0-9]+[.][0-9]+[.][0-9]+-r[0-9]+$' || fail invalid_version
done
for hash in "$nh" "$ih" "$ndx"; do
 printf '%s\n' "$hash" | grep -Eq '^[0-9a-f]{64}$' || fail invalid_hash
done
nx="$XL-$nv.apk"; ni="$ID-$iv.apk"
safe "$NEW/$nx" && safe "$NEW/$ni" && safe "$NEW/Packages.adb" || fail release_assets_missing
[ "$(sha "$NEW/$nx")" = "$nh" ] && [ "$(sha "$NEW/$ni")" = "$ih" ] &&
[ "$(sha "$NEW/Packages.adb")" = "$ndx" ] || fail release_digest_mismatch
signed "$NEW/$nx"; signed "$NEW/$ni"; signed "$NEW/Packages.adb"
ox="$(installed "$XL")"; oi="$(installed "$ID")"
[ -n "$ox" ] && [ -n "$oi" ] || fail installed_versions_unknown
safe "$FEED/$XL-$ox.apk" && safe "$FEED/$ID-$oi.apk" || fail old_rollback_apks_missing
if [ "$nv" = "$ox" ] && [ "$nh" != "$(sha "$FEED/$XL-$ox.apk")" ]; then fail native_same_version_repacked; fi
if [ "$iv" = "$oi" ] && [ "$ih" != "$(sha "$FEED/$ID-$oi.apk")" ]; then fail indonesia_same_version_repacked; fi
if [ "$nv" = "$ox" ] && [ "$iv" = "$oi" ]; then
 echo XL_V12P_ACTION=noop_same_versions
 echo XL_V12P_PRODUCTION=unchanged
 exit 0
fi
[ ! -e "$BACKUP" ] && [ ! -L "$BACKUP" ] || fail previous_backup_exists
printf 'ndx file://%s/Packages.adb\n' "$NEW" > "$STAGE/plan.list"
if ! apk --no-network --keys-dir /etc/apk/keys --repositories-file "$STAGE/plan.list" \
 upgrade --simulate "$XL" "$ID" > "$STAGE/plan.log" 2>&1; then
 cat "$STAGE/plan.log"; fail solver_failed
fi
cat "$STAGE/plan.log"
awk -v x="$XL" -v i="$ID" -v ox="$ox" -v oi="$oi" -v nx="$nv" -v ni="$iv" '
/^\([0-9]+\/[0-9]+\)/ {
 if ($2!="Upgrading" || ($3!=x && $3!=i) || $5!="->") bad=1
 a=$4; b=$6; sub(/^\(/,"",a); sub(/\)$/,"",b)
 if ($3==x && (++cx>1 || a!=ox || b!=nx)) bad=1
 if ($3==i && (++ci>1 || a!=oi || b!=ni)) bad=1
}
END {if (bad || cx!=(ox!=nx) || ci!=(oi!=ni)) exit 1}
' "$STAGE/plan.log" || fail solver_proposes_out_of_scope_change
grep -q '^OK: ' "$STAGE/plan.log" || fail solver_success_receipt_missing
echo XL_V12P_SIMULATION=target_only
free="$(df -k /overlay | tail -n1 | awk '{print $4}')"
case "$free" in ''|*[!0-9]*) fail free_space_unavailable ;; esac
[ "$free" -ge 384 ] || fail overlay_space_low
mkdir -m 700 "$BACKUP" || fail snapshot_create_failed
cp -p /etc/apk/world "$BACKUP/world.before" || fail world_snapshot_failed
printf '%s\n' "$ox" > "$BACKUP/native.before"
printf '%s\n' "$oi" > "$BACKUP/indonesia.before"
others > "$BACKUP/other.before"
mkdir -m 755 "$STAGE/feed.next" || fail next_feed_exists
cp -p "$NEW/$nx" "$NEW/$ni" "$NEW/Packages.adb" "$STAGE/feed.next/" || fail stage_copy_failed
mv "$FEED" "$BACKUP/feed" || fail old_feed_preserve_failed
if ! mv "$STAGE/feed.next" "$FEED"; then
 mv "$BACKUP/feed" "$FEED" || :
 fail repository_swap_failed
fi
if ! apk --no-network --keys-dir /etc/apk/keys --repositories-file "$STAGE/plan.list" upgrade "$XL" "$ID"; then
 restore; fail upgrade_failed_rolled_back
fi
if [ "$(installed "$XL")" != "$nv" ] || [ "$(installed "$ID")" != "$iv" ] ||
 ! cmp -s "$BACKUP/world.before" /etc/apk/world ||
 ! others | cmp -s "$BACKUP/other.before" - ||
 [ "$(sha "$FEED/Packages.adb")" != "$ndx" ]; then
 restore; fail integrity_failed_rolled_back
fi
echo XL_V12P_RELEASE=installed
echo XL_V12P_INTEGRITY=pass
echo XL_V12P_WORLD=unchanged
echo XL_V12P_PACKAGE_SCOPE=two
echo XL_V12P_ROLLBACK=backup_retained
