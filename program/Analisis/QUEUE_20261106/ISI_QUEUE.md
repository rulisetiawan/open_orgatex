# Isi QUEUE.BTD yang diterima 6 November 2026

File sumber: C:\Users\Lenovo Yoga 7i\Downloads\QUEUE.BTD
SHA256: e98848eea5f535bd290a1d354b3a76855b1135c31e8b1a81753dfd9c1b1e7ebf

Ditemukan dua payload batch untuk A001. Field posisi dan halaman index mendukung urutan di bawah. Ini pembacaan statis snapshot, bukan status mesin saat ini.

| Posisi | Referensi | Batch | Mesin | Program | Nama program | Warna | Resep |
|---:|---|---|---|---:|---|---|---|
| 1 | 062232 | PJZ828 | A001 | 622 | TOP VINYL TUA CALL | PRB TM COKLAT | 20261105PJZ828 |
| 2 | 062277 | PKD338 | A001 | 502 | VINYL SDG CALL | ABU | 20261105PKD338 |

## Struktur dan bukti

- Ukuran file 12.288 byte; pola halaman 1.024 byte, total 12 halaman.
- Payload 759 byte sesuai T_BATCH_HEADER_ELEMENT. Nilai 759 juga muncul pada header offset 0x16.
- Record 062277 berada di 0x2006 dan berposisi 2; record 062232 berada di 0x2406 dan berposisi 1.
- Referensi ditemukan kembali di halaman index 0x400, status+referensi di 0x800, teks batch di 0xC00, serta posisi di 0x1400.
- Lima descriptor yang teramati memuat offset/panjang payload: key 0 = 1/7, key 1 = 0/8, key 2 = 28/21, key 3 = 8/6, key 4 = 757/2.
- Key 3 menunjuk enam byte pertama field tanggal (dt_terminated) menurut layout library. Semua nilainya nol dalam kedua record, sehingga belum diuji dengan tanggal berbeda.
- Struktur index dan pointer database berada di luar payload. File ini bukan gabungan mentah record 759 byte.
- Kedua status mentah 0 (CREATED pada enum library), host_batch 1, host_config_no 0. Ini tidak membuktikan load release atau mesin running.
- Ketiga field tanggal pada kedua batch masih nol. Field times slot 2 berisi 29835 untuk PJZ828 dan 26651 untuk PKD338; makna/satuan belum ditetapkan.
- Seluruh slot konsumsi, event dan penghitung alarm dalam dua payload bernilai nol.

## Semua parameter batch mentah

| Slot | PJZ828 | PKD338 |
|---:|---:|---:|
| 1 | 919.90002 | 1248.76 |
| 2 | 200 | 200 |
| 3 | 6 | 6 |
| 4 | 6000 | 7500 |
| 5 | 0 | 0 |
| 6 | 0 | 0 |
| 7 | 220 | 220 |
| 8 | 0 | 0 |
| 9 | 0 | 0 |
| 10 | 0 | 0 |
| 11 | 2 | 2 |
| 12 | 40 | 40 |
| 13 | 90 | 90 |
| 14 | 0 | 0 |
| 15 | 600 | 699.28143 |
| 16 | 582.1687 | 1259.8795 |
| 17 | 400 | 400 |
| 18 | 0 | 0 |
| 19 | 0 | 0 |
| 20 | 6 | 6 |

Angka tersebut adalah parameter batch, bukan P1-P6 per fungsi PRG. Slot 1 dinamai WEIGHT pada konstanta library, tetapi satuan dan pemakaian aktual harus diverifikasi pada konfigurasi A001.

## Hubungan paket batch

Dengan pola folder yang sudah ditemukan, pasangan yang perlu dicocokkan berikutnya adalah OT/BATCH/062232/BATCHREF.REF + M_0622.PRG serta OT/BATCH/062277/BATCHREF.REF + M_0502.PRG. Nama/path tersebut diturunkan dari referensi dan nomor program; keberadaan paketnya belum diperiksa dari server aktif.

## Batas untuk pembuatan batch baru

Analisis ini cukup untuk membaca dua payload dan mengetahui urutannya, tetapi belum menjadi implementasi penulisan Btrieve. Penambahan record harus menjaga page/index, definisi key, pointer, locking dan sinkronisasi dengan paket batch. Jangan mengubah nomor referensi dengan hex editor lalu menganggap seluruh index telah ikut berubah.

Sumber layout: D:/ORGATEX/OrgaTEX/analysis/decompiled/SecomCEDefines/OtxCSLib.Secom/T_BATCH_HEADER_ELEMENT.cs. Sumber pemilihan index 0 dan 4: D:/ORGATEX/OrgaTEX/analysis/decompiled/CommunicationServiceTasks/SetexCommunication.VirtualController/HostBatchList.cs.

File sumber tidak diubah. Decoder ini sengaja membatasi dirinya pada pola sampel yang diperiksa.