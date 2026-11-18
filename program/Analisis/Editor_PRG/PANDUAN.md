# PRG Studio

Buka `D:\File HMI\Analisis\Editor_PRG.html` di Edge atau Chrome. File ini mandiri: daftar program, definisi CNF, editor dan generator PRG disertakan dalam satu HTML, tanpa koneksi internet atau instalasi.

## Penggunaan

1. Pilih salah satu dari 37 program di panel kiri. Bisa juga memuat PRG lain dengan tombol **Buka file PRG**.
2. Ubah **ID program** dan **Nama program**. Nama maksimal 20 karakter ASCII. Nama hasil mengikuti ID, misalnya ID 183 menjadi `M_0183.PRG`.
3. Pilih langkah. Tentukan fungsi dan nilai parameter. Nama, satuan dan pilihan teks berasal dari CNF lokal.
4. Gunakan **Tambah**, **Duplikasi**, **Naik/Turun**, dan **Hapus** untuk menyusun langkah. Program Start dan Program End dipertahankan sebagai batas awal/akhir.
5. Tambahkan fungsi tangki/pompa/resource lain melalui **Tambah fungsi**. Pilihan fungsi mengikuti resource yang ditemukan pada CNF dan program sumber.
6. Klik **Ekspor PRG**. Browser mengunduh berkas biner PRG secara langsung.

**Program baru** membuat dua langkah Start/End menggunakan header dari template yang sedang dipilih. Tambahkan langkah di antaranya. Memilih fungsi lain membuat nilai default dari definisi CNF fungsi tersebut.

**Simpan draf** mengunduh JSON yang bisa dipulihkan melalui **Buka draf JSON**. Editor juga menyimpan draf terakhir di localStorage apabila diizinkan browser. Unduh draf JSON untuk penyimpanan yang dapat dipindahkan. **Urungkan** membatalkan hingga 30 perubahan dalam sesi program yang sedang dibuka.

## Batas validasi

- Struktur didasarkan pada PRG dan TYPECONF.CNF dari salinan sc777ce yang dianalisis; konfigurasi perangkat lain dapat berbeda.
- Nilai asli pada field yang belum didefinisikan tetap dipertahankan. Contohnya P6 fungsi 718.
- Perubahan parameter angka diperiksa terhadap batas statis CNF. Batas dinamis ditandai; nilainya belum diambil dari perangkat.
- Field parameter yang memakai referensi/formula tidak diedit melalui kolom angka biasa.
- Mengganti fungsi membuat record baru dengan default CNF. Duplikasi langkah mempertahankan record lengkap. Field tambahan asli dipertahankan ketika hanya mengubah nilai pada fungsi yang sama.
- Header program menggunakan template; metadata lain yang tidak diedit dipertahankan.
- Periksa hasil di editor resmi Orgatex/SECOM yang sesuai sebelum digunakan pada mesin. Belum dilakukan transfer atau pengujian runtime pada PLC/HMI.

## Verifikasi yang telah dilakukan

- Seluruh 37 program sumber dimuat dan diekspor ulang dengan hasil identik byte-per-byte.
- Perubahan satu nilai temperatur menghasilkan perubahan hanya pada empat byte nilai tersebut.
- Penambahan/penghapusan langkah, komentar, ID dan nama berhasil dibaca ulang.
- Nilai tambahan P6=1 tetap ada setelah ekspor ulang.
- Uji browser Edge: unduh PRG, buka kembali hasil, tambah/hapus resource, urutkan/duplikasi/hapus langkah, simpan/pulihkan draf, pembatasan nilai statis, dan tampilan seluler.
- File PRG yang diunduh dari browser diperiksa lagi dengan Python; library sumber dan CNF dibandingkan terhadap SHA-256 inventaris asli.

## Sumber editor

`Editor_PRG/build_editor.py` menyatukan `template.html`, `engine.js`, `app.js`, dan data hasil analisis menjadi `Editor_PRG.html`. Menjalankan builder tidak mengubah PRG/CNF sumber.
