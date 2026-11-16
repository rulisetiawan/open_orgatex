# Versi terbaru: v0.9.3

Jalankan JALANKAN_CONTROLLER_V093.bat. Petunjuk terbaru ada pada PETUNJUK_V093.md.
Fill P2 kini dapat diubah dengan batas min/maks yang diisi pengguna sesuai HMI. Judul versi telah diperbaiki. 40 tes lokal lulus; belum diuji ke PLC fisik. Bagian berikut adalah catatan versi sebelumnya.

# SETEX Controller v0.7 — Intervent per fungsi, profil 13E

Tutup aplikasi lama dan jalankan JALANKAN_CONTROLLER_V07.bat.

Panel Intervent sekarang memiliki pilihan:
- 141 - Temperature Control: P1 suhu, P2 gradien, P3 waktu.
- 71 - Drain Percent: P1 level akhir (%), P3 waktu. P2 kode drain ditampilkan
  dan dipertahankan dari pembacaan, belum boleh diedit karena tabel enum
  pilihan drain belum diurai lengkap.

Pilih fungsi yang sesuai dialog proses HMI, klik Baca fungsi, cocokkan nilainya,
lalu pilih parameter dan masukkan nilai dalam satuan tampilan. Mengganti fungsi
menghapus snapshot lama sehingga wajib membaca kembali sebelum perubahan.
Pembacaan fungsi terpilih bukan deteksi otomatis fungsi yang sedang aktif.

Error API 19 / error 62 sekarang diterangkan sebagai kesalahan pengolahan
program / Invalid status. Error ini BELUM terselesaikan; penambahan pilihan
Drain Percent tidak membuktikan SV_CHANGE akan diterima.
Belum diketahui apakah penolakan berasal dari keadaan proses, mode Intervent,
atau konteks target yang masih berbeda dari HMI. Tidak ada pemasukan PIN,
login, SV_SET_MANUAL atau SV_RESET_MANUAL otomatis. Tidak ada retry otomatis.

Jika status tetap ditolak, diperlukan pembandingan status/konteks saat
Intervent normal melalui HMI. Simpan log sebelum dan sesudah tindakan HMI
untuk analisis. Tidak ada perintah perubahan dijalankan oleh pengembang.

30 tes lokal lulus; ini bukan validasi pengubahan parameter pada mesin fisik.
Petunjuk v0.6 berikut tetap berlaku, dengan tambahan pilihan fungsi di atas.
# SETEX Controller v0.6 — Intervent proses eksperimental

Tutup aplikasi lama, lalu jalankan JALANKAN_CONTROLLER_V06.bat.
Judul: SETEX Controller v0.6 - Intervent eksperimental.
Default tujuan tetap 172.16.120.113:50000. Tidak ada koneksi saat aplikasi dibuka.

## Mengubah parameter Temperature Control

1. Pilih LIVE Controller dan isi IP/port mesin yang benar.
2. Pada panel Intervent proses klik **1. Baca fungsi**.
3. Hasil harus menampilkan Temperature Control fungsi 141 serta P1/P2/P3
   yang cocok dengan fungsi proses pada HMI. Bila gagal baca/layout tidak
   cocok, aplikasi tidak mengirim SV_CHANGE.
4. Pilih P1 - Suhu (°C), P2 - Gradien (°C/min), atau P3 - Waktu (min).
5. Isi nilai baru dalam satuan tampilan, misalnya 50 untuk 50 °C. Jangan
   mengisi 3333 atau 3500 sebagai pengganti °C. Desimal dapat memakai titik/koma.
6. Klik **2. Konfirmasi ubah**. Dialog menampilkan IP, function ID, baris
   fungsi dan tiga nilai sebelum/sesudah. Pastikan fungsi yang dimaksud aktif.
7. Setelah konfirmasi, aplikasi membaca ulang. Perubahan konteks/nilai akan
   membatalkan permintaan. Jika tetap sama, dikirim satu SV_CHANGE, kemudian
   fungsi dibaca ulang. Untuk perubahan berikutnya klik Baca fungsi lagi.

