#!/bin/sh
# VeCI WE5927 generic USSD RPC NO_DATA probe. NEVER SENDS USSD.
# The only 'start' request contains INVALID alphabetic code. The pinned RPC
# SHA256 proves the installed plugin rejects this before running the worker.
set -eu
umask 077
LC_ALL=C; PATH=/usr/sbin:/usr/bin:/sbin:/bin; export LC_ALL PATH
PLUGIN=/usr/libexec/rpcd/veci.dialer
WORKER=/usr/libexec/veci-ussd-dialer
RPC_SHA=ca1aa890fc64f7caaf72f577cb8f04b3dcd12527389eb7df464c2fc632c2e251
WORKER_SHA=37b3f3c0d50179f8d4dc11d8dec8f3c123acc52f29ac614745c75abbef44e0f5
CORE_SHA=d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce
TEMP=
fail(){ echo VECI_USSD_NODATA_PREFLIGHT=blocked; echo "VECI_USSD_NODATA_REASON=$1"; exit 1; }
digest(){ sha256sum "$1" | awk '{print $1}'; }
safe(){ [ -f "$1" ] && [ ! -L "$1" ] && [ -x "$1" ] && [ "$(digest "$1")" = "$2" ]; }
cleanup(){ [ -n "$TEMP" ] && [ -d "$TEMP" ] && rm -rf "$TEMP" || :; }
trap cleanup EXIT
[ "$#" = 1 ] && [ "$1" = --diagnose ] || fail usage
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
safe "$PLUGIN" "$RPC_SHA" || fail rpc_plugin_changed
safe "$WORKER" "$WORKER_SHA" || fail worker_changed
[ "$(digest /usr/libexec/rpcd/veci 2>/dev/null || :)" = "$CORE_SHA" ] || fail core_rpc_changed
[ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ] || fail http_listener_enabled
ubus -S list veci.dialer 2>/dev/null | grep -qx veci.dialer || fail rpc_not_registered
# A bad dial string is rejected by the exact verified RPC shell BEFORE emit.
# Never pass a valid USSD code, dial choice, AT command, or SIM identifier.
BAD_CODE=NOT_A_USSD_DIAL
BODY='{"code":"NOT_A_USSD_DIAL","approval":"I_APPROVE_THIS_USSD_DIAL"}'
TEMP="$(mktemp -d /tmp/veci-ussd-nodata.XXXXXX)" || fail temp_unavailable
direct_rc=0
printf '%s' "$BODY" | "$PLUGIN" call start >"$TEMP/direct.out" 2>/dev/null || direct_rc="$?"
direct_reason="$(jsonfilter -s "$(cat "$TEMP/direct.out")" -e '@.reason' 2>/dev/null || :)"
if [ "$direct_reason" = invalid_dial ] && [ "$direct_rc" = 0 ]; then
 echo VECI_USSD_NODATA_DIRECT_PLUGIN=invalid_dial_guard_pass
else
 echo VECI_USSD_NODATA_DIRECT_PLUGIN=unexpected_or_no_json
 echo "VECI_USSD_NODATA_DIRECT_EXIT=$direct_rc"
fi
# If the direct fake request failed fail-closed, DO NOT invoke ubus start.
[ "$direct_reason" = invalid_dial ] && [ "$direct_rc" = 0 ] || fail fake_input_safety_not_confirmed
status_rc=0
ubus -S call veci.dialer status >"$TEMP/status.out" 2>/dev/null || status_rc="$?"
status_ready="$(jsonfilter -s "$(cat "$TEMP/status.out")" -e '@.ready' 2>/dev/null || :)"
if [ "$status_rc" = 0 ] && [ "$status_ready" = true ]; then
 echo VECI_USSD_NODATA_STATUS_RPC=pass
else
 echo VECI_USSD_NODATA_STATUS_RPC=failed
 echo "VECI_USSD_NODATA_STATUS_EXIT=$status_rc"
fi
# The only ubus 'start' is guaranteed invalid, with no path to the modem.
ubus_rc=0
ubus -S call veci.dialer start "$BODY" >"$TEMP/ubus.out" 2>/dev/null || ubus_rc="$?"
ubus_reason="$(jsonfilter -s "$(cat "$TEMP/ubus.out")" -e '@.reason' 2>/dev/null || :)"
if [ "$ubus_rc" = 0 ] && [ "$ubus_reason" = invalid_dial ]; then
 echo VECI_USSD_NODATA_UBUS_FAKE_START=guard_pass
else
 echo VECI_USSD_NODATA_UBUS_FAKE_START=failed
 echo "VECI_USSD_NODATA_UBUS_EXIT=$ubus_rc"
fi
echo VECI_USSD_NODATA_MODEM_REQUESTS=none
echo VECI_USSD_NODATA_REAL_USSD_SENT=false
echo VECI_USSD_NODATA_LUCI_CHANGED=false
echo VECI_USSD_NODATA_PREFLIGHT=pass
