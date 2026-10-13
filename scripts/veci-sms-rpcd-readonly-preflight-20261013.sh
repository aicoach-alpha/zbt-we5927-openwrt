#!/bin/sh
# READ-ONLY rpcd executable plugin preflight for actual WE5927.
# Never writes /usr or /etc; never restarts rpcd/LTE, never invokes modem/CMGL.
set -eu
umask 077
LC_ALL=C; export LC_ALL
REPO=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
PIN=cecfe43e99a1bf9b4c7c9c1158432acd44099de5
RPC_SHA=24102a1919856de11a2eb207c57e56b78f85612a50bf71628ff1959edf856a2e

stop() {
  echo "RPCD_PREFLIGHT_ERROR=$1"
  exit 1
}
[ "$#" -eq 0 ] || stop unexpected_arguments
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || stop wrong_board
command -v jsonfilter >/dev/null 2>&1 || stop missing_jsonfilter
command -v ubus >/dev/null 2>&1 || stop missing_ubus
command -v wget >/dev/null 2>&1 || stop missing_wget
tmp="$(mktemp /tmp/veci-rpcd-preflight.XXXXXX)" || stop cannot_stage
trap 'rm -f "$tmp"' EXIT
trap 'exit 130' INT TERM
wget -q -O "$tmp" "$REPO/$PIN/source/veci-sms-inbox-we5927/files/usr/libexec/rpcd/veci.sms" ||
  stop download_failed
sha="$(sha256sum "$tmp" | awk '{print $1}')"
[ "$sha" = "$RPC_SHA" ] || stop wrong_plugin_hash
sh -n "$tmp" || stop invalid_plugin_shell
signature="$(sh "$tmp" list 2>/dev/null)" || stop plugin_list_failed
scope="$(jsonfilter -s "$signature" -e '@.listIndex.scope' 2>/dev/null)" ||
  stop invalid_list_signature
ack="$(jsonfilter -s "$signature" -e '@.listIndex.ack_unread_status' 2>/dev/null)" ||
  stop invalid_list_signature
[ "$scope" = str ] && [ "$ack" = str ] || stop invalid_list_signature
printf '%s\n' 'RPCD_PLUGIN_LIST_CONTRACT_PASS'
printf '%s\n' 'SOURCE_SHA_VERIFIED=true'
printf '%s\n' 'NO_MODEM_COMMANDS_SENT=true'
echo "LIVE_V12_SHA=$(sha256sum /www/veci/js/pages/cellular.js 2>/dev/null | awk '{print $1}')"
if ubus list veci.cellular 2>/dev/null | grep -qx 'veci.cellular'; then
  echo 'EXISTING_CELLULAR_RPC=registered'
else
  echo 'EXISTING_CELLULAR_RPC=not_registered'
fi
if ubus list veci.sms 2>/dev/null | grep -qx 'veci.sms'; then
  echo 'SMS_INBOX_RPC=registered'
else
  echo 'SMS_INBOX_RPC=absent'
fi
if [ -d /root/veci-sms-inbox-v13-rollback ]; then
  backupsha="$(sha256sum /root/veci-sms-inbox-v13-rollback/cellular-v12.js 2>/dev/null | awk '{print $1}')"
  case "$backupsha" in
    2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40)
      echo 'V13_FAILED_INSTALL_BACKUP=valid_v12' ;;
    *) echo 'V13_FAILED_INSTALL_BACKUP=unverified' ;;
  esac
else
  echo 'V13_FAILED_INSTALL_BACKUP=absent'
fi
