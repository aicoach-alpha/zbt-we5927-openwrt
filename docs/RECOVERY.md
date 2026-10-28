# LTE recovery design

The LTE watchdog uses a faster three-strike check and conservative recovery escalation. Source defaults were changed on 2026-10-28; the live router requires its own guarded UCI change and watchdog restart before the new interval is in effect.

## Health check

The default configuration uses:

```
ping_host=1.1.1.1
ping_interval=10
fail_threshold=3
```

A second target, 8.8.8.8, is used as a fallback if the primary target does not respond.

This sets a **target of about 30–45 seconds** before interface-first recovery when consecutive IP checks fail. Actual detection depends on ICMP probe latency and scheduler timing. It is a detection threshold, not a promise of completed internet reconnection.

## Escalation order

```text
1. Logical LTE interface restart
   ifdown lte
   ifup lte

2. Soft modem reconnect
   AT+CFUN=0
   AT+CFUN=1

3. Hard modem power-cycle
   only after repeated recovery cycles

4. Optional SIM failover
   only when auto_failover=1
```

A successful lower-level recovery resets the recovery counter.

## Why not Watchcat?

Watchcat is small and useful on many OpenWrt routers, but on this hardware it would duplicate work already performed by the modem-aware LTE daemon.

The custom daemon knows:

- the RNDIS data interface;
- the AT serial function;
- the modem power GPIO;
- the SIM selector GPIO;
- the difference between interface recovery, CFUN recovery and hard reset.

Running another independent watchdog can produce competing recovery actions.

## Why interface-first?

A mobile connection can fail while the modem itself is still registered and healthy.

Restarting only the logical LTE interface is cheaper and less disruptive than:

- resetting the radio stack;
- cycling modem power;
- rebooting the whole router.

The modem is only touched if interface recovery fails.

## LuCI status and AT locking

Status queries and the watchdog share the AT port.

The script serializes AT access with a lock and the LuCI page uses a fast cached status path. This prevents a page refresh from waiting indefinitely behind modem I/O.

The cache refresh is background work. A failed refresh does not overwrite the last known-good modem details.

## Dual-SIM

Automatic SIM failover is disabled by default:

```
auto_failover=0
```

Enable it only after both SIM slots and GPIO polarity have been verified on the exact hardware.

## Do not use full-router reboot as the first recovery step

The design intentionally avoids rebooting OpenWrt for ordinary LTE failures. Full router reboot should remain a last-resort/manual recovery path.

## 2026-10-28 — Fast reconnect deployment and failure boundaries

The scoped hotfix `scripts/veci-v13-lte-fast-reconnect-20261028.sh` changes **only** `we5927_lte.main.ping_interval=10` and `we5927_lte.main.fail_threshold=3`, backs up the original UCI file and service enabled state, preserves the APN/SIM/auto-failover parameters, and performs one targeted `we5927-lte` service restart. It does not reset the modem, restart the complete router or reconfigure the WAN firewall itself. Existing daemon startup may nevertheless initialize LTE and briefly interrupt connectivity when the service restarts.

The watchdog still uses interface-first recovery (`ifdown/ifup lte`), then CFUN soft reconnect if data does not return, escalating to hardware power-cycle only as configured; dual SIM auto-failover remains disabled unless explicitly enabled. The original config's `hard_reset_after` is unchanged. The script has `--status` and `--rollback` modes.

**Source is not proof of production:** Do not mark this tuning LIVE before an office owner reports `VECI_FAST_RECONNECT_RELEASE=live_pass` and `VECI_FAST_RECONNECT_INTEGRITY=pass`. This verifies configuration and running watchdog, not a controlled real outage recovery. If a real outage still fails to recover, collect just the existing watchdog log segment and runtime status to identify whether the daemon hung or the modem failed to reconnect. Do not create a competing second watchdog or repeatedly reset the modem.
