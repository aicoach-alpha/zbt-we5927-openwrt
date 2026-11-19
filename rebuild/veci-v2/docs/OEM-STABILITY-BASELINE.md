# Baseline stabilitas WE2825-2SIM

Pada 19 November 2026 pemilik melaporkan Wi-Fi dan Internet stabil dengan firmware pabrik. Durasi dan hasil pengukuran belum tercatat. Identitas modem yang dilaporkan adalah QUALCOMM 4108, hardware W907_CE 20240826A. Board router yang dilaporkan sebelumnya memakai MediaTek MT7628AN.

Lampiran WE2825-2SIM_V26.03.04_V26.08.09.bin berukuran 7.471.108 byte. SHA-256 file unggahan dan salinan vendor-research pada andre-nas sama, yaitu 80529b8e9c31d686eb7f63a1517d6dbcf781f26cb4aceb7b8b1ff27c2d51d1f9. Hash cocok dengan contracts/oem-we5927-2sim.json. Header uImage menyebut MIPS LEDE Linux-4.4.61.

## Wi-Fi

Di rootfs OEM, lib/wifi/mt7628.sh menghasilkan konfigurasi default_radio0 pada ra0, mode AP 2,4 GHz, terhubung ke LAN. Template memakai beacon 100, DTIM 1 dan channel 0. Profil etc/wireless/mt7628/mt7628.dat berisi Channel=6, AutoChannelSelect=0, HideSSID=0, BeaconPeriod=100 dan DtimPeriod=1. Kanal aktif pada unit stabil perlu diukur. Konfigurasi tersimpan dan urutan inisialisasi vendor dapat memengaruhi hasil.

## LTE dan pembandingan pada unit identik

Provider VeCI memilih port kontrol berdasarkan identitas USB 05c6:902e dan interface yang dikenali. Hubungan antara identitas itu dan label W907_CE perlu dikonfirmasi dari enumerasi perangkat. Pada unit uji, rekam VID/PID, nomor interface, driver data dan kontrol, slot SIM, waktu dari cold boot hingga DHCP serta hingga akses Internet terkonfirmasi lewat modem. Redaksi IMEI, ICCID dan kredensial sebelum menyimpan bukti.

Gunakan klien, lokasi, SIM/operator dan kondisi WAN yang sama untuk OEM dan VeCI. Catat waktu beacon pertama, asosiasi klien dan akses LAN, kehilangan SSID, putus koneksi LTE serta hasil pemulihan. Jalankan gate ketahanan 72 jam yang ada pada kandidat VeCI. Pengamatan pemilik menjadi pembanding awal. Catat pengukuran fisik dan SHA image secara terpisah untuk setiap firmware.
