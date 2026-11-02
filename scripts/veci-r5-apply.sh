#!/bin/sh
# Manually applied from Windows laptop. Does not flash OpenWrt.
set -eu
action="$1"
job="$2"
expected="$(printf '%s' "$3")"
case "$job" in /tmp/veci-oneclick-[A-Za-z0-9]*) ;; *) echo "BAD_JOB_PATH" >&2; exit 2;; esac
archive="$job/veci-core-r5.tar.gz"
backup="$job/backup.tar.gz"
stage="$job/unpacked"
board="$(ubus call system board 2>/dev/null | jsonfilter -e '@.board_name' 2>/dev/null || true)"
[ "$board" = 'zbtlink,zbt-we5927' ] || { echo "WRONG_BOARD" >&2; exit 3; }
[ -f /www/veci/index.html ] && [ -f /usr/libexec/rpcd/veci ] &&
  [ -f /usr/share/rpcd/acl.d/veci.json ] || { echo "CORE_NOT_INSTALLED" >&2; exit 4; }
backup_router() {
    optional=''
    : > "$job/optional.list"
    for app in guest voucher; do
        if [ -f "/usr/libexec/rpcd/veci.app.$app" ] && [ -f "/www/veci-apps/$app.js" ]; then
            printf '%s\n' "$app" >> "$job/optional.list"
            optional="$optional usr/libexec/rpcd/veci.app.$app www/veci-apps/$app.js"
        fi
    done
    # optional has only fixed app names and is never derived from user input.
    # shellcheck disable=SC2086
    tar -czf "$backup" -C / www/veci usr/libexec/rpcd/veci usr/share/rpcd/acl.d/veci.json $optional
    [ -s "$backup" ] || { echo "BACKUP_FAILED" >&2; exit 5; }
}
restore_router() {
    [ -s "$backup" ] || { echo "BACKUP_MISSING" >&2; exit 6; }
    tar -xzf "$backup" -C / || { echo "ROLLBACK_COPY_FAILED" >&2; exit 7; }
    if ! tar -tzf "$backup" | grep -qx 'www/veci/veci-core-commit.txt'; then
        rm -f /www/veci/veci-core-commit.txt
    fi
    /etc/init.d/rpcd restart >/dev/null 2>&1 || true
    echo "ROLLBACK_FILES_RESTORED"
}
case "$action" in
    prepare)
        overlay="$(df -Pk /overlay | awk 'NR==2 {print $4}')"
        ram="$(df -Pk /tmp | awk 'NR==2 {print $4}')"
        case "$overlay:$ram" in *[!0-9:]*|:*|*:) echo "STORAGE_UNKNOWN" >&2; exit 8;; esac
        [ "$overlay" -ge 1024 ] && [ "$ram" -ge 4096 ] ||
          { echo "INSUFFICIENT_STORAGE" >&2; exit 9; }
        [ -s "$archive" ] || { echo "ARCHIVE_MISSING" >&2; exit 10; }
        backup_router
        echo "PREPARED_BACKUP"
        ;;
    apply)
        [ -s "$backup" ] || { echo "BACKUP_REQUIRED" >&2; exit 11; }
        case "$expected" in ''|*[!0-9a-f]*) echo "INVALID_EXPECTED_SHA" >&2; exit 12;; esac
        [ "$(printf '%s' "$expected" | wc -c | tr -d ' ')" -eq 64 ] || exit 12
        actual="$(sha256sum "$archive" | awk '{print $1}')"
        [ "$actual" = "$expected" ] || { echo "ARCHIVE_HASH_MISMATCH" >&2; exit 13; }
        mkdir -p "$stage"
        tar -xzf "$archive" -C "$stage" || { echo "EXTRACT_FAILED" >&2; exit 14; }
        [ -f "$stage/www/veci/index.html" ] &&
          [ -f "$stage/usr/libexec/rpcd/veci" ] &&
          [ -f "$stage/usr/share/rpcd/acl.d/veci.json" ] ||
          { echo "INVALID_BUNDLE" >&2; exit 15; }
        if ! cp -R "$stage/www/veci/." /www/veci/ ||
           ! cp "$stage/usr/libexec/rpcd/veci" /usr/libexec/rpcd/veci ||
           ! cp "$stage/usr/share/rpcd/acl.d/veci.json" /usr/share/rpcd/acl.d/veci.json; then
            restore_router
            echo "APPLY_COPY_FAILED" >&2
            exit 16
        fi
        for app in guest voucher; do
            if grep -qx "$app" "$job/optional.list"; then
                if [ ! -f "/usr/libexec/rpcd/veci.app.$app" ] ||
                   [ ! -f "/www/veci-apps/$app.js" ] ||
                   ! cp "$stage/usr/libexec/rpcd/veci.app.$app" "/usr/libexec/rpcd/veci.app.$app" ||
                   ! cp "$stage/www/veci-apps/$app.js" "/www/veci-apps/$app.js" ||
                   ! sh -n "/usr/libexec/rpcd/veci.app.$app"; then
                    restore_router
                    echo "APP_HOTFIX_FAILED_$app" >&2
                    exit 20
                fi
                chmod 755 "/usr/libexec/rpcd/veci.app.$app"
            fi
        done
        chmod 755 /usr/libexec/rpcd/veci
        if ! sh -n /usr/libexec/rpcd/veci; then
            restore_router
            echo "APPLY_SHELL_CHECK_FAILED" >&2
            exit 17
        fi
        if ! /etc/init.d/rpcd restart >/dev/null 2>&1; then
            restore_router
            echo "APPLY_RPCD_FAILED" >&2
            exit 18
        fi
        ready=0
        for attempt in 1 2 3 4; do
            if ubus list veci >/dev/null 2>&1; then ready=1; break; fi
            sleep 2
        done
        if [ "$ready" -ne 1 ]; then
            restore_router
            echo "APPLY_UBUS_FAILED" >&2
            exit 19
        fi
        # Check upgraded optional providers are actually registered by rpcd.
        for app in guest voucher; do
            if grep -qx "$app" "$job/optional.list"; then
                registered=0
                for attempt in 1 2 3 4; do
                    if ubus list 2>/dev/null | grep -Fxq "veci.app.$app"; then
                        registered=1
                        break
                    fi
                    sleep 2
                done
                if [ "$registered" -ne 1 ]; then
                    restore_router
                    echo "APP_PROVIDER_NOT_REGISTERED_$app" >&2
                    exit 21
                fi
            fi
        done
        # Preserve HTTP, uHTTPd, WAN, radio, LTE, DHCP and all UCI config.
        echo "VECI_CORE_R5_APPLIED"
        for app in guest voucher; do
            if grep -qx "$app" "$job/optional.list"; then
                echo "VECI_APP_$app HOTFIX_APPLIED"
            else
                echo "VECI_APP_$app NOT_INSTALLED"
            fi
        done
        ;;
    rollback)
        restore_router
        ;;
    *) echo "usage: veci-core-apply.sh prepare|apply|rollback JOB_DIR SHA" >&2; exit 2;;
esac
