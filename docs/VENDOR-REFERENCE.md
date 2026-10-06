# Vendor compatibility reference

The official WE2825-2SIM image inspected for this project contains a broad AnyWiFi-style cellular framework with QMI/MBIM tooling, manual dial profiles and per-modem AT/chat handlers.

This document records only factual interoperability observations needed to design open-source profiles. The vendor scripts themselves are not redistributed here.

## What the vendor image tells us

The factory stack includes:

- uqmi and umbim
- quectel-CM
- QMI, MBIM and USB networking kernel support
- generic 3G chat scripts
- modem-specific manual-dial handlers
- modem-specific status handlers
- a modem module list mapping USB IDs to data/AT serial hints
- network watchdog and module-restart logic

This confirms the WE2825-2SIM product family was intended to support significantly more cellular modules than the currently tested CX07E.

## High-value migration targets

The first community candidates should be the modem families that are both common and clearly represented in the vendor image:

1. Quectel EC20 / EC25
2. Quectel EC200T / EC200U / EC200A
3. SIMCom SIM7600 / A7600C
4. Fibocom L716 / L718 / NL668
5. Quectel RM500 / RM520N
6. Fibocom FM150 family

The factual USB-ID/port hints are stored in family/modems/vendor-candidates.json.

## What we intentionally do not copy

- vendor executables
- vendor shell scripts
- proprietary web UI
- device-specific credentials or calibration
- IMEI-changing behavior
- opaque binary drivers where an upstream OpenWrt equivalent is available

Instead, each supported modem gets a small auditable profile plus open-source control logic.
