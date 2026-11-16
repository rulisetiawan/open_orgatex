# v0.9.9 — Block sampai 240 alamat

Pilih SV_READ_BLOCK (11), objek yang diinginkan, Lebih dari 1, alamat awal dan jumlah sampai 240. Pilihan Sekali/Cyclic tetap berlaku.

Untuk WORD (IW/SET/ACT/LW/MW), 240 nilai = 480 byte: satu permintaan block, tanpa pembagian. Untuk DWORD objek 1035, 240 nilai = 960 byte: program mengirim dua block, 121 dan 119 counter, lalu menggabungkan hasil sesuai alamat. Dua block tidak menjamin snapshot pada saat yang persis sama. Jika satu block gagal, hasil gabungan tidak ditampilkan sebagai lengkap.

Batas ini berdasarkan kapasitas payload frame TCP yang dipakai program (486 byte), bukan klaim batas maksimum hardware. Log ARCNET MANUAL_20261111_131616_408694.log membuktikan permintaan 11/1025 mulai 1/jumlah 240 (01 00 F0 00), dengan respons 480 byte. Tidak ada objek 1035 di log tersebut.

Tutup aplikasi lama lalu jalankan JALANKAN_CONTROLLER_V099.bat. Panduan fitur lain ada di PETUNJUK_V098.md dan PETUNJUK_V097.md.
