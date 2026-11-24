# VeCI v2 WE5927 — Lessons Learned LTE dan Standar GUI

Tanggal: 24 November 2026. Perangkat: satu router ZBT-WE5927-DSIM, modem Qualcomm USB 05c6:902e, OpenWrt 25.12.6. Status: pengembangan source, BELUM firmware final siap flash.

## 1. Fakta lapangan

LAN 192.168.1.1 tetap dapat diakses, tetapi LTE usb0 berganti-ganti antara tanpa IP dan memperoleh 192.168.7.120/24 serta rute 192.168.7.1. HTTPS ke IP publik dan domain sempat timeout. Ditemukan netifd resmi yang dikelola procd pada PID1366 (PPID1), serta netifd kedua PID16862 yang merupakan anak shell PID16854. Ada keadaan ubus LTE pending tanpa DHCP, dan notify_proto Permission denied sewaktu peralihan interface. Ini bukti gejala dan konflik kepemilikan, bukan bukti tunggal akar masalah.

Pemulihan pada fisik router dilakukan sekali: setelah memeriksa identitas PID, hanya PID16862 dihentikan dengan SIGTERM. PID1366 dan LAN dipertahankan. Satu siklus down/up khusus LTE diterima. Hasil pemulihan: ORPHAN_TERM=ENDED; LAN=STILL_PRESENT; LTE_DOWN_EXIT=0; LTE_UP_EXIT=0; USB0_IPV4=assigned; LTE_ROUTE=present; HTTPS 1.1.1.1 mengembalikan HTTP301/exit0; HTTPS www.cloudflare.com mengembalikan HTTP200/exit0. Sebelumnya, LTE down/up tanpa pembersihan PID ekstra tidak berhasil. Hal ini mendukung hipotesis benturan netifd, tetapi belum membuktikan satu-satunya penyebab.

## 2. Pencegahan permanen dalam source

File canonical source/we5927-lte/files/usr/sbin/we5927-lte dan mirror files/usr/sbin/we5927-lte identik. Fungsi network_manager_safe membaca service network dari procd, mengecek identitas executable netifd, PPID1, dan mewajibkan tepat satu PID netifd yang sesuai. Saat proses ganda atau tidak diketahui, daemon LTE mencatat network_manager_anomaly, tidak mengulang interface, mengganti SIM, mengirim CFUN, atau menyalakan ulang modem. Tidak ada tindakan kill otomatis yang berisiko salah PID.

Semua jalur ifup/ifdown umum di daemon diganti dengan operasi ubus khusus network.interface.lte up/down, dengan validasi kepemilikan dan LAN bridge. Internet tidak ditentukan dari sekadar usb0 carrier, DHCP IP, gateway, atau status ubus; pembuktian koneksi memakai HTTPS nyata melalui LTE. GUI baru memiliki networkHealth RPC hanya-baca yang menunjukkan netifd resmi dan ekstra, uptime, RAM, load, DHCP dan IP/rute tanpa membocorkan identitas SIM atau pengguna.

## 3. Empat menu utama GUI profesional

Beranda: Dashboard dan trafik; Kesehatan jaringan. Diagram alur modem-router-klien, status internet yang benar-benar diuji, grafik trafik kernel LTE, grafik RAM dari data nyata.

Koneksi: Ringkasan koneksi; LTE dan SIM; Wi-Fi; LAN dan DHCP; Pemantauan LTE. APN, failover SIM, pengaturan Wi-Fi, klien, kanal, security, DHCP leases, routing, dan speed test browser.

SMS Center: Kotak pesan; Status dan diagnostik. Inbox, sent, drafts, komposisi, diagnostik transport, konfirmasi eksplisit sebelum pengiriman.

Pengaturan: Sistem dan cadangan; DNS dan jaringan; Akses dan keamanan; Firmware dan addon. NTP, log, backup, cron, DNS, IPv6, SSH/HTTPS, firewall, verifikasi signature, paket yang disetujui.

