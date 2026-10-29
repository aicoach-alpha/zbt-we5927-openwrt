#!/bin/sh
# VeCI v14d — LAN-only HTTP after reboot. HTTPS/LTE/firewall/rpcd untouched.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH
MODE="$1"
CFG=/etc/config/uhttpd
BACK=/etc/config/uhttpd.veci-v14d-before-boot-rebind-20261029
STAGE=/etc/config/.uhttpd.veci-v14d-stage
HOOK=/etc/hotplug.d/iface/95-veci-http-lan-rebind
SVC=/etc/init.d/uhttpd
fail(){ echo "VECI_V14D_ERROR=$1"; exit 1; }
listener_present(){
 awk '$2=="0101A8C0:0050" && $4=="0A"{ok=1} END{exit !ok}' /proc/net/tcp 2>/dev/null
}
check_config(){
 awk '
 function unquote(s){gsub(sprintf("%c",39),"",s);gsub("\"","",s);return s}
 $1=="config"{main=($2=="uhttpd" && unquote($3)=="main");if(main)mains++}
 main && $1=="list" && $2=="listen_https"{https++}
 main && ($1=="list" || $1=="option") && $2=="listen_http"{http++;if(unquote($3)=="192.168.1.1:80")good_http++}
 main && $1=="option" && $2=="redirect_https"{redirects++;if(unquote($3)=="0")redirect0++}
 END{if(mains!=1 || https<1 || redirects!=1 || redirect0!=1 || http>1 || (http==1 && good_http!=1))exit 32}
 ' "$CFG" || fail unexpected_uhttpd_config
}
echo VECI_V14D_STAGE=start
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail unexpected_board
grep -Fqx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail unexpected_firmware
[ -f "$CFG" ] && [ -s "$CFG" ] && [ ! -L "$CFG" ] && [ -x "$SVC" ] && [ -d /etc/hotplug.d/iface ] || fail prerequisites_missing
case "$MODE" in
 --status)
  check_config
  if listener_present;then echo VECI_V14D_TCP80=listen;else echo VECI_V14D_TCP80=absent;fi
  if [ -x "$HOOK" ] && [ ! -L "$HOOK" ];then echo VECI_V14D_HOOK=installed;else echo VECI_V14D_HOOK=absent;fi
  echo VECI_V14D_PRODUCTION=unchanged
  exit 0 ;;
 --rollback)
  [ -s "$BACK" ] && [ ! -L "$BACK" ] && [ -f "$HOOK" ] && [ ! -L "$HOOK" ] || fail backup_or_hook_missing
  rm -f "$HOOK" || fail rollback_hook_failed
  cp -p "$BACK" "$CFG" || fail rollback_copy_failed
  "$SVC" restart || fail rollback_restart_failed
  echo VECI_V14D_ROLLBACK=restored
  exit 0 ;;
 --apply) ;;
 *) fail invalid_mode ;;
esac
check_config
[ ! -e "$BACK" ] && [ ! -L "$BACK" ] && [ ! -e "$STAGE" ] && [ ! -L "$STAGE" ] &&
 [ ! -e "$HOOK" ] && [ ! -L "$HOOK" ] || fail previous_transaction_requires_review
# Never replace a wildcard or another service's TCP/80 binding.
if awk '$2 ~ /:0050$/ && $4=="0A" && $2!="0101A8C0:0050"{x=1} END{exit !x}' /proc/net/tcp;then fail unexpected_port80_owner;fi
echo VECI_V14D_STAGE=backup_original
cp -p "$CFG" "$BACK" || fail backup_failed
chmod 600 "$BACK"
if ! grep -Eq "^[[:space:]]*(list|option)[[:space:]]+listen_http[[:space:]]+['\"]?192[.]168[.]1[.]1:80['\"]?" "$CFG";then
 echo VECI_V14D_STAGE=add_missing_lan_http
 awk '
 function unquote(s){gsub(sprintf("%c",39),"",s);gsub("\"","",s);return s}
 $1=="config" && $2=="uhttpd" && unquote($3)=="main"{
  print;print "\tlist listen_http " sprintf("%c",39) "192.168.1.1:80" sprintf("%c",39);n++;next
 }
 {print}
 END{if(n!=1)exit 32}
 ' "$CFG" >"$STAGE" || fail stage_failed
 chmod 600 "$STAGE"
 mv "$STAGE" "$CFG" || fail replace_failed
fi
echo VECI_V14D_STAGE=install_persistent_lan_hotplug
cat >"$HOOK" <<'HOTPLUG'
#!/bin/sh
# Only LAN ready events; retry port bind only when exact socket missing.
case "$ACTION" in ifup|ifupdate) ;; *) exit 0;; esac
[ "$INTERFACE" = lan ] || exit 0
[ -f /etc/config/uhttpd ] && [ -x /etc/init.d/uhttpd ] || exit 0
pidof uhttpd >/dev/null 2>&1 || exit 0
awk '$2=="0101A8C0:0050" && $4=="0A"{ok=1} END{exit !ok}' /proc/net/tcp 2>/dev/null && exit 0
LOCK=/tmp/veci-http-lan-rebind.lock
mkdir "$LOCK" 2>/dev/null || exit 0
trap 'rmdir "$LOCK" 2>/dev/null || :' EXIT
awk '$2=="0101A8C0:0050" && $4=="0A"{ok=1} END{exit !ok}' /proc/net/tcp 2>/dev/null && exit 0
/etc/init.d/uhttpd restart >/dev/null 2>&1 || logger -t veci-http-lan-rebind 'LAN HTTP restart failed'
HOTPLUG
chmod 755 "$HOOK" || fail hook_permissions_failed
echo VECI_V14D_STAGE=restart_uhttpd_once
if ! "$SVC" restart;then
 rm -f "$HOOK" || :
 cp -p "$BACK" "$CFG" || fail restore_failed
 "$SVC" restart || :
 fail restart_failed_original_restored
fi
echo VECI_V14D_STAGE=one_integrity_gate
check_config
[ -x "$HOOK" ] && [ ! -L "$HOOK" ] || fail persistent_hook_missing
if ! listener_present;then
 echo VECI_V14D_STAGE=http_listener_missing_rollback
 rm -f "$HOOK" || :
 cp -p "$BACK" "$CFG" || fail failed_integrity_restore_config_failed
 "$SVC" restart || fail failed_integrity_restore_https_failed
 fail http_listener_absent_original_restored
fi
pidof uhttpd >/dev/null 2>&1 || fail uhttpd_not_running
echo VECI_V14D_HTTP=192.168.1.1:80
echo VECI_V14D_HTTPS=preserved
echo VECI_V14D_BOOT_RECOVERY=lan_hotplug_installed
echo VECI_V14D_INTEGRITY=pass
echo VECI_V14D_RELEASE=live_config_pass
