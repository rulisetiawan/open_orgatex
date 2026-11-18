# Orgatex ke HMI — identitas batch dan mekanisme pengambilan

Tanggal pemeriksaan: 31 Oktober 2026. Analisis statis atas backup lokal dan hasil dekompilasi yang sudah tersedia. Tidak ada koneksi atau pengiriman perintah ke mesin. Tool REA tidak tersedia pada sesi ini; pemeriksaan dilakukan dengan pembacaan kode hasil dekompilasi dan byte file melalui alat lokal, bukan hasil eksekusi REA baru.

## 1. Temuan utama

File PRG membawa program proses. Data identitas batch berada di BATCHREF.REF dan menunjuk ke program yang digunakan. Karena itu aplikasi pengganti Orgatex membutuhkan pengelolaan batch dan antrian selain editor PRG.

Contoh langsung dari `Storage/sc777ce/BATCH/060892`:

| Elemen | Nilai yang terbaca | Dasar |
|---|---|---|
| Referensi internal | 060892 | byte 1–7 BATCHREF.REF; sama dengan nama folder |
| Batch produksi | PJT026 | text slot 1; konstanta CFG_BTCHT_BATCH_NO |
| Mesin | B012 | byte 748–752 |
| Pelanggan | PT.ARTA PERMAI | text slot 3 |
| Artikel | CM 30S RIB | text slot 4 |
| Kode warna | 1650159 | text slot 5 |
| Deskripsi warna | UNGU | text slot 6 |
| Nomor resep | 20261027PJT026 | text slot 7; konstanta CFG_BTCHT_RECIPE_NO |
| Nomor program | 401 | uint16 byte 26–27 dan daftar program byte 759–761 |
| File program | M_0401.PRG | file yang memang ada di folder yang sama |
| Text slot 20 | VINYL MD CALL | label mentah; tidak disamakan otomatis dengan judul internal PRG |
| Parameter batch slot 1 | sekitar 325,85 | float32; konstanta library menyebut WEIGHT, satuan perlu diperiksa pada konfigurasi mesin |

Nomor resep merupakan referensi. Field ini sendiri tidak memuat daftar bahan dan jumlah dosing. Parameter batch juga berbeda dari parameter setiap fungsi/step PRG.

## 2. Struktur BATCHREF yang dicocokkan

Struktur `T_BATCH_HEADER_ELEMENT` memakai Pack=1. Dari ukuran field yang dideklarasikan, panjang header adalah 759 byte. Setelah header terdapat daftar `T_PROG_LIST_ELEMENT`, masing masing 3 byte.

| Offset nol | Panjang byte | Field |
|---:|---:|---|
| 0 | 1 | pstat_key |
| 1 | 7 | batch_ref_no |
| 8 | 18 | tiga tanggal waktu, masing masing 6 byte |
| 26 | 2 | program_no |
| 28 | 420 | 20 slot teks, masing masing 21 byte |
| 448 | 80 | 20 parameter float32 |
| 528 | 80 | 20 consumption float32 |
| 608 | 80 | 20 times int32 |
| 688 | 40 | 20 events uint16 |
| 728 | 20 | 10 alarm group counter uint16 |
| 748 | 5 | machine_no |
| 753 | 2 | host_batch |
| 755 | 2 | host_config_no |
| 757 | 2 | position |
| 759 dan seterusnya | 3 per elemen | program_no uint16 dan program_type byte |

Pemeriksaan menemukan 1.591 file pada dua cabang `Storage/sc777ce/BATCH` dan `Network/F/OT/BATCH`; semuanya memenuhi panjang header dan kelipatan elemen tersebut. Sebanyak 1.590 nama folder cocok dengan nomor referensi dalam file. Satu pengecualian adalah file langsung di folder BATCH, tanpa subfolder nomor referensi. Kecocokan ini mendukung layout, tetapi tidak memvalidasi satuan seluruh parameter atau status runtime.

Pada contoh 060892, byte status adalah 0; enum library menamainya CREATED. Keberadaan file di HMI maupun nilai tersebut tidak membuktikan mesin sedang menjalankan batch. File utama `Storage/sc777ce/BATCH/BATCHREF.REF` justru berisi referensi 038964 dan byte status 3. Backup dapat memuat keadaan dari waktu berbeda.

## 3. Antrian per mesin dan konfirmasi pengambilan

`HostBatchList.GetFilePath` mengarah ke `MACHINES/<MachineNumber>/BATCHES/QUEUE.BTD`. Pemilihan batch melibatkan nomor mesin, lalu referensi batch atau urutan posisi. Kode juga memiliki jalur database dengan filter machine_no dan batch_status_key; angka status database tidak boleh langsung disamakan dengan enum status file HMI.

Pada implementasi `CECommunicationService`, perintah yang ditemukan:

| Command ID | Nama | Perilaku kode |
|---:|---|---|
| 150 | READ_BATCH | baca header berdasarkan referensi atau posisi pertama |
| 160 | READ_BATCH_QUEUE | baca daftar header antrian mesin |
| 120 | LOAD_HOST_BATCH | baca dan kunci record; balas referensi 7 byte |
| 121 | LOAD_HOST_BATCH_CONFIRMED | hapus record yang dikunci dari antrian, lalu balas |
| 122 | LOAD_HOST_BATCH_CANCELED | balas pembatalan tanpa penghapusan record pada cabang ini |

Urutan pada handler server:

1. Terima MachineNo, Operation dan ReferenceNo.
2. Baca record antrian menggunakan operasi Btrieve yang mengunci record.
3. Kirim referensi internal yang terpilih.
4. Tunggu pesan lanjutan pada socket yang sama.
5. Jika menerima CONFIRMED, panggil DeleteLockedBatch, yang menjalankan DeleteRecord pada record antrian. Jika CANCELED, jangan hapus record melalui cabang ini.
6. Tutup handle file pada finally, termasuk ketika terjadi kegagalan.

Menghapus record antrian bukan bukti bahwa folder batch, histori, atau program ikut dihapus. Konfirmasi pengambilan juga bukan konfirmasi mesin mulai running. Handler ini tidak menunjukkan seluruh urutan transfer isi PRG di antara pesan tersebut; bagian klien dan capture masih diperlukan untuk memastikan urutan lengkap.

Port fallback pada constructor layanan adalah 50150 jika konfigurasi CEComServicePort bernilai 0. Ini merupakan default kode, bukan port aktif yang sudah terbukti pada instalasi PT.SMM. Command ID di atas adalah command layanan variable-message, bukan alamat register PLC atau ID fungsi PRG.

## 4. Hubungan dengan LAWER dan PLC

Header mendefinisikan slot teks recipe number, dosing machine number dan dosing batch number. Library juga mendefinisikan sejumlah konstanta parameter dosing. Makna slot harus dikonfirmasi per konfigurasi: beberapa konstanta memakai indeks yang sama untuk konteks mesin yang berbeda.

Pada contoh 060892, text slot 8 dan 9 kosong. Konfigurasi backup `Network/F/OT/CFG/ORGATEX.INI` memiliki LAWER=0 dan USE_GATEWAY_COMMUNICATION=0. Hal ini belum membuktikan tidak ada dosing pada seluruh instalasi, tetapi tidak mendukung klaim bahwa interface LAWER aktif melalui konfigurasi tersebut.

Alur konseptual yang didukung artefak:

Planning/order → batch untuk mesin tertentu → referensi internal dan antrian → pengambilan metadata/program oleh HMI → pemilihan dan eksekusi program → komunikasi HMI ke PLC.

Jalur host–HMI dan HMI–PLC harus ditangani terpisah. Struktur BATCHREF tidak membuktikan framing ARCNET, alamat nilai actual, handshake dosing atau interlock PLC.

## 5. Implikasi untuk pengembangan aplikasi

Editor PRG yang sudah dibuat dapat menjadi modul program proses. Modul lanjutan yang dibutuhkan adalah:

- Master mesin dan konfigurasi jenis program/parameter yang kompatibel.
- Form batch: batch produksi, referensi internal, mesin, artikel, warna, berat, nomor resep dan program.
- Antrian per mesin beserta urutan dan status transfer.
- Pengaitan resep chemical dan dosing dengan identitas batch yang sama.
- Adapter komunikasi dengan konfirmasi penerimaan, pencatatan kegagalan dan rekonsiliasi status sebelum pengiriman ulang.
- Pemisahan status antrian host, batch tersimpan pada HMI dan status actual proses PLC.

Yang sudah tersedia untuk pekerjaan offline: decoder batch, contoh metadata nyata, file PRG pasangan dan kode server untuk antrian/konfirmasi. Yang belum terbukti: layanan dan port yang aktif pada HMI ini, urutan transfer file klien secara lengkap, serta konfirmasi eksekusi/dosing di mesin. Validasi berikutnya harus mencocokkan satu aksi load batch pada HMI dengan log atau capture host–HMI dan perubahan file/status, tanpa menganggap contoh kode sebagai bukti runtime.

## 6. Sumber lokal yang diperiksa

- `D:/ORGATEX/OrgaTEX/analysis/decompiled/SecomCEDefines/OtxCSLib.Secom/T_BATCH_HEADER_ELEMENT.cs`: field, konstanta dan enum status.
- `D:/ORGATEX/OrgaTEX/analysis/decompiled/SecomCEDefines/OtxCSLib.Secom/T_DATE_TIME.cs`: enam byte per tanggal waktu.
- `D:/ORGATEX/OrgaTEX/analysis/decompiled/SecomCEDefines/OtxCSLib.Secom/T_PROG_LIST_ELEMENT.cs`: elemen daftar program.
- `D:/ORGATEX/OrgaTEX/analysis/decompiled/CommunicationServiceTasks/SetexCommunication.VirtualController/HostBatchList.cs`: antrian dan operasi record. Namespace memuat VirtualController; klaim penerapan pada layanan CE didasarkan pada pemanggilan kelas ini oleh CECommunicationService, bukan pada simulator saja.
- `D:/ORGATEX/OrgaTEX/analysis/decompiled/CommunicationServiceTasks/CommunicationServiceTasks.BackgroundTasks.CECommunicationService/CECommunicationService.cs`: ReadBatch sekitar baris 608, ReadBatchQueue sekitar 633, LoadHostBatch sekitar 651.
- Folder yang sama: `LOAD_HOST_BATCH_REQ.cs`, `LOAD_HOST_BATCH_RES.cs`, `T_SECOM_VARIABLE_MESSAGE_COMMAND.cs`.
- `D:/File HMI/Storage/sc777ce/BATCH/060892/BATCHREF.REF` dan `M_0401.PRG`.
- `D:/File HMI/Network/F/OT/CFG/ORGATEX.INI`: konfigurasi snapshot.

Hasil decode seluruh file dan SHA256 per file: `BATCHREF_decoded.json`. Decoder: `decode_batchref.py`. Script hanya membaca sumber dan menulis hasil analisis.