Desain dibuat secara orisinal: sidebar navy, kartu putih-biru, menu horizontal responsif di ponsel, bantuan istilah awam, state belum diketahui tidak dipaksa PASS, tidak memakai CDN/font pihak ketiga. Fungsi lama dipertahankan dan ditata ulang, bukan hanya mockup.

## 4. Syarat kandidat firmware

Semua 39 modul aktif harus punya bukti source/test yang sah dan tidak di-skip; USSD sudah pensiun permanen dan tidak boleh dihidupkan kembali. Image harus punya kecocokan board exact, isi squashfs yang lengkap, ukuran NOR dan ruang cadangan, signature/trust anchor dan sysupgrade -T. Setelah flash aman, UAT fisik harus mencakup boot tunggal procd netifd, IP dan route LTE, HTTPS langsung dan DNS, LAN wired, Wi-Fi AP dan klien, SMS fisik, UX mobile/desktop, 72 jam stabilitas, tanpa reload atau modem reset otomatis. Flash dan OTA otomatis tidak diizinkan.

Sebelum pengembangan ini, source-completion-gate melaporkan 7/39 source verified, 70 blockers, build_permitted=false. Ini adalah gate bukti, bukan kesalahan kompilasi. Jangan menandai firmware final atau menyajikan .bin signed bila gate belum lulus. Pengembangan ini tidak mengubah router fisik.

## 5. Hasil regression dan build gate pada source terbaru

- scripts/tests: 419 tests selesai, OK, 5 skipped.
- tests: 38 tests selesai, OK.
- Rangkaian source dan package guard: shell syntax, UI JavaScript, HTML unique IDs, NetworkHealth procd mock, single/dual netifd scenario, source mirror identical.
- Pre-compile source gate terbaru: build_permitted=false, 7 dari 39 modul source_verified, 70 blocker. Build full image BELUM dijalankan karena gerbang bukti ini menolak. Jumlah blocker tidak diubah atau dinyatakan PASS secara manual.
- Versi paket berubah: we5927-lte release 12, veci-v2-runtime release 21, veci-v2-ui release 2. Nomor rilis paket bukan nomor firmware final.
- Tidak ada file .bin baru yang signed/flashable, router fisik tetap berjalan pada firmware sebelumnya yang internet LTE-nya telah pulih.

## 6. Bug tambahan gerbang build ditemukan dan diperbaiki

Gerbang source lama secara keliru mengecek 40 modul padahal kontrak aktif berisi 39 setelah USSD dipensiunkan. Perhitungan sekarang konsisten: ACTIVE_CORE_COUNT=39 dan retired_module_reintroduced diperlakukan sebagai penolakan. Ini hanya memperbaiki satu kesalahan jumlah; 70 blocker nyata lainnya masih ada, yaitu 32 modul belum source_verified, 32 belum memiliki bukti implementation/test, satu kesenjangan manifest bukti, serta lima SHA source yang berubah/stale. Data ini bukan izin bypass untuk menghasilkan firmware.


## 7. Koreksi penting: progres 7/39 bukan regresi 40/40 hardware

Audit Git historis membuktikan source-completion gate **40/40 PASS** pada commit 2bb593a tanggal 23 November 2026. Cabang firmware perbaikan LTE+GUI saat ini berasal dari baseline berbeda yang tidak menggabungkan commit tersebut. Penurunan 40/40 menjadi 7/39 terutama disebabkan oleh divergensi branch dan kehilangan manifest/source acceptance; bukan bukti 32 modul rusak. Perbandingan file juga menunjukkan 21 file historis hilang dan 31 file berubah hash sehingga sebagian fungsi perlu rekonsiliasi nyata. Referensi rincian: docs/WE5927-40-TO-39-GIT-BRANCH-DIVERGENCE-20261124.md. Pensiunnya USSD menjadikan target aktif 39, bukan rollback terhadap fitur lainnya.
