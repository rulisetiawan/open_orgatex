# Pemeriksaan diagnostik SETEX — 10 November 2026

Pemeriksaan statis PE/import/resource/disassembly. Tidak menjalankan EXE,
tidak memuat DLL, tidak membuka koneksi ke mesin, dan tidak mengubah backup.

## MsgDiagnosticCE_2d.exe

Lokasi: `13E/SC777CE/MsgDiagnosticCE_2d.exe` (juga ada di 6A dan 12B).
Ukuran 258048 byte. PE machine 0x14C (x86), subsystem 9 (Windows CE GUI),
subsystem version 5.0. Ini bukan aplikasi desktop Windows biasa.

Dependensi: SecomCE_MessageService_2d.dll, SecomCE_BGUtils_2d.dll,
mfcce400d.dll, COREDLL.dll.

Resource dialog 102 memiliki Settings, Refresh, Check structures, Pause,
Clear log. Resource dialog 130 memiliki Task ID, Operation, Refresh time (ms),
Rows count, dan keterangan 0 - stop refresh.

Imports menunjukkan fungsi membaca catatan log, memilih metode logging,
menetapkan file log, ekspor catatan, informasi queue/buffer. Ada juga fungsi
Msg_Send/Msg_Receive dan inisialisasi queue. Karena itu belum dibuktikan
bahwa menjalankan alat ini sepenuhnya pasif atau tidak memengaruhi HMI.

## Kendala utama: fungsi Msg_Log pada DLL pendamping adalah stub

Pada `13E/SC777CE/SecomCE_MessageService_2d.dll`:

| Export | RVA | Hasil pemeriksaan |
| --- | --- | --- |
| Msg_Log_GetTopCount | 0x3909 | Mengembalikan -1, tanpa mengambil log |
| Msg_Log_GetLastRecordPosition | 0x3933 | Mengembalikan -1 |
| Msg_Log_GetRecord | 0x395D | Mengembalikan -1, tanpa membaca record |
| Msg_Log_LogRecordToFile | 0x3987 | Mengembalikan -1, tanpa menulis record |
| Msg_Log_GetLoggingMethod | 0x39B1 | Mengembalikan -1 |
| Msg_Log_SetLoggingMethod | 0x39DB | Hanya wrapper sinkronisasi; tidak menetapkan metode |
| Msg_Log_Clear | 0x3A73 | Mengembalikan -1 |

Ini membuat jalur perekaman Msg_Log pada build backup ini tidak dapat
diandalkan untuk menangkap payload Intervent, walaupun antarmukanya ada.
Belum dilakukan pengujian runtime atau pemeriksaan file terpasang pada HMI
yang sedang berjalan; file online bisa berbeda dari backup.

## Pembandingan tiga backup

Ketiga mesin 6A/12B/13E memiliki SHA-256 identik untuk masing-masing file:

- MsgDiagnosticCE_2d.exe:
  `fca00216b412649522967a4fd7a3694e7d61fc6a51e7210adedcc88b46061f08`
- SecomCE_MessageService_2d.dll:
  `6adfbbacfc62450d7ff0b85b51705d852747ab68a7019b67bb226dc7d52e83a7`

Mengambil EXE/DLL dari dua backup lainnya tidak menyediakan implementasi
logging yang berbeda.

## Jalur diagnostik kedua: CDiagModule di BGUtils

`13E/SC777CE/SecomCE_BGUtils_2d.dll` menyediakan implementasi yang berbeda:

- BGU_NewMessageServiceEvent, RVA 0x30C0.
- CDiagModule::NewMessageServiceEvent, RVA 0x10FCC: memeriksa IsToLog,
  mengalokasikan record, membangun CDiagRecordMessageService, lalu LogEvent.
- CDiagModule::IsToLog, RVA 0x11233: memeriksa flag koneksi/perekaman;
  logging tidak selalu aktif.
- CDiagModule::LogEvent, RVA 0x112A4.
- CDiagModule::WriteToFile, RVA 0x1143B.
- CDiagModule::SendMessageDump, RVA 0x11DCB.
- CDiagModule::GetMessageDumpOverview, RVA 0x1239E.

Ini kandidat yang lebih menjanjikan untuk merekam pesan internal. Keberadaan
fungsi belum membuktikan setiap perubahan Intervent dicatat, logging aktif,
alamat/port aksesnya, atau cara mengaktifkannya tanpa efek samping.

## Kesimpulan praktis

MsgDiagnostic tidak dapat dinyatakan siap dipakai sebagai perekam Intervent
pada backup ini. Jangan mengganti DLL mesin atau mengaktifkan Clear log /
Check structures untuk tujuan pengambilan contoh transaksi.

Langkah riset berikutnya: telusuri CDiagModule (protokol diagnostik, filter,
aktivasi record, dan format record message-service) atau peroleh fasilitas
diagnostik yang didokumentasikan SETEX untuk build kontroler tersebut.
Belum diperlukan pengoperasian alat diagnostik pada mesin produksi untuk
melakukan penelusuran statis lanjutan itu.
