#!/bin/sh
# VeCI v1.6.1 immutable INACTIVE staging only. No live component replacement.
# Actions: status, stage, rollback. No enable/activate command by design.
set -eu
umask 077
LC_ALL=C;export LC_ALL
RELEASE_SHA=4f8b5070443bf0eebf036d502d2ff0f852ffa32c
BUNDLE_SHA=351ae4c239f37d62e4e2694dcdc487d763acd9bf7a5ac386e6e94bec06a68738
URL=https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-sms-v161-stage-4f8b5070443b/veci-v161-stage.tar.gz
STAGE=/root/veci-v161-stage
UI=/www/veci/js/pages/cellular.js
BIN=/usr/libexec/veci-sms-cmgs
CSS=/www/veci/sms-center.css
RPC=/usr/libexec/rpcd/veci.sms
ACL=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
SEND=/usr/libexec/veci-sms-send-one
FLAG=/etc/veci-sms-feature
SENT=/etc/veci-sms-sent-history
DRAFT=/etc/veci-sms-drafts

fail(){ printf 'VECI_V161_STAGE_ERROR=%s\n' "$1" >&2;exit 1; }
sha(){ sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
board(){
  [ "$(id -u)" = 0 ] || fail root_required
  [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_board
  [ "$(uname -r)" = 6.12.94 ] || fail unexpected_kernel
}
live_ok(){
  [ "$(sha "$UI")" = be7706e19a6e1548cfb63a1e29c95da5ce67a8934f274bbd44d4edfd9aea2aef ] &&
  [ "$(sha "$BIN")" = ccb6f066f0be2fa0fbb5131a98f90ded88e28ae0442a57d0d73b1949b07016fb ] &&
  [ "$(sha "$CSS")" = fd3b3540109d815d9b3cb5151298af04ef865e55557d8a8a91d9c30f1548fdb2 ] &&
  [ "$(sha "$RPC")" = 669c6d753f14eb7c8b7d77c1aea28059eb25e20f71511efa301942707f1e0615 ] &&
  [ "$(sha "$ACL")" = 827fd96f101ece20e6a4e307cc82fb4d3a463989c2cd4b09cdc72cd8d9a2193c ] &&
  [ "$(sha "$SEND")" = 51c13afc282936ae0e1d06692ce9df2d0a310058499ac6961ba8cd622f55efeb ] &&
  [ -f "$FLAG" ] && [ ! -L "$FLAG" ] &&
  [ -f "$SENT" ] && [ ! -L "$SENT" ] &&
  [ -f "$DRAFT" ] && [ ! -L "$DRAFT" ]
}
manifest_in(){
  root="$1"
  [ -d "$root" ] && [ ! -L "$root" ] || return 1
  [ -f "$root/SHA256SUMS" ] && [ ! -L "$root/SHA256SUMS" ] || return 1
  [ -f "$root/RELEASE_INFO" ] && [ ! -L "$root/RELEASE_INFO" ] || return 1
  grep -Fxq "SOURCE_COMMIT=$RELEASE_SHA" "$root/RELEASE_INFO" || return 1
  grep -Fxq 'NO_AUTO_ACTIVATION=1' "$root/RELEASE_INFO" || return 1
  (cd "$root" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
  for f in cellular.js rpcd-veci.sms veci-sms-cmgs veci-sms-status-report \
           veci-sms-send-one veci-sms-delivery-map veci-sms-sent-delivery-view \
           veci-sms-report-ingest;do
    [ -f "$root/$f" ] && [ ! -L "$root/$f" ] || return 1
  done
}
manifest_ok(){ manifest_in "$STAGE"; }
status(){
  board
  if live_ok;then echo 'VECI_V160_LIVE_FILE_INTEGRITY=pass'
  else echo 'VECI_V160_LIVE_FILE_INTEGRITY=unrecognized';fi
  if manifest_ok;then echo 'VECI_V161_INACTIVE_STAGE=verified'
  else echo 'VECI_V161_INACTIVE_STAGE=absent_or_invalid';fi
  echo 'VECI_V161_ACTIVATED=false'
  echo 'MODEM_COMMANDS=false'
  echo 'SMS_SENT_READ_DELETED=false'
  echo 'ROUTER_REBOOT_OR_SERVICE_RESTART=false'
}
stage(){
  board
  live_ok || fail live_baseline_changed
  if manifest_ok;then echo 'VECI_V161_STAGE_ALREADY_PRESENT_PASS';status;return;fi
  [ ! -e "$STAGE" ] && [ ! -L "$STAGE" ] || fail stage_present_unrecognized
  for tool in wget tar mktemp sha256sum awk df grep cp mv chmod;do
    command -v "$tool" >/dev/null 2>&1 || fail missing_tool
  done
  free="$(df -k /overlay | awk 'NR==2{print $4}')"
  case "$free" in ''|*[!0-9]*) fail overlay_unknown;;esac
  [ "$free" -ge 600 ] || fail overlay_too_small
  original="$(cat "$FLAG" 2>/dev/null || :)"
  case "$original" in 0|1);;*)fail invalid_feature_switch;;esac
  work="$(mktemp -d /tmp/veci-stage.XXXXXX)" || fail temp_unavailable
  dest="/root/.veci-v161-stage.$$"
  [ ! -e "$dest" ] && [ ! -L "$dest" ] || fail temp_collision
  complete=0
  cleanup(){
    rc=$?;trap - EXIT
    rm -rf "$work"
    if [ "$complete" != 1 ];then rm -rf "$dest";fi
    exit "$rc"
  }
  trap cleanup EXIT
  trap 'exit 130' INT TERM
  wget -qO "$work/bundle.tar.gz" "$URL" || fail bundle_download
  [ "$(sha "$work/bundle.tar.gz")" = "$BUNDLE_SHA" ] || fail bundle_checksum
  tar -xzf "$work/bundle.tar.gz" -C "$work" || fail bundle_extract
  [ -d "$work/veci-v161" ] && [ ! -L "$work/veci-v161" ] || fail bundle_layout
  mkdir -m 700 "$dest" || fail stage_prepare
  cp -p "$work/veci-v161/"* "$dest/" || fail stage_copy
  chmod 700 "$dest" || fail stage_permission
  [ "$(cat "$FLAG" 2>/dev/null || :)" = "$original" ] || fail switch_changed
  live_ok || fail live_changed_during_stage
  manifest_in "$dest" || fail stage_integrity_before_commit
  mv "$dest" "$STAGE" || fail stage_commit
  complete=1
  manifest_ok || fail stage_integrity_after_commit
  echo 'VECI_V161_INACTIVE_STAGING_PASS'
  status
}
rollback(){
  board
  manifest_ok || fail stage_not_verified
  live_ok || fail live_baseline_changed
  rm -f "$STAGE"/cellular.js "$STAGE"/rpcd-veci.sms \
    "$STAGE"/veci-sms-cmgs "$STAGE"/veci-sms-status-report \
    "$STAGE"/veci-sms-send-one "$STAGE"/veci-sms-delivery-map \
    "$STAGE"/veci-sms-sent-delivery-view "$STAGE"/veci-sms-report-ingest \
    "$STAGE"/SHA256SUMS "$STAGE"/RELEASE_INFO || fail rollback_files
  rmdir "$STAGE" || fail rollback_unexpected_files
  echo 'VECI_V161_INACTIVE_STAGING_ROLLBACK_PASS'
  status
}
[ "$#" -eq 1 ] || fail usage
case "$1" in
  status) status;;
  stage) stage;;
  rollback) rollback;;
  *)fail invalid_action;;
esac
