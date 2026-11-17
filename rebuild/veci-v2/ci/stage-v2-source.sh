#!/bin/sh
# Stage only source packages in a verified, isolated OpenWrt build tree.
# No router SSH, no firmware flash, no package installation.
set -eu
if [ "$#" -ne 1 ]; then
  echo 'usage: stage-v2-source.sh <pinned-openwrt-source>' >&2
  exit 2
fi
root="$(CDPATH= cd -- "$1" && pwd -P)"
here="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
case "$root" in /|/etc|/root|/tmp|/home|/overlay|/rom)
  echo unsafe_build_root >&2; exit 2 ;; esac
[ -f "$root/include/toplevel.mk" ] &&
[ -f "$root/target/linux/ramips/dts/mt7628an_zbtlink_zbt-we5927.dts" ] &&
[ -f "$root/package/we5927-lte/Makefile" ] &&
[ -d "$root/.git" ] || {
  echo missing_custom_board_or_not_build_tree >&2; exit 3
}
pin='64900e756efa667774214f9c6b17c113222e01f7'
[ "$(git -C "$root" rev-parse HEAD)" = "$pin" ] || {
  echo wrong_openwrt_source_commit >&2; exit 3
}
for name in veci-v2-runtime veci-v2-package-manager veci-v2-ui veci-v2-sms; do
  src="$here/packages/$name"
  dst="$root/package/$name"
  [ -f "$src/Makefile" ] && [ ! -L "$src" ] &&
    [ ! -L "$dst" ] || { echo "invalid_package:$name" >&2; exit 3; }
  if [ -e "$dst" ]; then
    if [ "$name" = veci-v2-sms ]; then
      cmp -s "$src/Makefile" "$dst/Makefile" &&
      cmp -s "$src/veci-v2-sms-acl.json" "$dst/veci-v2-sms-acl.json" || {
        echo "different_existing_sms_package:$name" >&2; exit 3
      }
    else
      diff -qr "$src" "$dst" >/dev/null || {
        echo "different_existing_package:$name" >&2; exit 3
      }
    fi
  fi
done
# The SMS transport source is canonical and reviewed in the old module.
# Never duplicate its code inside the repository or execute vendor binaries.
sms_origin="$here/../../source/veci-cellular-we5927/files"
sms_files='etc/config/veci_sms etc/uci-defaults/97-veci-sms-userdata
usr/libexec/rpcd/veci.sms usr/libexec/veci-sms-parse
usr/libexec/veci-sms-delete-one usr/libexec/veci-sms-send-one
usr/libexec/veci-sms-sent-history usr/libexec/veci-sms-drafts'
sms_dst="$root/package/veci-v2-sms/files"
for rel in $sms_files; do
  [ -f "$sms_origin/$rel" ] && [ ! -L "$sms_origin/$rel" ] &&
  [ ! -L "$sms_dst/$rel" ] || { echo "invalid_sms_source:$rel" >&2; exit 3; }
  if [ -e "$sms_dst/$rel" ]; then
    cmp -s "$sms_origin/$rel" "$sms_dst/$rel" || {
      echo "different_sms_runtime:$rel" >&2; exit 3
    }
  fi
done
# Validation succeeded before any modifications.
for name in veci-v2-runtime veci-v2-package-manager veci-v2-ui veci-v2-sms; do
  src="$here/packages/$name"
  dst="$root/package/$name"
  if [ ! -d "$dst" ]; then
    mkdir "$dst"
    cp -a "$src/." "$dst/"
  fi
  if [ "$name" != veci-v2-sms ]; then
    diff -qr "$src" "$dst" >/dev/null || {
      echo "staging_corrupt:$name" >&2; exit 4
    }
  fi
done
mkdir -p "$sms_dst"
for rel in $sms_files; do
  if [ ! -e "$sms_dst/$rel" ]; then
    mkdir -p "$(dirname "$sms_dst/$rel")"
    cp -p "$sms_origin/$rel" "$sms_dst/$rel"
  fi
  cmp -s "$sms_origin/$rel" "$sms_dst/$rel" ||
    { echo "sms_transport_mismatch:$rel" >&2; exit 4; }
done
echo VECI_V2_SMS_TRANSPORT_SINGLE_SOURCE=PASS
echo VECI_V2_EXACT_BOARD_PACKAGES_STAGED=PASS
echo NOT_A_FINISHED_IMAGE_NOT_SIGNED_NOT_FLASHABLE
