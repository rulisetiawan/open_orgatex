# Controller v0.9.5 — Intervent fungsi

Jalankan JALANKAN_CONTROLLER_V095.bat. Tutup aplikasi lama lalu buka ulang agar kode baru dimuat.

1. Pilih LIVE Controller, isi IP 172.16.120.113 dan port 50000.
2. Tunggu step tujuan aktif pada HMI. Pilih Fill 713, Temperature 141, atau Drain 71 lalu Baca fungsi.
3. Isi **Slot aktif (1–13)**. Slot bukan nomor step program dan bukan P1/P2/P3. Log historis ketiga fungsi menunjukkan slot 1; gunakan 1 hanya pada konteks yang sama. Pembacaan dengan baris query 0 belum menentukan slot aktif secara otomatis. Jangan mencoba seluruh slot secara berurutan.
4. Pilih parameter dari tabel atau dropdown, masukkan nilai dalam satuan tampilan. Untuk Fill P2, isi batas min/maks liter sesuai HMI dahulu. Kode jenis air dan kode drain tetap baca saja.
5. Klik Konfirmasi ubah. Dialog menampilkan tujuan, slot dan nilai lama/baru serta urutan Manual → Simpan → Selesai. Konfirmasi menjalankan seluruh urutan sekali.
6. Amati status setiap tahap dan nilai baca ulang. Cocokkan dengan HMI; rekam ARCNET untuk pengujian pertama.

## Perubahan protokol

Jalur utama sekarang 109/3 → 106/6 (payload fungsi 64 byte, enam float, slot eksplisit) → 110/3. Object 41 tidak dipakai jalur UI Intervent. Keenam nilai dibaca ulang sebelum masuk dan setelah masuk Manual; hanya parameter pilihan yang diubah. Slot/fungsi tidak cocok harus ditolak Controller, tanpa pencarian slot atau fallback otomatis.

Setelah ACK masuk Manual, program selalu mencoba keluar melalui 110/3, termasuk ketika simpan gagal atau Stop ditekan. Jika masuk Manual timeout, program tidak meneruskan simpan dan tidak menganggap sesi dimilikinya. Jika status Manual belum pasti, periksa dan selesaikan lewat HMI. ACK bukan bukti nilai fisik sudah berubah; baca ulang tetap diperlukan. Tidak ada retry otomatis.

Log TX/RX tetap di controller_packets.jsonl di folder aplikasi. Saat gagal, simpan log dan screenshot status lengkap, catat step aktif dan slot yang diisi.

Urutan didasarkan pada analisis biner yang diberikan dan rekaman ARCNET. Versi ini diuji lokal dengan respons simulasi; penerimaan jalur TCP di mesin belum terverifikasi. Jangan menjalankan Intervent HMI dan program bersamaan selama uji.
