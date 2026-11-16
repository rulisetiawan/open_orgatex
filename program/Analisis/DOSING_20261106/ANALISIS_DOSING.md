# Analisis dosing dari tiga file A2

Analisis statis 6 November 2026. Tidak ada file dikirim ke mesin, koneksi LAWER, atau perubahan status dosing.

## Kesimpulan file

Ketiga file adalah record teks fixed-width dengan 21 field dipisahkan karakter `|`, berukuran 185 byte. Nama prefix A2 cocok dengan `TRANS_ACK_FNAME_PREFIX` pada definisi T_PREPARATION_REQ_BUFFER: balasan transfer. Akhiran .05/.13/.08 cocok dengan nomor call-off pada isi file, bukan nomor ekstensi format atau nomor step PRG.

| File | Referensi | Mesin | Call-off | Koreksi | Tank | Volume transfer mentah | Return code |
|---|---|---|---|---|---|---|---|
| A2058028.05 | 058028 | B009 | 05 | 00 | 01 | 00000 | 0200 |
| A2057986.13 | 057986 | B004 | 13 | 00 | 02 | 00000 | 0200 |
| A2058021.08 | 058021 | B002 | 08 | 00 | 01 | 00000 | 0200 |

`0200` diparse menjadi integer 200, yaitu ERR_PREQ_OK. Handler CheckResponseFile pada library yang tersedia mengubah status request menjadi FINISHED untuk kode 200, selain itu FINISHED_ERROR. Nilai ini adalah laporan keberhasilan protokol, bukan bukti sensor/flowmeter bahwa bahan benar-benar terkirim.

Volume transfer tercatat nol. Ini tidak membuktikan nol bahan didosing; belum diketahui apakah instalasi mengisi nilai aktual atau hanya mengirim status. Nama bahan, takaran target, dan jumlah aktual tiap bahan tidak tersedia dalam ketiga file.

Record ini tidak terenkripsi. Banyak field berupa spasi: nomor batch produksi, recipe_no, weight, liquor, ratio, deadline, station, dan request_type. Identitas internal, machine, call-off, tank dan return code cukup untuk mengenali balasannya, tetapi belum cukup untuk membangun resep.

Terminator sampel adalah LF + NUL (0A 00), bukan CR LF. Layout library menyediakan dua byte terminator; penulis request dalam Dosing.cs menggunakan CR LF. Perbedaan ini dicatat dan tidak dinormalisasi pada hasil decode.

## Alur yang didukung kode lokal

1. Program mesin mencapai kondisi permintaan dosing. Pada jalur virtual controller yang diperiksa, perubahan status request menjadi RELEASED memicu pembacaan tag batch, call-off, correction, tank, station, tipe permintaan, volume, dll. Ini membuktikan desain handler tersebut, bukan alamat/tag aktual B009/B004/B002.
2. Data tersebut dibuat menjadi request. GetFileName memetakan tipe 1 ke R1/A1, dan tipe 0 atau 2 ke R2/A2. Konstanta mendefinisikan R1 sebagai preparation request dan R2 sebagai transfer request. R1 tidak wajib mendahului setiap R2; contoh integrasi juga mendukung proses satu tahap.
3. Layanan/interface dosing mencocokkan batch dan call-off dengan resep. Skrip contoh vendor dosedemo.sql membaca Dyelot_Adds untuk transfer requested (TransferState=10, TransferAcked=0), lalu mengambil ProductCode, AmountPerMachine, Unit dan Counter dari Dyelot_Recipe berdasarkan Dyelot, ReDye, CorrectionNumber dan CallOff.
4. Sistem dosing menyiapkan dan mentransfer bahan. Dalam contoh integrasi, hasil per bahan masuk ActualAmount dan State=10, sedangkan status seluruh call-off menjadi TransferState=40 (Finished). dosedemo.sql adalah simulasi lama, tidak membuktikan bahwa database/adapter LAWER aktif saat ini memakai jalur itu.
5. Balasan A2 cocok dengan referensi dan nomor call-off. Contoh pasangan yang diharapkan: R2058028.05 -> A2058028.05. File request pasangannya belum tersedia pada tiga file yang diberikan.
6. CheckResponseFile membaca return code dan volume, meneruskan nilai ke tag controller, mengubah status selesai/error, menyimpan status, lalu menghapus file response yang dikonsumsi. Tindak lanjut langkah mesin tetap bergantung pada program PLC/interlock; tidak otomatis dibuktikan oleh ACK.

Enum PLCDosingStatus pada jalur tersebut: LOCKED=0, RELEASED=1, STARTED=2, FINISHED=5, FINISHED_ERROR=6. Angka ini bukan TransferState database (10/20/40); keduanya domain status berbeda.

## Hubungan dengan LAWER dan planner

Nama LAWER tidak ada di isi ketiga file. A2 menunjukkan antarmuka balasan dosing SETEX, bukan identitas software yang menulisnya. Backup ORGATEX.INI yang tersedia mencantumkan LAWER=0 dan USE_GATEWAY_COMMUNICATION=0; itu hanya konfigurasi snapshot, bukan bukti kondisi seluruh instalasi saat ini.

Planner saat ini membuat BATCHREF, PRG dan queue. Itu belum membuat baris resep dan call-off pada database/interface dosing. Batch baru yang menjalankan fungsi dosing masih membutuhkan pengaitan resep bahan, takaran, mesin, tank dan call-off pada sistem dosing. Mengganti nomor referensi paket saja belum membuktikan bahwa LAWER mengenali batch baru.

A2 adalah jawaban status: jangan menjadikannya file pemicu atau mengisi 0200 untuk menggantikan proses dosing. Handler dapat memperlakukannya sebagai request selesai.

Untuk menuntaskan pemetaan instalasi diperlukan request R2 pasangan, data resep/call-off terkait referensi 058028/057986/058021, dan konfigurasi/log interface dosing aktif. PRG pasangan dibutuhkan untuk mengaitkan call-off dengan step/fungsi sebenarnya. Sampai data tersebut tersedia, nomor bahan, kilogram/liter dan algoritme dosis tiap call-off belum bisa ditentukan.

## Sumber yang diperiksa

- Tiga file asli di C:/Users/Lenovo Yoga 7i/Downloads. Semua field, offset, panjang dan SHA256 tersimpan di dosing_decoded.json.
- D:/ORGATEX/OrgaTEX/analysis/decompiled/SecomCEDefines/OtxCSLib.Secom/T_PREPARATION_REQ_BUFFER.cs
- D:/ORGATEX/OrgaTEX/analysis/decompiled/SecomCEDefines/OtxCSLib.Secom/PLCDosingStatus.cs
- D:/ORGATEX/OrgaTEX/analysis/decompiled/CommonControllerDefines/OtxCSLib.CommonDefinitions/secom_errors.cs
- D:/ORGATEX/OrgaTEX/analysis/decompiled/CommunicationServiceTasks/SetexCommunication.VirtualController.Modules/Dosing.cs
- D:/File HMI/Network/F/OT/BIN/dosedemo.sql (contoh, tidak dijalankan)
- D:/File HMI/Network/F/OT/CFG/ORGATEX.INI
- D:/File HMI/Storage/SC777CE/PATH.CFG: DRHSTDOS = \\OT\\DOSING
