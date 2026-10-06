# LTE recovery design

The LTE watchdog is intentionally conservative.

## Health check

The default configuration uses:

```
ping_host=1.1.1.1
ping_interval=30
fail_threshold=6
```

A second target, 8.8.8.8, is used as a fallback if the primary target does not respond.

This means the daemon waits for roughly **3 minutes of consecutive failed health checks** before initiating recovery.

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
