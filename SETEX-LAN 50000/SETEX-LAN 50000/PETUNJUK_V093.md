# v0.9.3 — Fill / Temperature / Drain

Tutup jendela lama, jalankan JALANKAN_CONTROLLER_V093.bat.
Judul harus SETEX Controller v0.9.3 - Fill / Temp / Drain.
IP awal tetap 172.16.120.113:50000. Tidak ada pengiriman otomatis saat dibuka.

## Mengubah volume Fill

1. Pilih LIVE Controller dan fungsi 713 - Fill Level (liter).
2. Klik Baca fungsi; cocokkan P1/P2 dengan dialog proses HMI.
3. Isi **Batas Fill dari HMI (L): min / maks** sesuai batas yang benar untuk
   mesin. Nilai ini berasal dari input Anda, BUKAN hasil deteksi kapasitas
   otomatis. Kolom sengaja kosong. Nilai resep 8000 L bukan bukti batas kapasitas.
4. Pilih P2 - Volume isi (L), isi nilai baru dalam liter.
5. Klik Konfirmasi ubah. Dialog menunjukkan IP, ID parameter 9, nilai lama,
   nilai baru, dan batas yang Anda isi. Konfirmasi jika benar.
6. Aplikasi membaca ulang sebelum pengiriman, mengirim satu perubahan
   SV_CHANGE_EXTENDED 137 / object 41, lalu membaca hasilnya kembali.

Jika min/maks belum valid, tombol ubah dan input nilai baru tetap nonaktif.
Rentang harus 0 ≤ min < maks dan berupa angka finite. Input tidak disimpan
ke konfigurasi mesin; pemeriksaan limit Controller tetap menentukan penerimaan.
Jika batas mesin belum diketahui, jangan mengisinya berdasarkan tebakan.

## Temperature dan Drain

- Temperature Control 141: P1 suhu °C, P2 gradien °C/min, P3 waktu menit.
- Drain Percent 71: P1 level akhir %, P3 waktu menit.
- Jenis air Fill dan kode jalur Drain tetap baca saja: tabel enum belum lengkap.

Setiap kali langkah berganti, pilih fungsi yang sesuai dan klik Baca fungsi
lagi. Aplikasi belum mendeteksi pergantian step atau mengirim perubahan step
berikutnya secara otomatis. Setiap perubahan memerlukan snapshot dan konfirmasi
baru. Jangan menafsirkan bacaan fungsi terpilih sebagai bukti fungsi aktif.

## Hasil dan keterbatasan

Jalur perubahan baru berasal dari penelusuran statis API ProcessInfo/controller;
kompatibilitas fisik dan efek tampilan harus diuji pada mesin. Tes lokal tidak
membuktikan keberhasilan perubahan proses. Status ACK dan hasil baca ulang
ditampilkan, tanpa fallback ke simulasi dan tanpa retry/rollback otomatis.
Timeout setelah kirim dapat berarti nilai sudah diterapkan; jangan langsung
mengulang. Semua frame dicatat di controller_packets.jsonl.

Perubahan ini ditujukan untuk parameter proses dan batch berjalan, bukan
penyuntingan file resep master PRG permanen. Tidak ada perpindahan mode manual,
pengiriman PIN, remote keyboard/mouse, atau perintah start/stop otomatis.

Validasi v0.9.3: 40 tes lokal lulus; termasuk layout ID 9/float liter,
keharusan limit eksplisit, penolakan di luar batas tanpa koneksi, dan sekali kirim.
Pengembang tidak mengirim perubahan ke mesin fisik pada revisi ini.
