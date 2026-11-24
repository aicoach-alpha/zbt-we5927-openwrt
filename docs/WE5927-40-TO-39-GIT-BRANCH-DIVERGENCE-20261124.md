# Audit regresi progres 40/40 menjadi 7/39 — 24 November 2026

## Kesimpulan utama
Penurunan statistik source-verified 40/40 menjadi 7/39 BUKAN hasil audit kegagalan 32 fitur. Dua cabang divergen dan riwayat 40/40 tidak diintegrasikan ke cabang VeCI v2 pengembangan LTE+GUI.

- Commit 6252464 (23 Nov 2026, 11:43 +0700): kontrak 40/40 source_verified, manifest 40/40 pass.
- Commit 2bb593a133261de0fc2cd5e78e61f574ea1137d4 (23 Nov 2026, 13:43 +0700): masih memuat 40 module source_verified dan 40 manifest pass. Pemeriksaan ulang gate di checkout historis **exit 0**, **build_permitted true**, **40/40**, **0 blockers**. Ini bukti source gate, BUKAN bukti UAT fisik 40/40.
- Commit 0f52d71 (24 Nov 2026, 10:11 +0700): berasal dari garis sejarah lama dengan 8/40 source_verified; setelah pengguna memensiunkan USSD, tercatat 7/39. **2bb593a bukan ancestor 0f52d71**; merge-base di 04e8058, sehingga integrasi 40/40 tidak pernah terbawa ke cabang ini.
- Commit 8c74067 (24 Nov 2026, 16:21 +0700): melanjutkan cabang 7/39 dan keliru mengutip angka ini sebagai progress implementasi. Penambahan pencegahan LTE dan GUI bukan penyebab hilangnya catatan baseline.

## Pemeriksaan terukur sumber historis vs current
Semua 39 nama modul aktif saat ini ada dalam baseline manifest 40/40. Satu nama yang dikeluarkan karena keputusan pengguna ialah lte_ussd (dipensiunkan secara permanen). Dari file dan hash yang diikat ke 39 rekaman baseline:
- **21 file baseline tidak ada di cabang saat ini**, terdiri dari **7 file implementasi/antarmuka** (observabilitas dan restore) serta **14 file uji dan pendukung**.
- **31 file baseline ada, tetapi telah berubah hash** (termasuk perubahan yang memang diminta seperti LTE dan GUI).
- **3/39 modul** secara utuh masih cocok dengan semua hash baseline. Ini bukan ukuran jumlah modul bekerja; hash yang berbeda hanya berarti bukti sumber historis tidak berlaku otomatis.
- **7/39** adalah hitungan manifest current yang tersisa dan berstatus verified; **70 blocker** pada current source-completion gate sebagian besar merupakan catatan/verifikasi yang tidak ikut digabung, bukan 70 gangguan nyata router.

## Perbaikan yang benar dan aman
1. Jadikan commit 2bb593a baseline verifikasi source resmi yang tidak dihapus atau diturunkan tanpa diagnosis. Riwayat 40/40 tidak boleh dipresentasikan sebagai 7/39 kemajuan keseluruhan.
2. Rekonsiliasi **39 fitur aktif** dari cabang yang lulus 40/40, dengan komparasi perubahan per file. JANGAN menghidupkan kembali USSD.
3. Pulihkan hanya implementasi dan uji yang aman dan masih diperlukan. File observabilitas dan restore yang terhapus perlu review keamanan, bukan copy otomatis.
4. Pertahankan revisi LTE pada commit 8c74067, empat menu GUI dan semua bukti UAT fisik yang relevan. Jangan mengembalikan operasi jaringan berbahaya atau image sebelumnya yang belum terverifikasi.
5. Jalankan ulang pengujian terfokus dan regenerasi source hashes/log receipts **hanya setelah benar-benar dieksekusi** pada file saat ini. Selanjutnya jalankan gate 39 modul dan inspeksi image ROM.
6. 40/40 source verified dan 39/39 source verified **tidak sama dengan** hardware UAT berhasil, signed image dibuat, sysupgrade -T lulus pada image terbaru, atau ketahanan 72 jam.

## Status tindakan saat catatan dibuat
- Baseline 2bb593a diverifikasi secara terpisah pada NAS tanpa menyentuh router.
- Cabang 8c74067 masih belum di-merge dengan baseline; 39/39 belum direkonsiliasi.
- Tidak ada firmware baru, flash, reset, atau perubahan pada satu router fisik.
- Status current source gate tidak digunakan lagi untuk menyimpulkan bahwa 32 fitur rusak.