Ini memakai jalur fungsi **SV_CHANGE 106 / object 6**, bukan write SET 3 dan
bukan jalur parameter object 41 yang konteksnya belum terurai. Template
berasal dari Api_Rem_ReadFunction dan Api_ChangeFunction pada binary 13E,
serta pemanggilan Api_ChangeFunction dari sc777ce.exe. Baris fungsi diambil
langsung dari balasan pembacaan, bukan nomor step 003 pada daftar program.

Dukungan dibatasi Temperature Control 141, profil konfigurasi 13E:
P1 0..150 °C, P2 0..9.9 °C/min, P3 0..180 min. Parameter lain dalam pesan
fungsi dipertahankan nilainya dari pembacaan; hanya pilihan Anda yang diubah.
Metadata request mengikuti builder HMI, bukan menyalin field opaque balasan.

**Kompatibilitas online masih eksperimental.** Respons 64 byte diparsing
sesuai layout fungsi hasil penelusuran API; belum ada pengujian fisik jalur
fungsi ini dari lingkungan pengembang. Jika layout respons berbeda, kirim
controller_packets.jsonl untuk diperiksa; jangan menganggap parser ini sudah
membuktikan pemetaan target pada semua firmware.

Fitur ini ditujukan untuk parameter fungsi proses. Tidak menyimpan/mengedit
resep PRG di disk dan belum menjamin semua halaman display berubah otomatis.
Setelah uji pertama, cocokkan parameter proses pada HMI dan nilai SET terkait.
Aplikasi tidak membuka menu HMI dan tidak mengirim keyboard/mouse.

Tidak ada retry/rollback otomatis. Timeout sesudah pengiriman berarti hasil
belum pasti; perintah mungkin sudah diterapkan. Stop tidak menarik kembali
perintah yang sudah dikirim. Pemeriksaan sebelum perubahan bukan transaksi
atomik dengan PLC. Pembacaan fungsi saja belum membuktikan fungsi itu aktif;
aktivitasnya masih harus Anda cocokkan pada mesin.

Validasi lokal v0.6: 28 tes lulus (respons uji buatan). Tidak ada SV_CHANGE
ke mesin fisik dilakukan dalam pengembangan ini.

## Fungsi register dari v0.5

Fitur baca dan SV_WRITE tetap tersedia melalui panel terpisah. Petunjuk v0.5
berikut berlaku untuk register, bukan untuk panel Intervent baru.
# SETEX Controller v0.5 — Read / Write

Tutup jendela lama lalu jalankan JALANKAN_CONTROLLER_V05.bat (atau JALANKAN.bat).
Judul baru: SETEX Controller v0.5 - Read / Write.
Default IP 172.16.120.113, port 50000. Python 3.10+ dengan tkinter;
tidak membutuhkan paket pip untuk menjalankan aplikasi.

## Write satu alamat

1. Pilih LIVE Controller dan objek IW, ACT, SET, LW, atau MW.
2. Pilih Satuan, isi satu alamat saja, lalu pilih Sekali.
3. Isi Nilai mentah baru (0..65535), bilangan bulat desimal.
4. Klik Baca nilai lama → Konfirmasi write.
5. Dialog menampilkan IP/port, objek/ID, alamat, nilai lama, nilai baru dan hex.
   Pilih Ya untuk mengirim atau Tidak untuk membatalkan.
6. Aplikasi membaca nilai lama kembali. Jika berubah selama konfirmasi,
   write dibatalkan agar Anda dapat memeriksa dan mengonfirmasi ulang.
7. SV_WRITE dikirim satu kali, lalu alamat yang sama dibaca ulang.

Tombol Mulai baca tetap hanya membaca. Pilihan Perintah mengatur pembacaan;
tombol write terpisah selalu memakai SV_WRITE (2).

Nilai adalah uint16 mentah, belum konversi °C, persen, faktor skala, atau
bilangan signed. Arti dan izin alamat tergantung program PLC mesin.
ACT atau register lain dapat ditimpa kembali oleh program PLC; baca ulang
hanya menggambarkan nilai pada saat itu. Pemeriksaan nilai lama bukan operasi
compare-and-swap atomik di PLC; nilai masih bisa berubah setelah pemeriksaan.

Versi ini tidak menyediakan write blok, daftar, cyclic, bit, retry, rollback,
atau pengembalian nilai lama otomatis. Stop sebelum pengiriman membatalkan;
setelah write dikirim Stop tidak dapat menarik kembali perintahnya.

