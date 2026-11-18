SETEX MONITOR — VERSI STATUS.ACT SAJA
Jalankan Jalankan_Monitor.bat dengan Python 3 pada Windows.
URL: ftp://172.16.120.113/Storage/sc777ce/
Isi username/password jika diperlukan; password tidak disimpan.
Baca sekali mengambil satu snapshot; Mulai cyclic mengulang setelah interval; Stop menghentikan pembaca. FTP minimal 30 detik; timeout bawaan 60 detik.

SUMBER
Hanya STATUS/STATUS.ACT. Tidak ada pembacaan ALARM.ACT, ALARMS.LOG, EVENTS.LOG, LINE, BATCH atau Config. Seluruh 10104 byte dibaca sementara ke RAM; tidak ditulis ke HMI. FTP hanya RETR (dengan login dan perintah protokol standar); shared access ditentukan server FTP. Lokal/SMB memakai GENERIC_READ dan FILE_SHARE_READ | FILE_SHARE_WRITE.

TAMPILAN
Mesin, nomor lot, kode resep (bisa kosong), deskripsi, kandidat nomor step, status raw, dua parameter suhu, dua gradien, parameter waktu mentah. Mapping target suhu/gradien hanya didukung snapshot E013 step 003 Temperature Control. Step lain tetap raw. Status raw bukan RUN/BREAK/END; waktu bukan countdown. Sensor aktual belum dipetakan.
Kuning BERUBAH membandingkan snapshot sukses sebelumnya pada path sama, beserta nilai lama. Jumlah byte berubah juga ditampilkan. Sumber berbeda memulai acuan baru. Kegagalan ditandai STALE.

PENYIMPANAN
Hanya tombol Simpan snapshot membuat pasangan JSON dan ACT pada disk lokal tetap. Pengaturan koneksi disimpan lokal otomatis. Tidak ada file sumber ditulis. Jangan memilih lokasi mesin sebagai tujuan simpan.

BATASAN
Pembacaan lengkap file bukan berarti seluruh struktur sudah didecode. Snapshot saat writer aktif belum tentu konsisten. Beban dan dampak terhadap HMI/Orgatex belum dijamin; uji Baca sekali dahulu.

DETAIL FLAG KANDIDAT 0x0020
Ditampilkan word UInt16 LE dalam hex/biner; bit 4 (0x10), bit 7 (0x80), bit 5 (0x20), bit 6 (0x40), serta OR bit 4/7. Nilai SET/CLEAR dan perubahan dibanding snapshot sebelumnya juga tersimpan dalam JSON melalui fault_word_raw dan fault_bits.
ErrorEN.txt E013 mengonfirmasi teks kode 90 PLC offline, 91 Stop alarm activ, 92 Hold alarm activ. Hubungan bit dengan field file 0x20 BELUM dibuktikan dari executable/controller. Alamat 0x1462c3/0x15189f/dll yang diberikan pengguna bukan offset langsung file STATUS.ACT dan belum dianalisis.
Snapshot E013 lokal yang diperiksa bernilai 0x0001, jadi bit 4–7 CLEAR. CLEAR tidak menjamin PLC online atau bebas alarm. Jangan sengaja memutus PLC atau memicu alarm untuk pengujian.

FORMAT 11C 10188 BYTE
Program menerima dua ukuran: 10104 dan 10188 byte. Ukuran lain ditolak; pembacaan dibatasi 10189 byte agar oversize terdeteksi.
Format 10188: identitas tetap memakai offset awal; pola blok 0x154 dengan stride 205. Kandidat nomor step pada 0x15E ditampilkan sebagai belum terverifikasi HMI. Suhu/gradien/waktu memakai offset E013 tidak dibaca pada format ini, sehingga tidak ada angka keliru yang ditampilkan sebagai parameter.
Pemetaan flag 0x20 tetap kandidat untuk kedua format. Batas ukuran bukan penanda versi firmware resmi.

