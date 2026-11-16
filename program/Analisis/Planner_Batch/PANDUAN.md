# Planning Batch SETEX

Jalankan `D:\File HMI\Analisis\Buka_Planner_Batch.cmd`, lalu buka http://127.0.0.1:8768/.
Tampilan berada di `D:\File HMI\Analisis\Planner_Batch.html`. Membuka HTML melalui file:// menampilkan petunjuk launcher: ekspor database membutuhkan helper lokal.

1. Baca salinan BREFNEXT.DAT atau isi kandidat referensi enam digit. Nilai awal 062340 berasal dari file pengguna; bukan reservasi server.
2. Pilih program dari daftar, atau impor PRG hasil editor. Template bawaan adalah BATCHREF 062277/A001 dan M_0502; daftar lama berasal dari backup B012. Impor BATCHREF dari mesin yang sesuai bila tersedia (satu program M, 762 byte).
3. Masukkan mesin tujuan, misalnya E013, nomor batch baru, metadata, dan 20 parameter batch. Pilihan mesin menerima 1–4 huruf kapital/angka. Satuan tidak ditebak.
4. Jika perlu, buka **Edit nilai langkah PRG**, pilih step, ubah nilai P1–P6, lalu klik **Terapkan nilai langkah**. Struktur, ID fungsi dan nomor program tetap mengikuti sumber. Untuk menambah/menghapus fungsi gunakan editor PRG lama lalu impor hasil yang sesuai.
5. Klik **Tambah ke planning**. Batch berikutnya mendapat kandidat referensi berikutnya. Edit, hapus, atau naikkan urutan dari daftar. Urutan per mesin mengikuti urutan daftar tersebut.
6. Klik **Unduh ZIP · Queue + Batch + PRG**. Draf planning dapat disimpan dan dibuka kembali lewat JSON.

Contoh hasil ZIP:

```text
OT/BATCH/062340/BATCHREF.REF
OT/BATCH/062340/M_0502.PRG
OT/MACHINES/E013/BATCHES/QUEUE.BTD
planning-manifest.json
BACA_DULU.txt
```

## Yang telah diverifikasi

- Queue ditulis melalui `BtrieveInterface.dll` x86 yang berasal dari instalasi lokal OrgaTEX, menggunakan signature BTRCALL dari OtxDataBaseLayer.
- Helper menyalin template QUEUE ke direktori kerja sementara, menghapus record dalam salinan melalui API, lalu memasukkan record planning melalui API. Tidak ada penulisan index secara manual.
- Setiap queue hasil ekspor ditutup, dibuka ulang, dan semua record dibaca melalui kelima key. Jumlah, keunikan referensi, isi payload 759 byte, dan urutan posisi diverifikasi. Kegagalan menghentikan ekspor ZIP.
- Pengujian mencakup 50 record dalam satu queue, satu record, dua mesin dengan posisi terpisah, validasi input, round-trip draf, serta UI desktop/mobile.
- Isi ZIP browser diperiksa terpisah: metadata E013, nilai batch 999.5 dan nilai langkah 1.25 sesuai input. Byte PRG lainnya tetap sama. File pengguna tidak diubah.
- Hasil uji ada pada `verification.json`, `browser-test-result.json`, serta `test_export.py` dan `test_browser.cjs`.

## Batas penggunaan

- Ekspor ZIP adalah pembuat paket offline. Fitur FTP opsional mengirim file ketika tombol Kirim ditekan, bukan perintah load/start PLC. Keberhasilan baca melalui library lokal belum membuktikan penerimaan oleh HMI E013 atau mesin lain.
- Queue hasil ekspor **baru dan hanya berisi planning ini**. Bukan merge dengan antrean aktif; jangan menggantikan queue produksi yang masih berisi pekerjaan.
- Tidak membaca atau memperbarui BREFNEXT.DAT aktif. Alokasi referensi terpusat dan sinkronisasi OrgaTEX belum diimplementasikan.
- Tidak menghitung ulang resep/LAWER/dosis ketika berat berubah, dan tidak memvalidasi parameter terhadap CNF mesin tujuan. PRG dari mesin berbeda tidak otomatis kompatibel.
- Status CREATED, tanggal terpilih/mulai/selesai dan hasil konsumsi/event/alarm diinisialisasi. Slot times[20] dipertahankan karena semantiknya belum seluruhnya terpetakan. Teks dan parameter yang tidak diedit dipertahankan dari template.
- Host config BATCHREF/queue awal 2/0 mengikuti perbedaan pada pasangan sumber A001, bukan nilai universal. Keduanya dapat diatur di bagian konfigurasi. Posisi BATCHREF = 0; posisi queue = urutan per mesin.
- Template multi-program atau tipe program selain M belum didukung dan ditolak, bukan dipotong diam-diam.

