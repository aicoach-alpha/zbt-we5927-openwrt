# Family firmware architecture

The long-term goal is to turn this project from a single-device customization into a community-maintained modern OpenWrt firmware family for related ZBT cellular routers.

The project deliberately does not use one universal binary for all ZBT routers. It uses one common codebase with separate board profiles and board-specific images.

## Layers

ZBT Community OpenWrt

- Common service layer
  - LuCI cellular UI
  - smart LTE recovery
  - DNS policy
  - logging / health
- Board profiles
  - WE2825-2SIM / tested WE5927
  - WE5927-A (discovery only)
  - future MT7628 ZBT boards
- Modem profiles
  - CX07E (tested)
  - Quectel candidates
  - SIMCom candidates
  - Fibocom candidates
  - future QMI/MBIM/RNDIS/ECM profiles

## Why separate board and modem profiles?

A router board controls flash layout, DTS, Ethernet topology, LEDs/buttons, modem power GPIO, SIM selector GPIO, and Wi-Fi calibration partitions.

A modem profile controls USB VID/PID, data mode, AT function selection, registration/signal commands, soft reconnect behavior, and safe USB recovery.

Those are independent dimensions. The same board can ship with different modems, and the same modem can be used on different boards.

## Safety model

| State | Meaning |
|---|---|
| tested | Verified directly by this project on real hardware |
| community-tested | Verified by reproducible community evidence |
| reference-only | Seen in vendor compatibility data, but not safe for automatic control |
| discovery | Placeholder; hardware facts are incomplete |

Only tested and community-tested board profiles may produce release images.

Only tested and community-tested modem profiles may be automatically controlled by the cellular manager.

A VID/PID match alone is not always enough. Several vendor IDs are reused across modem variants, so some candidates require a model probe before they can be promoted.

## Vendor resources policy

The inspected ZBT firmware is useful as an interoperability reference because it contains broad modem compatibility knowledge.

The clean-room workflow is:

1. Observe factual mapping and protocol behavior in the vendor image.
2. Document those facts independently.
3. Implement an open-source profile or driver behavior.
4. Verify it on real hardware.

We do not publish vendor proprietary scripts or opaque binaries merely because they were present in the factory image.

## Release model

The intended model is one repository with multiple board-specific images, for example:

- we2825-2sim-sysupgrade.bin
- we5927-compatible-sysupgrade.bin
- future-board-a-sysupgrade.bin
- future-board-b-sysupgrade.bin

This follows the same general safety principle as OpenWrt: shared source, hardware-specific images.
