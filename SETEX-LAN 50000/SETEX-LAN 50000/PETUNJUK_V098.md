# v0.9.8 — Counter konsumsi batch, objek 1035

Tutup versi lama lalu jalankan JALANKAN_CONTROLLER_V098.bat.

1. Isi IP/port dan pilih LIVE Controller.
2. Pilih objek **Konsumsi batch - DWORD (1035)**.
3. Untuk satu counter, pilih SV_READ (1), Satuan, dan alamat counter yang diketahui.
4. Untuk rentang, pilih SV_READ_BLOCK (11), Lebih dari 1, isi alamat awal dan jumlah counter (maksimal 80). Alamat awal 1/jumlah 10 berarti counter 1–10, bukan 10 byte. Gunakan rentang yang diketahui valid pada mesin.
5. Untuk alamat terpencar pilih SV_READ, lalu daftar seperti 1,3,5. Pembacaan dilakukan berurutan dengan jeda antar alamat sebagaimana versi sebelumnya.
6. Pilih Sekali atau Cyclic dan interval. Klik **Mulai baca**. Stop menghentikan cyclic. Ekspor CSV menyimpan hasil sebagaimana pembacaan register lainnya.

Setiap counter dibaca sebagai unsigned DWORD 32-bit Little-Endian (0–4294967295), bukan WORD 16-bit, signed integer, atau float. Nilai ditampilkan desimal mentah dan hex 8 digit. Tidak tersedia write atau reset counter ini.

Belum diketahui: rentang alamat valid, nama utilitas setiap alamat, faktor skala, dan satuan fisik. Jangan menganggap alamat pertama pasti air atau listrik. Nilai mentah belum otomatis dikonversi ke liter/kWh.

Fitur ini membaca pada saat Anda meminta atau secara cyclic, belum otomatis mendeteksi Program End atau menyimpan laporan akhir batch. Untuk menangkap nilai akhir, pembacaan harus terjadi sebelum reset counter; cyclic pun dapat melewatkan nilai akhir jika jendela waktunya pendek. Klaim waktu reset spesifik mesin masih perlu dicocokkan dengan rekaman nyata.

Bukti lokal: 13E/SC777CE/System/Commands.csv baris 97 mencantumkan service 1/objek 1035 sebagai pembacaan doubleword; baris 166 mencantumkan service 11/objek 1035 sebagai block doubleword. Decoder memakai format 4-byte Little-Endian sesuai informasi yang diberikan pengguna. Penerimaan dan layout balasan TCP mesin belum diuji untuk objek ini; panjang payload harus tepat jumlah counter × 4, jika berbeda nilai tidak ditampilkan.

Fitur status 112/0 dan detail alarm tetap dipisahkan sesuai PETUNJUK_V097.md. Intervent tetap mengikuti PETUNJUK_V095.md.