## Arti hasil write

- ACK diterima + baca ulang cocok: respons write lolos pemeriksaan dan nilai
  hasil baca sama dengan yang diminta pada saat itu.
- Nilai baca ulang berbeda: aplikasi menampilkan nilai aktual, bukan memaksa
  hasil menjadi nilai yang diminta.
- Timeout / ACK tidak valid: hasil write belum pasti. Perintah mungkin sudah
  diterapkan. Tidak ada pengiriman ulang otomatis; aplikasi mencoba baca ulang.
- Baca ulang gagal/dihentikan: hasil belum terkonfirmasi. Jangan menyimpulkan
  mesin tidak berubah hanya karena aplikasi menampilkan error.

## Membaca data

Pilih SV_READ, objek, alamat, Sekali atau Cyclic, lalu Mulai baca.
Tulis 10,20,30,40 untuk alamat terpisah; kolom jumlah dan pilihan Satuan/
Lebih dari 1 diabaikan ketika ada koma. Daftar dibaca satu per satu dengan
jeda 1 detik. Untuk rentang, tulis alamat awal dan pilih Lebih dari 1 serta
jumlah. SV_READ_BLOCK hanya untuk rentang berurutan, maksimal 80 alamat.
Interval cyclic minimal 1 detik setelah satu siklus selesai.

| Objek | ID | Arti |
| --- | --- | --- |
| IW | 1025 | Info Words |
| ACT / IST | 1010 | Nilai aktual |
| SET / SOLL | 1009 | Nilai target/setpoint |
| LW | 1001 | Link Words |
| MW | 1058 | Memory Words |

Alamat masing-masing objek terpisah: ACT 1 tidak berarti sensor yang sama
dengan IW 1. Menu SET adalah kelompok data target, bukan perintah write.

Mode SIMULASI hanya untuk pembacaan angka buatan dan diberi label pada tabel
serta CSV. Tidak ada fallback dari LIVE ke angka simulasi. Decoder bit dan
SV_READ_LIST LIVE belum diimplementasikan.

## Koneksi, log, dan validasi

Tes TCP saja membuka/menutup koneksi tanpa payload aplikasi. Aplikasi tidak
menghubungi jaringan saat dibuka. Semua koneksi dilakukan setelah aksi Anda.
controller_packets.jsonl mencatat TX/RX, waktu, IP/port, termasuk balasan parsial.
Ekspor CSV menyimpan maksimal 5000 baris terakhir; baris hasil baca ulang write
ditandai LIVE baca ulang write. Arsipkan log saat aplikasi berhenti bila membesar.

Implementasi Controller masih eksperimental, hasil penelusuran statis DLL 6A:
- RCClient.ini: Controller_Port=50000, RCServer_Port=50010.
- Commands.csv: SV_READ (1), SV_WRITE (2), SV_READ_BLOCK (11) untuk objek word.
- Api_ReadPLCWord/Words: payload alamat uint16 / alamat+jumlah uint16.
- Api_WritePLCWord → fungsi internal RVA 0x17474 pada
  SecomCE_D_BackGround_2d.dll: service 2, panjang payload 4, alamat uint16
  pada offset 20, nilai uint16 pada offset 22.
- SecomCE_TCP_2d.dll mengirim frame tetap 516 byte. Header panjang data berada
  di offset 18, payload mulai offset 20. Format ini berbeda dari campuran
  header 74 byte pada dokumen perencanaan awal.
- Balasan diperiksa magic, panjang, jenis respons, service, dan object ID.
  Format ACK write pada mesin target masih harus diverifikasi melalui pengujian.

Validasi lokal: python -m unittest -v; 21 tes lulus. Termasuk layout write,
penolakan nilai invalid, batal konfirmasi, nilai lama berubah, stop sebelum
pengiriman, sekali kirim tanpa retry saat timeout, dan baca ulang gagal.
Respons pengujian dibuat lokal. Pengembang tidak melakukan write ke PLC fisik.



