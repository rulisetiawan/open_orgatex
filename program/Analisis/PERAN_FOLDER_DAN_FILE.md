# Peran folder dan file Orgatex / SETEX

Pemeriksaan statis 28 Oktober 2026. Semua 4.122 file sumber di delapan folder asli diinventarisasi, diberi SHA-256, dan diklasifikasikan. Inventaris tidak berarti semua format biner telah didekode. Sumber tidak diubah; executable, updater, SQL, PHP dan koneksi perangkat tidak dijalankan.

## Cara membaca bukti

Isi teks, header/exports/imports PE dan referensi konfigurasi adalah bukti langsung. Peran dari nama/lokasi diberi label dugaan atau batas pemeriksaan. Pustaka yang diimpor membuktikan dependensi statis, bukan bahwa fungsi tersebut sedang aktif.

## Alur sistem

BOOT.INI menunjuk image NK.BIN. Loader.cfg menunjuk sc777ce.EXE; penghubung otomatis boot ke loader belum tersedia dalam salinan ini. sc777ce menggunakan modul background, data, hardware, service, history dan process info. Background mengimpor modul TCP dan ARCNET. ARCNET.CFG mengatur node sendiri 1 dan PLC 2. PATH.CFG menghubungkan direktori lokal dengan direktori host Orgatex. Peran TCP tidak boleh disamakan dengan Modbus tanpa bukti protokol.

## Folder tingkat atas

| Folder | Peran | Batas |
|---|---|---|
| Application Data | Metadata folder aplikasi Windows CE | Hanya desktop.ini |
| My Documents | Folder dokumen dan shortcut template Office | Tidak ditemukan project PLC di sini |
| Network/F | Salinan area jaringan/share berisi OT, Update, manual dan ekspor data | Bukan bukti share masih terhubung |
| Program Files | Shortcut command prompt/WordPad dan template dokumen | Aplikasi inti HMI ada di Storage |
| Recycled | Folder penampungan file terhapus | Kosong |
| Storage | Image boot dan penyimpanan aplikasi/data HMI | Bukan bukti image recovery lengkap |
| Temp | 8 ikon alarm dan 462 ikon proses bitmap | Regenerasi cache belum diuji |
| Windows | Metadata folder dan shortcut bantuan | Bukan seluruh isi OS, sebagian OS dapat berada dalam image NK.BIN |

## Folder runtime HMI: Storage/sc777ce

| Folder | Fungsi |
|---|---|
| Loader | Loader executable, konfigurasinya dan MFC runtime |
| Config | 21 file konfigurasi mesin, fungsi, teks, aset visual dan artefak PLC |
| Programs | 37 file program proses PRG dan satu referensi BATCHREF |
| BATCH | Daftar batch dan data per batch: program, referensi, log serta dua PEX |
| STATUS | Snapshot status/alarm, data line, log event/alarm dan berkas Btrieve |
| ERRORLOG | Tiga log teks diagnostik; berbeda dari rekaman proses biner |
| System | Teks sistem/error, kamus command/object, font dan aset bendera |
| Doc | Manual SECOM777/777CE bahasa Inggris dan Jerman |
| Udreg | Data pembaruan timezone registry |
| Udtools | 22 payload BIN untuk CI16, CP8, CP14 dan IMARC; bukan bukti semuanya terpasang |
| Update | Kosong dalam salinan ini |

## Folder Orgatex: Network/F

| Folder | Fungsi dan batas |
|---|---|
| ENGLISH | 30 manual fitur/modul. Versi campuran; bukan daftar lisensi atau fitur aktif |
| Update/Config | Salinan konfigurasi lain. Tidak otomatis benar untuk HMI ini |
| OT/BATCH | 3.174 file dalam direktori batch: 1.594 PRG dan 1.580 REF |
| OT/BIN | Enam skrip pendukung. Tidak ada executable aplikasi Orgatex dalam folder ini |
| OT/CFG | Pengaturan global/background, profil/dokumen modul, syntax color dan metadata instalasi |
| OT/DOSING | Lima record teks pertukaran dosing, masing-masing 185 byte |
| OT/GROUP/001 dan 002 | Konfigurasi tipe per grup; masing-masing memiliki BACKUP. Hubungan ke mesin tertentu belum dipastikan |
| OT/HISTORY/HS045xxx | Empat pasang program historis BP dan log PR, dikelompokkan berdasarkan rentang nomor |
| OT/PROCEDUR/001..016 | Masing-masing berisi USERCONF.CNF; bukan salinan seluruh library procedure |
| OT/REPORTS | 105 file: 67 CST mesin, berkas report D/E, log ZKX dan snapshot heartbeat |

