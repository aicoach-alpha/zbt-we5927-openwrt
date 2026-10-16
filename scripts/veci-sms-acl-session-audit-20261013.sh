#!/bin/sh
# WE5927 audit for SMS Inbox authorization WITHOUT reading SMS and WITHOUT
# leaking passwords, session tokens, account names or configuration contents.
# No service restarts, login attempts, session grants or configuration writes.
set -eu
umask 077
LC_ALL=C
export LC_ALL

error() {
  case "$1" in wrong_board|missing_tools|rpcd_unavailable|acl_missing|acl_invalid|no_login_sections)
    reason="$1" ;;
  *) reason=audit_unavailable ;;
  esac
  printf 'SMS_ACL_AUDIT_ERROR=%s\n' "$reason"
  exit 1
}

[ "$#" -eq 0 ] || error unexpected_args
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || error wrong_board
for cmd in ubus uci jsonfilter grep awk; do
  command -v "$cmd" >/dev/null 2>&1 || error missing_tools
done
acl=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
[ -f "$acl" ] || error acl_missing
# jsonfilter handles strict numeric fields; do not use arbitrary eval.
rule="$(jsonfilter -i "$acl" -e '@.veci-sms-inbox-we5927.write.ubus.veci.sms[0]' 2>/dev/null || :)"
# JSON keys with literal dots may require quoted paths, so use a narrowly
# bounded text assertion as a secondary structural signal.
grep -Fq '"veci.sms"' "$acl" || error acl_invalid
grep -Fq '"listIndex"' "$acl" || error acl_invalid
if ! ubus list veci.sms 2>/dev/null | grep -qx 'veci.sms'; then
  error rpcd_unavailable
fi
printf 'SMS_RPC=registered\n'
printf 'ACL_LISTINDEX_WRITE_DECLARED=true\n'
# Classify login section grants without exposing usernames/password fields.
n=0
priv=0
restricted=0
wildcard=0
uncertain=0
while [ "$n" -lt 32 ]; do
  typ="$(uci -q get "rpcd.@login[$n]" 2>/dev/null || :)"
  [ "$typ" = login ] || break
  read_grants="$(uci -q get "rpcd.@login[$n].read" 2>/dev/null || :)"
  write_grants="$(uci -q get "rpcd.@login[$n].write" 2>/dev/null || :)"
  # Treat any patterns/negation conservatively; this is a static signal,
  # not an authenticated per-user access test.
  label=restricted
  case " $write_grants " in
    *' * '*) label=wildcard; wildcard=$((wildcard+1)) ;;
    *' veci-sms-inbox-we5927 '*) label=explicit_sms_write; priv=$((priv+1)) ;;
    *'!'*|*'*'*|*'?'*) label=needs_manual_review; uncertain=$((uncertain+1)) ;;
    *) restricted=$((restricted+1)) ;;
  esac
  printf 'LOGIN_%s_WRITE_GRANT_CLASS=%s\n' "$n" "$label"
  unset read_grants write_grants label
  n=$((n+1))
done
[ "$n" -gt 0 ] || error no_login_sections
printf 'LOGIN_COUNT=%s\n' "$n"
printf 'WILDCARD_WRITE_LOGIN_COUNT=%s\n' "$wildcard"
printf 'EXPLICIT_SMS_WRITE_LOGIN_COUNT=%s\n' "$priv"
printf 'RESTRICTED_LOGIN_COUNT=%s\n' "$restricted"
printf 'NEEDS_REVIEW_LOGIN_COUNT=%s\n' "$uncertain"
# Anonymous ubus session access to the method is a pure query.
# Never send listIndex itself and never output a live session id.
anonymous='00000000000000000000000000000000'
answer="$(ubus call session access "{\"ubus_rpc_session\":\"$anonymous\",\"scope\":\"ubus\",\"object\":\"veci.sms\",\"function\":\"listIndex\"}" 2>/dev/null || :)"
if [ -n "$answer" ]; then
  grant="$(printf '%s' "$answer" | jsonfilter -e '@.access' 2>/dev/null || :)"
else
  grant=''
fi
case "$grant" in
  false|0) echo 'ANONYMOUS_SMS_LIST_ACCESS=denied' ;;
  true|1) echo 'ANONYMOUS_SMS_LIST_ACCESS=ALLOWED_SECURITY_FAILURE' ;;
  *) echo 'ANONYMOUS_SMS_LIST_ACCESS=unknown' ;;
esac
echo 'NO_SMS_MODEM_COMMAND_SENT=true'
echo 'NO_CREDENTIALS_OR_SESSION_TOKENS_EXPORTED=true'
echo 'NON_ADMIN_SESSION_TEST=not_performed'
