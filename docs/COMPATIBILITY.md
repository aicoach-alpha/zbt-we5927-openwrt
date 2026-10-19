# Compatibility matrix

This matrix separates what is tested from what is merely known to exist in the ZBT vendor stack.

## Boards

| Board / marketing name | OpenWrt identity | Status | Build image |
|---|---|---:|---:|
| WE2825-2SIM / tested WE5927 | zbtlink,zbt-we5927 | Tested | Yes |
| WE5927-A / Nano-SIM/eSIM variants | unknown | Discovery | No |
| Other ZBT MT7628 cellular boards | varies | Planned | No |

The tested WE2825-2SIM/WE5927 profile uses an 8 MB NOR layout, MT7628AN, GPIO 46 for SIM selection and GPIO 1 for modem power. Those values are not inherited by other models unless independently verified.

## Modems

| Modem/profile | USB ID | Status | Automatic control |
|---|---|---:|---:|
| CX07E | 05c6:902e | Tested | Yes |
| Quectel EC20/EC25 family | 2c7c:0125 and vendor aliases | Vendor reference | No |
| Quectel EC200T | 2c7c:6026 | Vendor reference | No |
| Quectel EC200U | 2c7c:6002 | Vendor reference | No |
| Quectel EC200A | 2c7c:6005 | Vendor reference | No |
| SIMCom SIM7600 | 1e0e:9001 | Vendor reference | No |
| SIMCom A7600C | 1e0e:9011 | Vendor reference | No |
| Fibocom L716/L718 | 2cb7:0001 | Vendor reference / ambiguous | No |
| Fibocom NL668 | 1508:1001 | Vendor reference | No |
| Quectel RM500 | 2c7c:0800 | Vendor reference | No |
| Quectel RM520N | 2c7c:0801 | Vendor reference | No |
| Fibocom FM150 variants | 2cb7:0104/0105/0109/010a | Vendor reference | No |

Vendor reference means the modem was represented in the inspected ZBT WE2825-2SIM firmware. It does not mean it has been tested with this community implementation.

## Promotion gate for a modem

Before a modem can move from reference-only to community-tested, we need:

1. USB VID/PID and USB interface topology.
2. Exact model string from a safe AT port.
3. Verified data mode and network interface.
4. Verified SIM/operator/registration/signal queries.
5. Soft reconnect test.
6. Recovery from a deliberate interface failure.
7. Reboot persistence.
8. No uninterruptible or stuck serial I/O during status polling.

## Contributing hardware evidence

Run scripts/probe-zbt-hardware.sh on the router and attach its output to a hardware-support issue.

The probe intentionally does not query IMEI, ICCID or IMSI.
