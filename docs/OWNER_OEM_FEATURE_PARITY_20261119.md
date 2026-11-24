# Owner OEM → VeCI Native Feature Parity (19 November 2026)

Status ini adalah **analisis source, bukan klaim fitur fisik sudah lulus**.

| Fungsi yang nyata di OEM | OpenWrt/VeCI v2 sumber | Belum terbukti |
|---|---|---|
| Model WE2825-2SIM, 8 MiB, dual-SIM GPIO46 | Board patch/DTS dan exact size gate ada | Boot/recovery aktual image VeCI |
| Wi-Fi MT7628 2.4GHz saja | guardian, AP status, SSID, channel, UCI handler ada | Beacon/association/WPA2-AES hardware |
| Modem QUALCOMM 4108 USB 05c6:902e RNDIS | we5927-lte, verified AT port, RNDIS identity checks ada | Reconnect modem real dan LTE throughput |
| SIM1/SIM2 via GPIO46 | observed selector + manual SIM code ada | Mapping label GUI ke fisik + switching |
| WEB 3G/4G/LTE & APN | VeCI Koneksi / APN + LTE status ada | Login + APN hardware integration |
| SMS Center (permintaan tambahan) | VeCI v2 native SMS Center dan PDU backend source-tested | SMS nyata inbox/send/delete |
| WAN LAN NAT firewall DHCP | Core OpenWrt tersedia; UI OEM parity belum lengkap | Semua port, DHCP, firewall dan UI |
| DNS operator/manual dan preset | dnsmasq base package ada | **GUI native DNS** + commit/rollback masih perlu diimplementasi |
| Speed Test browser addon OEM | Tidak ada native UI VeCI lengkap | **GUI Speed Test** dengan endpoint hasil uji dan batas trafik masih perlu diintegrasi |
| Wi-Fi guest optional | Governance guest dan disabled default ada | Isolasi guest jika diaktifkan |
| Backup/restore dan signed update OTA | Signed verify/OTA source-tested | Restore dan trust chain end-to-end |
| No LuCI, only VeCI | Source build workflow melarang LuCI | Inventaris ROM image dan fungsi UI |
| SSH root tanpa Telnet | Dropbear di OpenWrt | Persistensi/ACL/HTTPS dan firewall di perangkat |

Catatan: Kontrak 40 required_core pada proyek VeCI v2 mengandung modul yang masih not_ported_to_v2. Jangan ubah label status menjadi PASS hanya karena kode dasar exist. Perbedaan SSID/guest/encryption antara UCI dan driver OEM harus diperhatikan, dan UI 5GHz vendor **bukan** fitur unit pemilik.

Implementasi berikut: DNS native RPC + rollback; Speed Test Lite berbasis browser yang menampilkan konteks uji dari klien; pindahkan fungsi OEM lain satu per satu secara terukur. Jangan duplikasi manajemen modem, SMS lock, atau DNS daemon.

## Progress native tools — 19 November 2026 (source branch only)
- Speed Test Lite native di tab Pengaturan: pengujian HTTP latency/jitter, download 1 MiB, upload 512 KiB dengan abort, timeout, dan batas riwayat sesi browser. CSP hanya memperbolehkan endpoint Cloudflare yang ditentukan. Mengukur koneksi dari browser/klien, bukan throughput langsung firmware router.
- DNS Settings native di tab Pengaturan: mode AUTO DNS operator / CUSTOM upstream IPv4, preset Cloudflare/Google/Quad9/AdGuard; provider rpcd veci.v2.dns dengan ACL status(read)/set(write), pembatas board, validasi IPv4, lock serial, pemeriksaan pending UCI, restart dnsmasq serta restore file dhcp bila penerapan gagal.
- Browser tool bukan daemon background dan tidak memodifikasi modem, GPIO atau rute LTE.
- Pengujian lokal validator/ACL/JS/shell dan regresi utama lulus. **Belum dikompilasi ke image baru**, belum ada uji UI browser fisik, operasi DNS pada router, maupun pengukuran LTE sebenarnya. Seluruh modul gabungan dhcp_dns_static_leases tetap PARTIAL karena DHCP/leases belum diport penuh.
