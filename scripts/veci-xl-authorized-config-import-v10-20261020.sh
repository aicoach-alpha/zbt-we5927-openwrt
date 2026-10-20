#!/bin/sh
# VeCI XL owner-only offline provisioning. NEVER embeds or displays app secrets.
# Supply valid operator-authorized values in root-owned /tmp/veci-xl-authorized-config.
# No network or OTP operations, no persistence to flash.
set -eu
umask 077
LC_ALL=C
export LC_ALL
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
SRC=/tmp/veci-xl-authorized-config
CIAM=/tmp/veci-xl-ciam
PRIVATE=/tmp/veci-telco-private
LOCK=/tmp/veci-xl-owner-rpc.lock
CIAM_FIELDS="basic_auth user_agent fingerprint device_id ax_api_sig_key"
PRIVATE_FIELDS="xdata_key api_key signature_secret"
ALL_FIELDS="$CIAM_FIELDS $PRIVATE_FIELDS"
fail(){ printf 'XL_PROVISION=%s\n' "$1"; exit 1; }
safe_dir(){
 [ -d "$1" ] && [ ! -L "$1" ] &&
 [ "$(ls -ldn "$1" | awk '{print $1 " " $3}')" = 'drwx------ 0' ]
}
safe_file(){
 [ -f "$1" ] && [ ! -L "$1" ] &&
 [ "$(ls -ldn "$1" | awk '{print $1 " " $3}')" = '-rw------- 0' ]
}
file_size(){
 wc -c < "$1" | tr -d '[:space:]'
}
valid_size(){
 bytes="$(file_size "$1")" || return 1
 case "$bytes" in ''|*[!0-9]*) return 1;; esac
 [ "$bytes" -ge 1 ] && [ "$bytes" -le 4096 ]
}
ready(){
 safe_dir "$CIAM" && safe_dir "$PRIVATE" || return 1
 for name in $CIAM_FIELDS; do
   safe_file "$CIAM/$name" && valid_size "$CIAM/$name" || return 1
 done
 for name in $PRIVATE_FIELDS; do
   safe_file "$PRIVATE/$name" && valid_size "$PRIVATE/$name" || return 1
 done
 [ "$(file_size "$PRIVATE/xdata_key")" -eq 32 ] || return 1
}
status(){
 if ready; then
   echo XL_PROVISION=locally_configured_operator_access_unverified
 else
   echo XL_PROVISION=awaiting_authorized_config
 fi
}
[ "$(id -u)" = 0 ] || fail root_required
case "${1:-}" in
 --status)
   [ "$#" -eq 1 ] || fail invalid_usage
   status
   exit 0
   ;;
 --apply)
   [ "$#" -eq 1 ] || fail invalid_usage
   ;;
 *)
   fail invalid_usage
   ;;
esac
# Entire supplied bundle must be root-owned private files before writing anything.
safe_dir "$SRC" || fail bundle_not_private
for name in $ALL_FIELDS; do
 safe_file "$SRC/$name" || fail missing_or_unsafe_bundle_file
 valid_size "$SRC/$name" || fail invalid_bundle_field_size
done
[ "$(file_size "$SRC/xdata_key")" -eq 32 ] || fail invalid_xdata_key_length
[ ! -L "$CIAM" ] && [ ! -L "$PRIVATE" ] || fail unsafe_target
if [ -e "$CIAM" ]; then safe_dir "$CIAM" || fail unsafe_target; fi
if [ -e "$PRIVATE" ]; then safe_dir "$PRIVATE" || fail unsafe_target; fi
# Never overwrite existing credentials or disturb an existing subscriber session.
for name in $CIAM_FIELDS; do
 [ ! -e "$CIAM/$name" ] && [ ! -L "$CIAM/$name" ] || fail target_already_present
done
for name in $PRIVATE_FIELDS; do
 [ ! -e "$PRIVATE/$name" ] && [ ! -L "$PRIVATE/$name" ] || fail target_already_present
done
for name in id_token access_token refresh_token verified_epoch pending-profile; do
 [ ! -e "$PRIVATE/$name" ] && [ ! -L "$PRIVATE/$name" ] || fail active_session_or_pending_profile
done
mkdir "$LOCK" 2>/dev/null || fail account_action_in_progress
writing=0
committed=0
cleanup(){
 if [ "$writing" = 1 ] && [ "$committed" = 0 ]; then
   for name in $CIAM_FIELDS; do rm -f "$CIAM/$name"; done
   for name in $PRIVATE_FIELDS; do rm -f "$PRIVATE/$name"; done
 fi
 rmdir "$LOCK" 2>/dev/null || :
}
trap cleanup EXIT
trap 'exit 130' INT TERM
mkdir -p "$CIAM" "$PRIVATE" || fail create_private_dirs_failed
chmod 700 "$CIAM" "$PRIVATE" || fail private_dir_mode_failed
safe_dir "$CIAM" && safe_dir "$PRIVATE" || fail private_dir_validation_failed
writing=1
for name in $CIAM_FIELDS; do
 cp "$SRC/$name" "$CIAM/$name" || fail write_failed
 chmod 600 "$CIAM/$name" || fail permission_failed
done
for name in $PRIVATE_FIELDS; do
 cp "$SRC/$name" "$PRIVATE/$name" || fail write_failed
 chmod 600 "$PRIVATE/$name" || fail permission_failed
done
ready || fail installed_config_validation_failed
committed=1
# Delete supplied plaintext files only after a complete local commit.
for name in $ALL_FIELDS; do rm -f "$SRC/$name" || :; done
rmdir "$SRC" 2>/dev/null || :
echo XL_PROVISION=installed_operator_auth_not_verified
