# VeCI idle RAM optimization (WE5927 General-Cafe)

## Actual resident-service audit

- The firmware update agent originally ran a shell plus sleep for 6 hours,
  regardless of whether the operator had disabled automatic checks.
- Fresh installations now default veci.update.auto_check=0.
  Existing UCI settings are preserved and NOT overwritten; they may remain 1.
- The init service starts a procd instance only if auto_check is 1.
  The service registers a reload_config trigger for veci UCI changes.
- When auto_check is turned off, the update loop exits on its next wake;
  operators should issue reload_config or restart the service after
  changes to apply them immediately.
- Manual firmware check through the VeCI RPC, signed image verification,
  and update buttons are retained. Auto-download and auto-install remain
  opt-in and the signature requirement remains intact.

The active voucher expiry-cleaner and LTE modem daemon are **preserved**:
they protect credential expiry, modem reconnect, and cellular access.
Changing them without an authenticated event-driven replacement risks
breaking real connected clients. This patch does not change router services
until a new firmware or compatible approved APK is deployed.

## Measurement and limitations

The patch reduces idle processes only when auto_check=0. The number
of bytes of router RAM saved is **not measured**; the NAS Docker builder
metrics are not router RAM measurements. Measure RSS/PSS and MemAvailable
before/after on the physical router, together with free overlay bytes,
then validate whether additional APK packages fit. No automatic router flash.