REVISI ALARM.ACT
Setiap Baca sekali atau cyclic kini membaca STATUS.ACT dan ALARM.ACT dari folder STATUS yang sama. FTP menggunakan satu sesi login dengan dua RETR. Tidak membaca ALARMS.LOG, EVENTS.LOG atau BATCH.
ALARM.ACT wajib 34 byte; tabel menampilkan hex serta 17 word UInt16 LE. Data belum didecode sebagai nomor alarm aktif. Perubahan kuning hanya trigger perubahan mentah, bukan konfirmasi alarm ON/OFF; metadata/counter juga dapat berubah. Jangan menganggap word pertama nonzero berarti trip.
Jika ALARM.ACT gagal, STATUS.ACT tetap ditampilkan dengan baris ALARM GAGAL/STALE. Timeout total tetap berlaku. Sumber dibaca berurutan, bukan snapshot atomik.
JSON Simpan snapshot menyertakan alarm_act (hex/words/error); file .ACT yang disimpan tetap STATUS.ACT. Tidak otomatis membuat file ALARM.ACT di PC.

TOMBOL MANUAL BACA ALARMS.LOG
Tombol terpisah menghentikan cyclic, lalu membaca hanya STATUS/ALARMS.LOG dari sumber yang sama. Jika worker lain masih berjalan, tunggu atau klik Stop. Tidak ada polling ALARMS.LOG otomatis.
File masuk RAM tanpa penulisan ke HMI atau penyimpanan otomatis. Jendela menampilkan ukuran dan preview hex dengan offset, maksimum preview 64 KiB; batas transfer 4 MiB. Ukuran tidak dikunci 16896 byte.
Klaim T_ALARMLOG_REC_V2 berukuran payload 34 byte belum diverifikasi terhadap struktur halaman database. Preview bukan daftar alarm terdecode; tidak menebak timestamp/kode/state ON-OFF dari potongan 34 byte.
Tekan Mulai cyclic lagi jika ingin melanjutkan STATUS.ACT + ALARM.ACT.

DECODE KANDIDAT RIWAYAT ALARM
Baca ALARMS.LOG membuka tab Kandidat riwayat dan Hex mentah. Tabel berisi nomor alarm kandidat, waktu mulai/selesai, durasi HH:MM:SS, offset payload dan tipe raw, diurutkan terbaru dahulu.
Pola waktu 6 byte adalah tahun sejak 1900, bulan, tanggal, jam, menit, detik. Kandidat kode UInt16 LE ditemukan 6 byte sebelum waktu mulai. Pasangan nomor/waktu telah cocok dengan beberapa baris HMI pada ALARMS.LOG 11 November 2026. Duplikat pasangan kode/waktu disatukan.
Ini pemindaian kandidat, bukan parser Btrieve lengkap atau pemotongan record tetap 34 byte. False positive dan entri terlewat masih mungkin. Alarm tanpa waktu selesai, nama alarm, state aktif, arti tipe dan acknowledgment belum dipetakan. Hasil kosong tidak membuktikan bebas alarm. Log hanya dibaca manual; cyclic tetap STATUS.ACT + ALARM.ACT.

TOTAL KONSUMSI KANDIDAT
Untuk format 10104 byte, tabel dan JSON consumption menambahkan lima Float64 little-endian 8 byte: air 1 0x2608; air 2 0x2610; air 3 0x2618; air 4 0x2620; energi listrik 0x2630. Unit kandidat L dan kWh (energi, bukan daya atau kW/h). Perubahan dibanding snapshot sebelumnya ditandai kuning.
Nilai biner backup 13E cocok: 148097707; 54659455; 1972; 2007; 433922.7398345843. Pembanding 12B dan 6A juga cocok dengan angka yang diberikan. Nama kanal dan satuan belum divalidasi langsung terhadap layar Total Consumption; mapping_verified=false dalam JSON.
Format 10188 byte tidak memakai offset konsumsi ini karena belum dipetakan. Tidak ada file tambahan atau transfer baru; nilai berasal dari STATUS.ACT yang sudah dibaca. STATUS.PRV tidak diambil otomatis.
