# Jalur Intervent ProcessInfo — temuan lanjutan

Analisis statis binary 13E; tidak menjalankan kontroler atau mengirim perintah.

## Perbedaan dari aplikasi v0.9.1

Aplikasi sekarang memakai `Api_ChangeFunction` ekuivalen service 106/object 6.
Pada modul tampilan proses ditemukan jalur perubahan parameter tersendiri.

`SecomCE_ProcessInfo_2d.dll`:
- Import Api_ChangeParameterExtended pada IAT 0x1B31C4.
- Wrapper RVA 0x8F607 meneruskan argumen ke API itu.
- Pemanggil pada RVA 0x421F9 mengambil ID parameter uint16 dari record
  tampilan +0x3B, nilai numerik dari hasil input, dan flag dari record +0x43
  (bit 0). Field target tambahan diteruskan sebagai konstanta 0 pada jalur ini.
- Ada jalur enum pada RVA 0x421B8 yang mengirim pilihan integer sebagai float.
- Wrapper juga melakukan konversi nilai tampilan ke raw untuk pembaruan buffer
  lokal sesudah pemanggilan API. Tidak sekadar mengirim semua P1..P6 fungsi.

`SecomCE_D_BackGround_2d.dll`, Api_ChangeParameterExtended RVA 0x295B2:
- Service **137** (0x89), object **41** (0x29).
- Panjang payload 124 byte.
- Payload +0: flag dari argumen; semantik tepat belum tervalidasi.
- Payload +1: jumlah entri 1.
- Payload +2: ID parameter uint16.
- Payload +4: nilai baru float32.
- Payload +122: target tambahan uint16 (0 pada pemanggil ProcessInfo di atas).

## Yang sudah terverifikasi pada balasan mesin

SV_READ/object 6 mengembalikan enam entri. Entri pertama dimulai di offset
frame 23: uint16 raw, float32 nilai tampilan, uint16 ID parameter; stride 8.
Contoh log fungsi 141: ID 3/4/5; fungsi 713: ID 7/9.
ID ini tersedia dari mesin, sehingga tidak perlu menebak nomor parameter
berdasarkan nomor slot P atau nomor langkah program.

## Batas kesimpulan

Ini bukti kuat jalur alternatif pada modul proses, bukan pembuktian bahwa
setiap dialog/tombol Intervent memakai service 137 pada seluruh firmware.
Masih perlu menelusuri semantik flag bit 0 dan pembentukan record tampilan,
serta mencocokkan respons/efek runtime. Memilih flag 0 atau 1 tanpa dasar
belum dinyatakan sebagai implementasi siap uji.

Kode akses tidak ditambahkan ke payload ini oleh builder yang diperiksa.
Hal ini tidak membuktikan otorisasi Controller tidak diperlukan; hanya bahwa
builder tersebut tidak memuat PIN. Tidak ada perubahan login/mode manual.

Aplikasi belum dialihkan ke jalur ini. Error Invalid status pada jalur lama
tidak dianggap selesai hanya karena template baru telah ditemukan.