## v0.8 — tiga fungsi proses
Jalankan JALANKAN_CONTROLLER_V08.bat. Tambahan pilihan 713 - Fill Level (liter), sesuai profil 13E dengan P1 ID 7 jenis air dan P2 ID 9 volume liter. Profil lain bernama Fill Level (ID 21) memakai level digital dan tidak sama dengan tampilan 8000 L. ID 713 masih kandidat untuk screenshot mesin tujuan; cocokkan hasil Baca fungsi. Fill 713 baru baca saja karena batas P2 bersifat dinamis lewat index konfigurasi 3/4, belum dipetakan. Tidak diisi batas volume tebakan. Temperature Control 141 dan Drain Percent 71 tetap eksperimental; error Invalid status belum diperbaiki. 31 tes lokal lulus.

## v0.9 — tabel parameter dari balasan
Jalankan JALANKAN_CONTROLLER_V09.bat. Sesudah Baca fungsi, tabel memperlihatkan enam slot P1..P6, ID dari balasan Controller, nama berdasarkan ID, nilai, satuan dan status. Scroll tabel untuk slot berikutnya. Klik baris yang tersedia untuk memilih parameter, lalu isi nilai baru pada kolom input di sebelahnya. Slot ID nol ditandai tidak dipakai/tidak dilaporkan. Slot dengan ID berbeda dari profil ditampilkan tetapi tidak boleh diubah. Nomor P adalah posisi; ID parameter adalah identitas, dan angka Step adalah posisi langkah program. Snapshot mencatat enam ID dari offset frame 29+8*i; slot P1/P2/P3 suhu ID 3/4/5 cocok dengan log mesin dan konfigurasi 13E. Nama/satuan ID yang belum dikenal tidak ditebak. Fill Level tetap baca saja. Versi ini memperbaiki tampilan dan pemeriksaan ID; belum memperbaiki error Invalid status. Penelusuran menunjukkan ProcessInfo memakai ServiceAPI_ChangeParameters/Api_ChangeParameterExtended, berbeda dengan jalur perubahan fungsi object 6 yang sekarang masih eksperimental. Belum ada SV_CHANGE object 41 atau mode manual otomatis. 33 tes lokal lulus.

## v0.9.1 — sumber nilai dan kontrol baca saja
Jalankan JALANKAN_CONTROLLER_V091.bat. Panel dilabeli Nilai fungsi Controller, bukan pembacaan Program List/PRG. Log 11:32 mencatat Fill 713 P2 8000, lalu 11:33 dan 11:48 menjadi 4000 (ID 9). Ini membuktikan 4000 berasal dari respons Controller; tidak membuktikan bahwa nilai program PRG harus sama. Tampilan Program List adalah sumber berbeda yang belum dibaca aplikasi. Cocokkan dengan dialog proses Fill saat fungsi tersebut aktif untuk menyelidiki perbedaan. Tombol perubahan dan input nilai dinonaktifkan bila hanya baca, termasuk Fill. Mengganti fungsi menghapus input lama; memilih baris/parameter mengisi nilai saat ini agar tidak membawa nilai dari fungsi lain. Pesan baca sukses tidak lagi menyuruh mengubah P1/P2/P3 untuk fungsi yang hanya baca. Error 62 masih belum selesai. 33 tes lokal lulus.


## v0.9.4 — uji SV_CHANGE 106 / object 41
Jalankan JALANKAN_CONTROLLER_V094.bat. Controller target menolak 137/41 dengan API 19 / Error 66 Invalid service; klaim versi sebelumnya bahwa jalur itu pasti cocok tidak dibuktikan pengujian fisik. Versi ini memakai Api_ChangeParameters: 106/41, payload 124 byte, flag 1, count 1, ID parameter dari snapshot, float32 satuan tampilan. Ini BUKAN 106/6 yang pernah ditolak Error 62. Commands.csv memuat 106/41 untuk mengubah parameter. Target extra wajib nol untuk 106 karena field extended tidak dipakai. Tidak ada fallback atau percobaan service lain otomatis. Aplikasi membaca ulang parameter sebelum dan sesudah satu pengiriman yang Anda konfirmasi. Fill tetap memerlukan batas min/maks yang diisi sesuai HMI. 42 tes lokal lulus; belum dilakukan perubahan ke mesin fisik dari lingkungan pengembang. Hasil penerimaan 106/41 masih perlu dibuktikan pada target.
