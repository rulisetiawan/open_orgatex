# v0.9.7 — Status dan detail alarm dipisahkan

Tutup aplikasi lama, jalankan JALANKAN_CONTROLLER_V097.bat.

1. Isi IP/port, pilih LIVE Controller.
2. Pilih Pembacaan Sekali atau Cyclic dan interval minimal 1 detik.
3. Klik **Baca status 112/0**. Hanya ringkasan dibaca, termasuk jumlah alarm dan ID utama. Tidak ada permintaan detail otomatis, termasuk saat alarm aktif.
4. Jika ingin melihat seluruh daftar, pilih objek detail 65 (bitmask ID 1–2000) atau 67 (maksimal 100 ID), lalu klik **Baca detail alarm**. Klik tombol tersebut adalah persetujuan untuk satu permintaan detail; tidak ada dialog tambahan.
5. Hasil detail muncul dalam jendela terpisah, dilengkapi waktu, IP dan jumlah ID. Jendela itu adalah snapshot, tidak cyclic. Klik lagi untuk mengambil snapshot baru.

Saat status cyclic berjalan, tombol detail tetap bisa diklik; permintaannya dikerjakan setelah transaksi yang sedang berjalan, tanpa menghentikan polling. Pilihan objek detail dikunci selama polling; Stop dahulu bila ingin menggantinya. Tombol Stop menghentikan polling. Saat idle, detail juga bisa diminta langsung tanpa pembacaan ringkasan sebelumnya.

Tombol Mulai baca tetap untuk register IW/SET/ACT. Pengaturan alamat/jumlah tidak dipakai oleh fitur status/alarm. Ekspor CSV menyimpan tabel ringkasan terakhir; detail terpisah tercatat sebagai paket TX/RX dalam controller_packets.jsonl, bukan CSV ringkasan.

Tidak ada reset/acknowledge alarm atau perubahan proses pada kedua tombol baca ini. ID belum dipetakan ke nama/kategori alarm. Layout mengikuti analisis 13E dan masih perlu diverifikasi di mesin. Jumlah nol adalah laporan snapshot, bukan jaminan kondisi mesin aman. Kegagalan pembacaan ditampilkan sebagai error, bukan nol alarm.

Intervent dan pembacaan register tetap tersedia. Panduan v0.9.6 tentang detail otomatis sudah digantikan oleh panduan ini.
