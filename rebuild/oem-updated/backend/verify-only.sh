#!/bin/sh
# OEM lab UI must never expose installation or stable-channel apply.
[ "${QUERY_STRING:-}" = "" ] || {
  printf 'Status: 403 Forbidden\r\nContent-Type: application/json\r\nCache-Control: no-store\r\n\r\n{"error":"installation_locked"}\n'
  exit 0
}
exec /usr/libexec/oem-updated/shared-verify
