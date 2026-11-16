# v0.9.6 — Baca status dan alarm

Tutup versi lama. Jalankan JALANKAN_CONTROLLER_V096.bat.

1. Isi IP dan port mesin, pilih LIVE Controller.
2. Pada Pembacaan pilih Sekali atau Cyclic. Untuk Cyclic isi interval minimal 1 detik.
3. Pilih detail 65 (bitmask ID 1–2000, bawaan) atau 67 (daftar maksimal 100 ID).
4. Klik **Baca status / alarm**, bukan Mulai baca. Tombol Mulai baca tetap untuk register IW/SET/ACT dan lainnya.
5. Hasil muncul pada tabel bawah: jumlah alarm, ID alarm utama, flag komunikasi/Stop/Halt mentah, lalu ID detail alarm aktif.
6. Klik Stop untuk mengakhiri cyclic. Ekspor CSV menyimpan snapshot status/alarm terakhir.

Objek, alamat dan jumlah register tidak dipakai oleh tombol status/alarm. Pilihan Sekali/Cyclic dan interval di bagian atas dipakai bersama. Interval cyclic adalah jeda setelah pembacaan selesai, sehingga periode aktual termasuk waktu transaksi.

Program mengirim 112/0 tanpa payload. Jika NumberOfAlarms > 0, dilanjutkan 1/65 atau 1/67, juga tanpa payload. Tidak ada perintah reset/acknowledge alarm atau perubahan proses pada fitur ini. Log TX/RX masuk controller_packets.jsonl. Layout 13E berasal dari laporan analisis yang diberikan; kompatibilitas balasan mesin masih harus diverifikasi saat tes pertama.

Jumlah nol berarti Controller melaporkan nol alarm aktif dalam snapshot itu, bukan jaminan kondisi mesin aman. Nama, tingkat bahaya, dan kategori ID belum dipetakan. Flag Stop/Halt ditampilkan mentah agar tidak menebak semantiknya. Jumlah dapat berubah di antara permintaan ringkasan dan detail; perbedaan ditandai. Kegagalan baca menghentikan cyclic dan menandai hasil sebelumnya bukan status terkini. Kegagalan detail mempertahankan ringkasan dengan pesan bahwa detail belum terbaca.

Tabel selalu berisi snapshot terbaru, sehingga alarm yang hilang tidak tertinggal. Riwayat respons tetap ada dalam log paket. Objek 67 ditandai terpotong bila jumlah aktif melebihi 100; gunakan 65 untuk rentang ID 1–2000.

Intervent Fill/Temperature/Drain dan pembacaan register tetap tersedia sebagaimana v0.9.5; lihat PETUNJUK_V095.md.
