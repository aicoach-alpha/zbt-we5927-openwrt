# Changelog

## 2026-10-06

- Public repository preparation.
- Documented official ZBT WE2825-2SIM firmware comparison.
- Added fast cached LuCI LTE status path.
- Added last-known-good modem status caching.
- Added non-blocking background full-status refresh.
- Added AT-port locking.
- Added safe AT-port resolution for CX07E.
- Added interface-first LTE recovery.
- Default health policy changed to 30-second checks with 6 consecutive failures (~3 minutes) before recovery.
- Automatic SIM failover remains disabled by default.
- Documented low-resource package policy and external DNS filtering strategy.