Folder host MACHINES, OPTIDYE dan udtools disebut PATH.CFG tetapi tidak ada dalam salinan OT ini. Karena itu konfigurasi path tidak sama dengan bukti kelengkapan folder.

## Perbedaan penting antarjenis file

- PRG: program langkah proses/operator, berbeda dari executable Windows dan program logika PLC.
- CP14.AWL: payload PLC biner; ekstensi AWL tidak membuatnya otomatis dapat dibaca sebagai ladder atau instruction list teks.
- CNF: konfigurasi/data terstruktur biner; beberapa menyimpan teks terbaca tetapi itu bukan decoder field lengkap.
- TBM/BBM/BMX: aset visual terstruktur yang tidak diperlakukan sebagai BMP biasa.
- BIN: peran mengikuti lokasinya; NK.BIN adalah image boot yang dirujuk, sedangkan Udtools berisi payload update modul.
- LOG: ERRORLOG/*.txt dapat dibaca langsung; log batch/status lain dapat berupa biner. Ekstensi LOG tidak memastikan teks.
- ACT/PRV: data status tersimpan dan pasangan yang diduga versi sebelumnya; format pemulihan belum diverifikasi.
- REF/BTD/PEX/CST: data pendamping dengan peran berdasarkan konteks; struktur record lengkap belum didekode.

## Penjelasan file satu per satu

Tabel berikut merangkum setiap nama file khusus. Semua instance, termasuk ribuan PRG/REF/BMP dan file dengan suffix numerik, tersedia di inventaris HTML/JSON.

| Nama | Peran | Dasar |
|---|---|---|
| `BOOT.INI` | Pengaturan boot: image NK.BIN, resolusi 640x480 dan warna 16 bit. | Isi teks |
| `NK.BIN` | Image OS yang ditunjuk BOOT.INI; isi image belum dibongkar. | Referensi konfigurasi |
| `BLDR` | Diduga bootloader penyimpanan; mekanisme internal belum dianalisis. | Nama/lokasi |
| `SPLASH.BMX` | Diduga gambar splash saat boot; format belum didekode. | Nama/lokasi |
| `sc777ce.EXE` | Aplikasi utama HMI SECOM777CE, PE x86 Windows CE; log runtime menyebut 2.24. | Header PE, imports dan log |
| `SecomCE_Loader_2d.exe` | Loader aplikasi HMI; Loader.cfg menentukan executable tujuan. Pemicu boot belum diketahui. | Nama dan Loader.cfg |
| `Loader.cfg` | Menetapkan DESTPATH, REM_PATH dan EXEFNAME untuk loader. | Isi teks |
| `PATH.CFG` | Peta direktori lokal, USB dan host untuk konfigurasi, program, batch, report dan firmware. | Isi teks |
| `ARCNET.CFG` | Parameter ARCNET: alamat sendiri 1, PLC 2, timeout 5 detik, timeout alternatif 200 ms. | Isi teks |
| `PLC_IO.CFG` | Katalog jenis modul dan kemampuan I/O: bit/word input-output, PT100, counter dan scaling. Bukan mapping tag mesin terpasang. | Isi teks |
| `SECOM.CFG` | Pengaturan dasar SECOM, penanganan power fail, daftar file konfigurasi tipe dan mesin. | Isi teks |
| `UPDATE.CFG` | Daftar ID/nama modul yang dikenali updater. Tidak membuktikan modul terpasang. | Isi teks |
| `PlcUpdate.exe` | Utilitas pembaruan PLC/modul; bergantung pada modul background, service tool dan hardware. | Nama, imports, UPDATE.CFG |
| `LX800ControllCenter.exe` | Utilitas pengaturan platform LX800; detail menu belum diuji. | Nama dan imports Cgos/FTD2XX |
| `LX800TouchCalibrate.exe` | Utilitas kalibrasi touchscreen LX800. | Nama dan imports hardware |
| `MsgDiagnosticCE_2d.exe` | Diagnostik pesan; mengimpor MessageService dan BGUtils. | Imports PE |
| `SecomCE_RemoteServer_2d.exe` | Komponen remote server; memiliki fungsi terjemahan pesan TCP dan SC737. Protokol/port aktif belum diketahui. | Exports dan imports PE |
| `SecomCE_Arcnet_2d.dll` | Antarmuka komunikasi ARCNET: start/stop modul dan status driver. | Exports Arc_GetDriverStatus/Arc_StartModule |
| `SecomCE_TCP_2d.dll` | Transport TCP: fungsi start server/client, port dan koneksi IPort. Tidak otomatis berarti Modbus TCP. | Exports TCP_StartServer/TCP_StartClient |
| `SecomCE_MessageService_2d.dll` | Layanan pesan yang digunakan modul komunikasi dan diagnostik. | Hubungan imports PE |
| `SecomCE_D_BackGround_2d.dll` | Lapisan background yang menghubungkan status/perangkat dengan TCP, ARCNET dan hardware. | Imports dan exports PE |
| `SecomCE_BGUtils_2d.dll` | Utilitas bersama: konfigurasi, codec CSV, akses data dan diagnostik. | Exports PE |
| `SecomCE_BtrieveAPI_2d.dll` | API akses data/record, termasuk pembacaan log alarm dan teks sistem. | Exports ALRL_ReadAlarmLogRecord dan BtrieveAPI |
| `SecomCE_Hardware_2d.dll` | Abstraksi hardware, pengaturan jaringan, barcode dan screensaver. | Exports CNetworkSettings/CBarcodeReader |
| `SecomCE_History_2d.dll` | Pencatatan dan pembacaan riwayat nilai proses. | Exports History_AddLogRecordV2/History_GetSetValue |
| `SecomCE_ProcessInfo_2d.dll` | Modul informasi/tampilan proses; menerima parameter UI dan batch. | Exports ProcessInfo dan imports |
| `SecomCE_RCClient_2d.dll` | Client sistem remote; memiliki fungsi koneksi dan interaksi layar. Implementasi lengkap belum dibaca. | Exports CRCSystemClient |
| `SecomCE_Service_2d.dll` | Dialog layanan/servis dan fungsi terkait data proses; dipakai aplikasi utama. | Exports CSecomServiceDlg dan imports |
| `SecomCE_ServiceTool_2d.dll` | Varian modul service tool; dipakai PlcUpdate.exe. | Imports/exports PE |
| `mfcce400d.dll` | Runtime Microsoft Foundation Classes untuk Windows CE yang dipakai program C++. | Exports MFC dan imports aplikasi |
| `olece400d.dll` | Runtime pendukung OLE/COM Windows CE. | Exports COleVariant/COleObject |
| `MACHCONF.CNF` | Konfigurasi mesin biner; memuat nama host dan jalur OT. Struktur field belum didekode penuh. | SECOM.CFG dan string biner |
| `TYPECONF.CNF` | Konfigurasi tipe/fungsi proses; berisi label fungsi, parameter dan kondisi mesin. | SECOM.CFG dan string biner |
| `TYPECONT.CNF` | Konfigurasi kontrol/tampilan tipe; berisi nama halaman, bahasa dan identitas konfigurasi. | String biner; peran rinci interpretasi |
| `TYPEFORM.CNF` | Diduga konfigurasi formula/parameter tipe, dengan label perhitungan volume/level. | Nama dan string biner |
| `CONFTEXT.CNF` | Teks konfigurasi multibahasa dan label fungsi. | String biner |
| `FNLEGEND.CNF` | Penjelasan fungsi proses, termasuk inisialisasi dan handshake dengan PLC. | Teks penjelasan dalam biner |
| `USERCONF.CNF` | Konfigurasi pengguna/label proses; sampel memuat label tambahan. Bukan bukti daftar akun. | String biner |
| `PASSCODE.CNF` | Diduga data kode akses; isi sensitif tidak diekstrak. | Nama/lokasi |
| `CP14.AWL` | Artefak PLC biner terkait CP14; bukan listing teks. Logika dan alamat I/O belum didekode. | Header dan string biner |
| `ALRIC_CE.TBM` | Pustaka aset ikon alarm; keterkaitan record belum didekode. | Nama dan daftar SECOM.CFG |
| `FCTIC757.TBM` | Diduga pustaka ikon fungsi. | Nama dan daftar SECOM.CFG |
| `FUNCP757.TBM` | Diduga pustaka gambar fungsi proses. | Nama dan daftar SECOM.CFG |
| `GRPIC757.TBM` | Diduga gambar/ikon grup fungsi. | Nama dan daftar SECOM.CFG |
| `HFUNICON.TBM` | Diduga ikon fungsi untuk tampilan tertentu; arti prefix H belum dipastikan. | Nama dan daftar SECOM.CFG |
| `HGRPICON.TBM` | Diduga ikon grup untuk tampilan tertentu; arti prefix H belum dipastikan. | Nama dan daftar SECOM.CFG |
| `LOGOP757.TBM` | Diduga pustaka logo tampilan. | Nama dan daftar SECOM.CFG |
| `PROCI757.TBM` | Pustaka ikon proses; memuat nama komponen WT_HOR/WNCH. | String biner dan daftar SECOM.CFG |
| `PROCP757.TBM` | Diduga gambar latar/halaman proses; memuat BGBLUE. | String biner dan nama |
| `PRSMP757.TBM` | Diduga gambar proses ukuran kecil/ringkas; memuat BG_BLU_S. | String biner dan nama |
| `STATP757.TBM` | Diduga gambar status; memuat TIME_SL. | String biner dan nama |
| `STPIC_CE.TBM` | Aset gambar terkait tampilan CE; fungsi spesifik belum dipastikan. | Daftar SECOM.CFG |
| `BATCHES.BTD` | Data daftar/manajemen batch lokal; struktur internal belum didekode. | Nama/lokasi |
| `BATCHREF.REF` | Referensi/index yang menyertai program/batch; format relasi belum didekode. | Pola keberadaan bersama PRG |
| `STATUS.ACT` | Snapshot status proses tersimpan; sampel berisi batch 060766 dan nama program. | String biner |
| `STATUS.PRV` | Diduga snapshot status sebelumnya; struktur dan ukuran sama dengan STATUS.ACT. | Pasangan nama/header |
| `ALARM.ACT` | Snapshot status alarm tersimpan; struktur belum didekode. | Nama/lokasi |
| `ALARM.PRV` | Diduga snapshot status alarm sebelumnya. | Pasangan nama/header |
| `ALARMS.LOG` | Log alarm dalam format biner; bukan log teks ERRORLOG. | Nama dan header |
| `EVENTS.LOG` | Log event dalam format biner. | Nama dan header |
| `TFiles.btr` | Berkas record Btrieve di folder status; semantik record belum dipastikan. | Ekstensi/header/lokasi |
| `Commands.csv` | Kamus ID command/object: read/write program, start/stop/resume, parameter dan konfigurasi. Bukan spesifikasi paket jaringan lengkap. | Isi teks |
| `DEFSTEXT.CNF` | Diduga basis teks sistem/default. | Nama/lokasi |
| `ErrorEN.txt` | Daftar teks pesan kesalahan bahasa Inggris. | Isi teks |
| `Flags.BBM` | Diduga aset bendera/bahasa; format internal belum didekode. | Nama/lokasi |
| `UpdateTZI.txt` | Definisi pembaruan timezone registry Windows CE. | Isi teks registry |
| `ORGATEX.INI` | Pengaturan aplikasi Orgatex, report, online status, recipe, database integration dan opsi lainnya. | Isi teks |
| `ZKX200.INI` | Konfigurasi background task: polling, status batch/mesin, recipe, import, housekeeping dan watchdog. | Isi teks |
| `SyntxCol.ini` | Pengaturan pewarnaan sintaks editor; detail pemakai belum diuji. | Nama/lokasi |
| `INSTALL.LOG` | Metadata instalasi Orgatex, direktori dasar F:\OT dan identitas pelanggan. | Isi teks |
| `Kill_Ot.bat` | Menghentikan proses Orgatex untuk alur shutdown/UPS sebelum engine Pervasive berhenti. | Komentar skrip |
| `MvHs2Sub.cmd` | Memindahkan file history PRG/LOG ke subfolder untuk struktur Orgatex 7.0+. | Komentar skrip |
| `egrep.vbs` | Helper pencarian teks regex, mode ignore-case dan inverse/quiet. | Komentar skrip |
| `hostdemo.sql` | Contoh simulasi integrasi host yang memasukkan dyelot ke Orgatex bertahap. | Komentar skrip |
| `dosedemo.sql` | Contoh simulasi tindakan sistem dosing untuk transfer produk ke mesin. | Komentar skrip |
| `improdct.sql` | Menyalin produk dari recipe produksi ke tabel master produk. | Komentar skrip |
| `ZKX200.INF` | Snapshot waktu mulai dan heartbeat background task, bukan bukti status server saat ini. | Isi teks |
| `sync.php` | Integrasi tambahan JSON ke SQL Server untuk machineShrinkages; juga menghapus record tertentu dan menulis ulang JSON. Tidak dieksekusi. | Pembacaan kode |
| `data.json` | Data tambahan terkait sinkronisasi; isi bukan satu dokumen JSON valid saat diuji json.loads. | Uji parser read-only |
| `ReportRecipe_1.xml` | Template layout laporan DevExpress XtraReports, bukan program PLC. | Root XML XtraReportsLayoutSerializer |
| `Document.xlsx` | Ekspor laporan alarm; judul awal menyebut All Alarms except ... Group 01 Jalur A1-A6: 0002 Thermic Alarms. | XML workbook dan sel judul |
| `machine.xls` | Daftar mesin; label terlihat meliputi controller/PLC version/type dan IP Address. Sel belum didekode lengkap. | String dalam OLE XLS |
| `function-label.xls` | Ekspor daftar fungsi/label; terlihat kolom group, item number/name/icon dan fungsi Program Start/Fill Level. | String dalam OLE XLS |
| `catatan.txt` | Catatan satu timestamp; tidak menjelaskan konfigurasi mesin. | Isi teks |
| `autorun.inf` | Metadata label/icon drive OrgaTEX; menunjuk OT/BIN/SYN111.ICO. | Isi teks |
| `ctl3d32.dll` | Diduga library antarmuka 3D Windows lama; pemakai dalam salinan ini belum diketahui. | Nama/lokasi |
| `Thumbs.db` | Cache thumbnail Windows; bukan konfigurasi proses. | Nama/lokasi |
| `desktop.ini` | Metadata tampilan folder/shell; bukan logika kontrol mesin. | Nama/lokasi |

## Salinan konfigurasi dan update

Perbandingan hash untuk semua file dengan nama sama antara konfigurasi HMI dan Network/F/Update/Config:

| File | Hasil |
|---|---|
| `ALRIC_CE.TBM` | Berbeda |
| `CONFTEXT.CNF` | Identik byte-per-byte |
| `CP14.AWL` | Berbeda |
| `FCTIC757.TBM` | Berbeda |
| `FNLEGEND.CNF` | Berbeda |
| `FUNCP757.TBM` | Berbeda |
| `GRPIC757.TBM` | Identik byte-per-byte |
| `HFUNICON.TBM` | Berbeda |
| `HGRPICON.TBM` | Identik byte-per-byte |
| `LOGOP757.TBM` | Identik byte-per-byte |
| `MACHCONF.CNF` | Berbeda |
| `PASSCODE.CNF` | Berbeda |
| `PROCI757.TBM` | Identik byte-per-byte |
| `PROCP757.TBM` | Identik byte-per-byte |
| `PRSMP757.TBM` | Identik byte-per-byte |
| `STATP757.TBM` | Identik byte-per-byte |
| `STPIC_CE.TBM` | Berbeda |
| `TYPECONF.CNF` | Berbeda |
| `TYPECONT.CNF` | Berbeda |
| `TYPEFORM.CNF` | Berbeda |
| `USERCONF.CNF` | Berbeda |

## Temuan yang memengaruhi interpretasi

Log Error3 mencatat masalah akses host SMM-ORGATEX dan disk mapping pada 26 Oktober 2026. ZKX200.INF terpisah mencatat heartbeat terakhir 28 Oktober 2026 pukul 13:27:31 menurut isi file. Kedua catatan berasal dari waktu/komponen berbeda, sehingga tidak cukup untuk menyatakan host masih offline atau seluruh komunikasi sudah normal.

Log 28 Oktober mencatat kegagalan copy system.hv dan TEMPPRG.TMP. Kelengkapan backup tidak dapat dijamin dari folder ini. STATUS.ACT memuat batch 060766; itu snapshot tersimpan, bukan status mesin live.

Ada string identitas seperti Thies dan ROTO dalam konfigurasi. String ini bisa berasal dari template/konfigurasi lama dan tidak dijadikan identifikasi pasti hardware mesin.

## Tingkat pemahaman saat ini

Peran struktur folder, file konfigurasi teks, dependensi program, pola data batch dan skrip pendukung sudah dipetakan. Belum terselesaikan: format internal seluruh CNF/PRG/AWL, mapping I/O aktual, paket komunikasi/port aktif, alur startup lengkap, kecocokan firmware dan kondisi fisik PLC. Manual, nama file, dan daftar modul tidak dipakai sebagai bukti konfigurasi aktif.

## Sumber dan berkas pendamping

Sumber primer: BOOT.INI, Loader.cfg, PATH.CFG, SECOM.CFG, ARCNET.CFG, PLC_IO.CFG, UPDATE.CFG; metadata PE seluruh EXE/DLL; sampel biner konfigurasi/program/status; skrip di OT/BIN; ORGATEX.INI, ZKX200.INI, INSTALL.LOG, ZKX200.INF; judul XML workbook dan string OLE spreadsheet. Pembacaan spreadsheet dibatasi untuk mengenali peran, bukan validasi seluruh sel.

- inventaris_file.html: pencarian semua file menurut nama, peran dan bukti.
- inventaris_file.json: 4.122 record dengan ukuran, peran, konteks dan SHA-256.
- inventaris_folder.json: semua direktori, termasuk direktori batch dan folder kosong.
- dependensi_program.json: machine/subsystem serta imports/exports EXE/DLL yang berhasil diparse.