## Komponen lokal

`server.py` hanya mendengarkan 127.0.0.1:8768. Ekspor dan FTP memerlukan token sesi dan host/origin lokal. Endpoint FTP memakai host dan path remote yang diisi pengguna; tidak ada endpoint untuk membuka sembarang path filesystem lokal dari browser. File sementara dibuat di subfolder jobs dan dibersihkan setelah ekspor. Log transfer dan backup queue lama disimpan di ftp_logs.

Launcher memakai Python lokal yang sudah tersedia; lokasi dapat disesuaikan di `launch.ps1`. Helper QueueTool.exe membutuhkan runtime Visual C++ 2013 x86 yang sudah tersedia pada komputer ini. Tidak ada instalasi tambahan atau perubahan konfigurasi OrgaTEX.

Untuk kompilasi ulang QueueTool.cs, gunakan compiler .NET Framework dengan `/platform:x86`, dan tempatkan BtrieveInterface.dll lokal di sebelah executable. Library tetap berasal dari instalasi pengguna, bukan implementasi ulang format Btrieve.

## FTP manual (tambahan 6 November 2026)

1. Susun planning untuk **satu mesin** per transaksi pengiriman. ZIP masih mendukung beberapa mesin.
2. Pada bagian **Kirim ke FTP**, isi host (tanpa ftp://), port, username/password, dan protokol FTP atau FTPS explicit TLS. SFTP belum didukung. Password tidak dimasukkan ke draf atau log.
3. Isi folder induk batch, misalnya `/OT/BATCH`, dan path queue, misalnya `/OT/MACHINES/{machine}/BATCHES/QUEUE.BTD`. Semua path bisa diganti sesuai FTP; `{machine}` otomatis menjadi mesin planning. Folder induk dan queue mesin yang valid harus sudah ada. Tidak menganggap error akses sebagai queue kosong.
4. **Periksa koneksi & queue** hanya membaca FTP. Helper mencoba penggabungan di salinan lokal dan memeriksa kelima indeks. Pemeriksaan tidak memesan referensi atau menjamin keadaan server belum berubah kemudian.
5. Sebelum **Kirim batch + gabungkan queue**, hentikan sementara semua akses tulis OrgaTEX/HMI ke queue dan pastikan referensi telah direservasi lewat mekanisme bersama di luar planner. Centang pernyataan hanya setelah kondisi tersebut dilakukan. Planner tidak bisa mengonfirmasi penghentian writer dari FTP.
6. Pengiriman mengambil queue terbaru, mempertahankan seluruh payload lama, menambahkan posisi setelah posisi terbesar, lalu memverifikasi queue lokal. Folder batch dan queue diunggah sementara, dibaca ulang dan dibandingkan hash sebelum publikasi.
7. Queue lama diberi nama `QUEUE.BTD.backup_<ID>` sebelum queue gabungan dipasang. Backup asli juga ada di `Planner_Batch/ftp_logs`. Queue diperiksa lagi untuk mendeteksi perubahan di tengah proses. Lock `.planner-transfer.lock` hanya mengoordinasikan sesama planner, **bukan lock yang dipatuhi OrgaTEX/HMI**.
8. Hasil sukses berarti file di FTP sudah cocok dengan hasil lokal. Tetap periksa pemuatan HMI sebelum menyatakan batch siap/berjalan. Fitur ini tidak mengubah counter atau mengirim perintah start.

Jika gagal, baca ID dan log transaksi. Paket staging atau folder batch yang telah dipublikasikan bisa tertinggal dan sengaja tidak dihapus otomatis. Jika queue lama sudah dipindahkan dan nama queue akhir masih kosong, helper mencoba mengembalikan nama lama. Ia tidak menimpa file yang muncul dari proses lain. Putus koneksi setelah rename dapat membuat hasil commit tidak pasti (`committed: null` pada log); jangan melakukan retry otomatis. Periksa queue/backup dan bersihkan staging hanya setelah status diketahui.

**Batas teknis:** FTP tidak menyediakan transaksi atomik lintas folder/queue maupun penguncian database bersama. Pemeriksaan hash mengurangi risiko tetapi tidak menutup celah concurrent write; karena itu penghentian writer dan reservasi nomor tetap wajib. Dukungan rename, izin folder, encoding, serta FTPS perlu diuji terhadap server sebenarnya.

Validasi fitur: 14 tes backend mencakup merge yang menjaga payload lama, konflik referensi, perubahan queue, gagal unggah, pemulihan rename, dan transport FTP nyata ke server simulasi **localhost**. Uji browser form memakai respons tiruan. Belum ada koneksi atau pengujian terhadap FTP produksi.
