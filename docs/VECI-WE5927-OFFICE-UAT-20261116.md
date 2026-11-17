# VeCI WE5927 office-laptop physical UAT, read-only

Source: scripts/uat/veci-office-readonly.ps1 (Windows PowerShell 5.1).

This tool is for a Windows laptop connected through a wired LAN port.
It uses the laptop's existing, trusted OpenSSH connection to the physical
ZBT-WE5927 at 192.168.1.1. The NAS and GitHub CI cannot substitute for the
physical router's radio beacon or physical Ethernet cable measurements.

The collector is read-only: no remote pipes, no shell pipeline, no network
restarts, no radio changes, no modem resets, no firmware flashing.
The prior diagnostic command accidentally spawned a second netifd because
a quoted grep expression containing a pipe was interpreted as shell control.
This tool prohibits metacharacters in remote commands and separately checks
that exactly one netifd remains.

On the already trusted Windows office laptop, save the script locally, then:

    powershell.exe -NoProfile -File .\veci-office-readonly.ps1 -Router 192.168.1.1 -Samples 3 -IntervalSeconds 30

Wi-Fi beacon verification is NOT implied by hostapd/ubus up.
Only after verifying a physical router SSID and matching BSSID independently:

    powershell.exe -NoProfile -File .\veci-office-readonly.ps1 -Router 192.168.1.1 -Samples 3 -IntervalSeconds 30 -ExpectedSSID "VERIFIED_NAME" -ExpectedBSSID "aa:bb:cc:dd:ee:ff"

Each observation includes per-port physical switch link status (0-3 LAN,
4 Ethernet WAN). A disconnected port is NOT treated as faulty or tested.
To complete all-port UAT, plug one verified Ethernet cable into each physical
LAN port separately and repeat the readings; this cannot be automated remotely.

The JSON report contains only booleans, counts, port numbers and timestamps;
it does not persist SSIDs, BSSIDs, IP addresses, device MACs, credentials,
modem IDs or raw log contents. Repeated ping success is only a short snapshot,
not 72-hour availability evidence. Router-LTE-uplink=True means the router's
own USB0 ICMP test passed; it does NOT prove wired clients get NAT forwarding
or that Wi-Fi clients can associate and browse. Client paths remain null until
separately tested from a device actually routing through 192.168.1.1.

If the script cannot establish SSH with existing verified host keys, stop and
check the laptop's SSH trust configuration. Never bypass host-key verification.
