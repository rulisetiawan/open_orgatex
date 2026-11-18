from pathlib import Path
from collections import Counter
import hashlib, json, html, pefile

ROOT = Path(r'D:\File HMI')
OUT = ROOT / 'Analisis'
original_roots = ['Application Data','My Documents','Network','Program Files','Recycled','Storage','Temp','Windows']
files = sorted(p for folder in original_roots for p in (ROOT/folder).rglob('*') if p.is_file())
specific = {
'BOOT.INI': ('Pengaturan boot: image NK.BIN, resolusi 640x480 dan warna 16 bit.', 'Isi teks'),
'NK.BIN': ('Image OS yang ditunjuk BOOT.INI; isi image belum dibongkar.', 'Referensi konfigurasi'),
'BLDR': ('Diduga bootloader penyimpanan; mekanisme internal belum dianalisis.', 'Nama/lokasi'),
'SPLASH.BMX': ('Diduga gambar splash saat boot; format belum didekode.', 'Nama/lokasi'),
'sc777ce.EXE': ('Aplikasi utama HMI SECOM777CE, PE x86 Windows CE; log runtime menyebut 2.24.', 'Header PE, imports dan log'),
'SecomCE_Loader_2d.exe': ('Loader aplikasi HMI; Loader.cfg menentukan executable tujuan. Pemicu boot belum diketahui.', 'Nama dan Loader.cfg'),
'Loader.cfg': ('Menetapkan DESTPATH, REM_PATH dan EXEFNAME untuk loader.', 'Isi teks'),
'PATH.CFG': ('Peta direktori lokal, USB dan host untuk konfigurasi, program, batch, report dan firmware.', 'Isi teks'),
'ARCNET.CFG': ('Parameter ARCNET: alamat sendiri 1, PLC 2, timeout 5 detik, timeout alternatif 200 ms.', 'Isi teks'),
'PLC_IO.CFG': ('Katalog jenis modul dan kemampuan I/O: bit/word input-output, PT100, counter dan scaling. Bukan mapping tag mesin terpasang.', 'Isi teks'),
'SECOM.CFG': ('Pengaturan dasar SECOM, penanganan power fail, daftar file konfigurasi tipe dan mesin.', 'Isi teks'),
'UPDATE.CFG': ('Daftar ID/nama modul yang dikenali updater. Tidak membuktikan modul terpasang.', 'Isi teks'),
'PlcUpdate.exe': ('Utilitas pembaruan PLC/modul; bergantung pada modul background, service tool dan hardware.', 'Nama, imports, UPDATE.CFG'),
'LX800ControllCenter.exe': ('Utilitas pengaturan platform LX800; detail menu belum diuji.', 'Nama dan imports Cgos/FTD2XX'),
'LX800TouchCalibrate.exe': ('Utilitas kalibrasi touchscreen LX800.', 'Nama dan imports hardware'),
'MsgDiagnosticCE_2d.exe': ('Diagnostik pesan; mengimpor MessageService dan BGUtils.', 'Imports PE'),
'SecomCE_RemoteServer_2d.exe': ('Komponen remote server; memiliki fungsi terjemahan pesan TCP dan SC737. Protokol/port aktif belum diketahui.', 'Exports dan imports PE'),
'SecomCE_Arcnet_2d.dll': ('Antarmuka komunikasi ARCNET: start/stop modul dan status driver.', 'Exports Arc_GetDriverStatus/Arc_StartModule'),
'SecomCE_TCP_2d.dll': ('Transport TCP: fungsi start server/client, port dan koneksi IPort. Tidak otomatis berarti Modbus TCP.', 'Exports TCP_StartServer/TCP_StartClient'),
'SecomCE_MessageService_2d.dll': ('Layanan pesan yang digunakan modul komunikasi dan diagnostik.', 'Hubungan imports PE'),
'SecomCE_D_BackGround_2d.dll': ('Lapisan background yang menghubungkan status/perangkat dengan TCP, ARCNET dan hardware.', 'Imports dan exports PE'),
'SecomCE_BGUtils_2d.dll': ('Utilitas bersama: konfigurasi, codec CSV, akses data dan diagnostik.', 'Exports PE'),
'SecomCE_BtrieveAPI_2d.dll': ('API akses data/record, termasuk pembacaan log alarm dan teks sistem.', 'Exports ALRL_ReadAlarmLogRecord dan BtrieveAPI'),
'SecomCE_Hardware_2d.dll': ('Abstraksi hardware, pengaturan jaringan, barcode dan screensaver.', 'Exports CNetworkSettings/CBarcodeReader'),
'SecomCE_History_2d.dll': ('Pencatatan dan pembacaan riwayat nilai proses.', 'Exports History_AddLogRecordV2/History_GetSetValue'),
'SecomCE_ProcessInfo_2d.dll': ('Modul informasi/tampilan proses; menerima parameter UI dan batch.', 'Exports ProcessInfo dan imports'),
'SecomCE_RCClient_2d.dll': ('Client sistem remote; memiliki fungsi koneksi dan interaksi layar. Implementasi lengkap belum dibaca.', 'Exports CRCSystemClient'),
'SecomCE_Service_2d.dll': ('Dialog layanan/servis dan fungsi terkait data proses; dipakai aplikasi utama.', 'Exports CSecomServiceDlg dan imports'),
'SecomCE_ServiceTool_2d.dll': ('Varian modul service tool; dipakai PlcUpdate.exe.', 'Imports/exports PE'),
'mfcce400d.dll': ('Runtime Microsoft Foundation Classes untuk Windows CE yang dipakai program C++.', 'Exports MFC dan imports aplikasi'),
'olece400d.dll': ('Runtime pendukung OLE/COM Windows CE.', 'Exports COleVariant/COleObject'),
'MACHCONF.CNF': ('Konfigurasi mesin biner; memuat nama host dan jalur OT. Struktur field belum didekode penuh.', 'SECOM.CFG dan string biner'),
'TYPECONF.CNF': ('Konfigurasi tipe/fungsi proses; berisi label fungsi, parameter dan kondisi mesin.', 'SECOM.CFG dan string biner'),
'TYPECONT.CNF': ('Konfigurasi kontrol/tampilan tipe; berisi nama halaman, bahasa dan identitas konfigurasi.', 'String biner; peran rinci interpretasi'),
'TYPEFORM.CNF': ('Diduga konfigurasi formula/parameter tipe, dengan label perhitungan volume/level.', 'Nama dan string biner'),
'CONFTEXT.CNF': ('Teks konfigurasi multibahasa dan label fungsi.', 'String biner'),
'FNLEGEND.CNF': ('Penjelasan fungsi proses, termasuk inisialisasi dan handshake dengan PLC.', 'Teks penjelasan dalam biner'),
'USERCONF.CNF': ('Konfigurasi pengguna/label proses; sampel memuat label tambahan. Bukan bukti daftar akun.', 'String biner'),
'PASSCODE.CNF': ('Diduga data kode akses; isi sensitif tidak diekstrak.', 'Nama/lokasi'),
'CP14.AWL': ('Artefak PLC biner terkait CP14; bukan listing teks. Logika dan alamat I/O belum didekode.', 'Header dan string biner'),
'ALRIC_CE.TBM': ('Pustaka aset ikon alarm; keterkaitan record belum didekode.', 'Nama dan daftar SECOM.CFG'),
'FCTIC757.TBM': ('Diduga pustaka ikon fungsi.', 'Nama dan daftar SECOM.CFG'),
'FUNCP757.TBM': ('Diduga pustaka gambar fungsi proses.', 'Nama dan daftar SECOM.CFG'),
'GRPIC757.TBM': ('Diduga gambar/ikon grup fungsi.', 'Nama dan daftar SECOM.CFG'),
'HFUNICON.TBM': ('Diduga ikon fungsi untuk tampilan tertentu; arti prefix H belum dipastikan.', 'Nama dan daftar SECOM.CFG'),
'HGRPICON.TBM': ('Diduga ikon grup untuk tampilan tertentu; arti prefix H belum dipastikan.', 'Nama dan daftar SECOM.CFG'),
'LOGOP757.TBM': ('Diduga pustaka logo tampilan.', 'Nama dan daftar SECOM.CFG'),
'PROCI757.TBM': ('Pustaka ikon proses; memuat nama komponen WT_HOR/WNCH.', 'String biner dan daftar SECOM.CFG'),
'PROCP757.TBM': ('Diduga gambar latar/halaman proses; memuat BGBLUE.', 'String biner dan nama'),
'PRSMP757.TBM': ('Diduga gambar proses ukuran kecil/ringkas; memuat BG_BLU_S.', 'String biner dan nama'),
'STATP757.TBM': ('Diduga gambar status; memuat TIME_SL.', 'String biner dan nama'),
'STPIC_CE.TBM': ('Aset gambar terkait tampilan CE; fungsi spesifik belum dipastikan.', 'Daftar SECOM.CFG'),
'BATCHES.BTD': ('Data daftar/manajemen batch lokal; struktur internal belum didekode.', 'Nama/lokasi'),
'BATCHREF.REF': ('Referensi/index yang menyertai program/batch; format relasi belum didekode.', 'Pola keberadaan bersama PRG'),
'STATUS.ACT': ('Snapshot status proses tersimpan; sampel berisi batch 060766 dan nama program.', 'String biner'),
'STATUS.PRV': ('Diduga snapshot status sebelumnya; struktur dan ukuran sama dengan STATUS.ACT.', 'Pasangan nama/header'),
'ALARM.ACT': ('Snapshot status alarm tersimpan; struktur belum didekode.', 'Nama/lokasi'),
'ALARM.PRV': ('Diduga snapshot status alarm sebelumnya.', 'Pasangan nama/header'),
'ALARMS.LOG': ('Log alarm dalam format biner; bukan log teks ERRORLOG.', 'Nama dan header'),
'EVENTS.LOG': ('Log event dalam format biner.', 'Nama dan header'),
'TFiles.btr': ('Berkas record Btrieve di folder status; semantik record belum dipastikan.', 'Ekstensi/header/lokasi'),
'Commands.csv': ('Kamus ID command/object: read/write program, start/stop/resume, parameter dan konfigurasi. Bukan spesifikasi paket jaringan lengkap.', 'Isi teks'),
'DEFSTEXT.CNF': ('Diduga basis teks sistem/default.', 'Nama/lokasi'),
'ErrorEN.txt': ('Daftar teks pesan kesalahan bahasa Inggris.', 'Isi teks'),
'Flags.BBM': ('Diduga aset bendera/bahasa; format internal belum didekode.', 'Nama/lokasi'),
'UpdateTZI.txt': ('Definisi pembaruan timezone registry Windows CE.', 'Isi teks registry'),
'ORGATEX.INI': ('Pengaturan aplikasi Orgatex, report, online status, recipe, database integration dan opsi lainnya.', 'Isi teks'),
'ZKX200.INI': ('Konfigurasi background task: polling, status batch/mesin, recipe, import, housekeeping dan watchdog.', 'Isi teks'),
'SyntxCol.ini': ('Pengaturan pewarnaan sintaks editor; detail pemakai belum diuji.', 'Nama/lokasi'),
'INSTALL.LOG': ('Metadata instalasi Orgatex, direktori dasar F:\\OT dan identitas pelanggan.', 'Isi teks'),
'Kill_Ot.bat': ('Menghentikan proses Orgatex untuk alur shutdown/UPS sebelum engine Pervasive berhenti.', 'Komentar skrip'),
'MvHs2Sub.cmd': ('Memindahkan file history PRG/LOG ke subfolder untuk struktur Orgatex 7.0+.', 'Komentar skrip'),
'egrep.vbs': ('Helper pencarian teks regex, mode ignore-case dan inverse/quiet.', 'Komentar skrip'),
'hostdemo.sql': ('Contoh simulasi integrasi host yang memasukkan dyelot ke Orgatex bertahap.', 'Komentar skrip'),
'dosedemo.sql': ('Contoh simulasi tindakan sistem dosing untuk transfer produk ke mesin.', 'Komentar skrip'),
'improdct.sql': ('Menyalin produk dari recipe produksi ke tabel master produk.', 'Komentar skrip'),
'ZKX200.INF': ('Snapshot waktu mulai dan heartbeat background task, bukan bukti status server saat ini.', 'Isi teks'),
'sync.php': ('Integrasi tambahan JSON ke SQL Server untuk machineShrinkages; juga menghapus record tertentu dan menulis ulang JSON. Tidak dieksekusi.', 'Pembacaan kode'),
'data.json': ('Data tambahan terkait sinkronisasi; isi bukan satu dokumen JSON valid saat diuji json.loads.', 'Uji parser read-only'),
'ReportRecipe_1.xml': ('Template layout laporan DevExpress XtraReports, bukan program PLC.', 'Root XML XtraReportsLayoutSerializer'),
'Document.xlsx': ('Ekspor laporan alarm; judul awal menyebut All Alarms except ... Group 01 Jalur A1-A6: 0002 Thermic Alarms.', 'XML workbook dan sel judul'),
'machine.xls': ('Daftar mesin; label terlihat meliputi controller/PLC version/type dan IP Address. Sel belum didekode lengkap.', 'String dalam OLE XLS'),
'function-label.xls': ('Ekspor daftar fungsi/label; terlihat kolom group, item number/name/icon dan fungsi Program Start/Fill Level.', 'String dalam OLE XLS'),
'catatan.txt': ('Catatan satu timestamp; tidak menjelaskan konfigurasi mesin.', 'Isi teks'),
'autorun.inf': ('Metadata label/icon drive OrgaTEX; menunjuk OT/BIN/SYN111.ICO.', 'Isi teks'),
'ctl3d32.dll': ('Diduga library antarmuka 3D Windows lama; pemakai dalam salinan ini belum diketahui.', 'Nama/lokasi'),
'Thumbs.db': ('Cache thumbnail Windows; bukan konfigurasi proses.', 'Nama/lokasi'),
'desktop.ini': ('Metadata tampilan folder/shell; bukan logika kontrol mesin.', 'Nama/lokasi'),
}

def classify(p):
    rel=p.relative_to(ROOT).as_posix(); n=p.name; ext=p.suffix.lower()
    if n in specific: role,basis=specific[n]
    elif ext=='.pdf': role,basis='Dokumentasi/referensi: '+p.stem+'. Keberadaan manual tidak membuktikan fitur terpasang.','Nama dokumen; isi tidak semua ditelaah'
    elif ext=='.lnk': role,basis='Shortcut Windows CE: '+p.read_text(errors='replace').strip(),'Isi teks shortcut'
    elif ext=='.ttf': role,basis='Font untuk teks antarmuka HMI.','Ekstensi dan lokasi'
    elif ext=='.pwt': role,basis='Template dokumen Pocket Word/WordPad.','Ekstensi dan lokasi Office/Templates'
    elif ext=='.bmp': role,basis=('Ikon alarm' if '/AlarmIcon/' in rel else 'Ikon komponen/animasi proses')+' di folder Temp; bukan program kontrol. Mekanisme regenerasi belum diuji.','Header bitmap dan lokasi'
    elif '/Udtools/' in rel and ext=='.bin': role,basis='Payload firmware/update keluarga '+p.parent.name+'; kode suffix tidak ditafsirkan sebagai versi pasti.','UPDATE.CFG dan lokasi'
    elif ext=='.prg': role,basis='Program langkah proses dyeing '+('untuk batch '+p.parent.name if '/BATCH/' in rel else 'arsip historis' if '/HISTORY/' in rel else 'dalam library lokal')+'; format parameter lengkap belum didekode.','Pola direktori dan sampel string PRG'
    elif ext=='.pex': role,basis='Berkas pendamping program pada batch; mungkin data ekstensi, semantik belum terkonfirmasi.','Nama/lokasi saja'
    elif ext=='.log' and ('/BATCH/' in rel or '/HISTORY/' in rel): role,basis='Rekaman proses batch; format biner belum didekode.','Pola nama PR dan lokasi'
    elif '/ERRORLOG/' in rel: role,basis='Log teks diagnostik aplikasi: startup, jaringan, alarm dan power fail.','Isi teks'
    elif n.startswith('LINE_') and ext=='.act': role,basis='Diduga snapshot line/urutan eksekusi proses; memuat referensi batch.','Nama dan string biner'
    elif n.startswith('EDX300PF.'): role,basis='Profil/dokumen modul EDX300; header menyebut /EDX300. Makna field belum didekode.','Header biner'
    elif n.startswith('OLN420DC.'): role,basis='Dokumen tersimpan modul OLN420; memuat C420Machine, CBatchInfo dan DocumentRights.','String biner'
    elif '/DOSING/' in rel: role,basis='Record pertukaran dosing bertanda pemisah |, memuat nomor batch dan kode mesin. Arti setiap kolom belum dipastikan.','Isi teks'
    elif ext=='.cst': role,basis='Diduga record status mesin '+p.stem.replace('MACH','')+'; format belum didekode.','Nama/lokasi REPORTS'
    elif '/REPORTS/' in rel and (n.lower().startswith('zkx200.') or n.lower().startswith('zkx210.')): role,basis='File report/log background task ZKX; arti suffix numerik belum dipastikan.','Pola nama dan lokasi'
    elif '/REPORTS/' in rel: role,basis='Berkas laporan/pertukaran data mesin; arti prefix dan suffix belum didekode.','Lokasi dan PATH.CFG'
    else: role,basis='Peran belum teridentifikasi; perlu analisis format lanjutan.','Belum terkonfirmasi'
    context=''
    if '/Update/Config/' in rel: context='Salinan di area Update; status kandidat update hanya interpretasi, bukan bukti sedang dipakai.'
    elif '/GROUP/' in rel: context='Konfigurasi grup '+rel.split('/GROUP/')[1].split('/')[0]+('; salinan BACKUP.' if '/BACKUP/' in rel else '.')
    elif '/PROCEDUR/' in rel: context='Di direktori procedure '+p.parent.name+'; direktori ini hanya memuat USERCONF dalam salinan yang tersedia.'
    return role,basis,context

rows=[]; pe_rows=[]
for p in files:
    role,basis,context=classify(p)
    rows.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,role=role,basis=basis,context=context,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    if p.suffix.lower() in ['.exe','.dll']:
        try:
            pe=pefile.PE(str(p),fast_load=True);pe.parse_data_directories(directories=[0,1])
            pe_rows.append(dict(path=p.relative_to(ROOT).as_posix(),machine=hex(pe.FILE_HEADER.Machine),subsystem=pe.OPTIONAL_HEADER.Subsystem,imports=[x.dll.decode(errors='replace') for x in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[])],exports=[x.name.decode(errors='replace') for x in getattr(getattr(pe,'DIRECTORY_ENTRY_EXPORT',None),'symbols',[]) if x.name]))
            pe.close()
        except pefile.PEFormatError: pass

dirs=[]
for base in original_roots:
    for p in [ROOT/base]+sorted(d for d in (ROOT/base).rglob('*') if d.is_dir()):
        prefix=p.relative_to(ROOT).as_posix()+'/'
        rr=[x for x in rows if x['path'].startswith(prefix)]
        dirs.append(dict(path=prefix,count=len(rr),bytes=sum(x['bytes'] for x in rr)))
(OUT/'inventaris_file.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'inventaris_folder.json').write_text(json.dumps(dirs,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'dependensi_program.json').write_text(json.dumps(pe_rows,ensure_ascii=False,indent=2),encoding='utf-8')

intro='''# Peran folder dan file Orgatex / SETEX

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
'''
report=intro
for name,(role,basis) in specific.items():
    if any(p.name==name for p in files): report+=f'| `{name}` | {role.replace("|","/")} | {basis} |\n'
report+='''
## Salinan konfigurasi dan update

Perbandingan hash untuk semua file dengan nama sama antara konfigurasi HMI dan Network/F/Update/Config:

| File | Hasil |
|---|---|
'''
for p in sorted((ROOT/'Storage/sc777ce/Config').iterdir()):
    q=ROOT/'Network/F/Update/Config'/p.name
    report+=f'| `{p.name}` | '+('Identik byte-per-byte' if q.exists() and p.read_bytes()==q.read_bytes() else 'Berbeda' if q.exists() else 'Tidak ada di Update')+' |\n'
report+='''
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
'''
(OUT/'PERAN_FOLDER_DAN_FILE.md').write_text(report,encoding='utf-8')
payload=json.dumps(rows,ensure_ascii=False).replace('<','\\u003c')
page='''<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Inventaris Orgatex / SETEX</title><style>body{font:15px system-ui;margin:28px;background:#f4f6f8;color:#1e293b}h1{font-size:25px}input,select{padding:12px;border:1px solid #bdc8d3;border-radius:6px;margin:4px}input{width:50%}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;text-align:left;border-bottom:1px solid #dce2e8;vertical-align:top}th{background:#173b50;color:white;position:sticky;top:0}td:first-child{word-break:break-word;min-width:260px}small{color:#526579}button{padding:9px;margin:8px}a{color:#12657c}.top{max-width:1100px}</style><div class="top"><h1>Inventaris Orgatex / SETEX</h1><p>4.122 file sumber · Analisis statis 28 Oktober 2026 · Tidak menjalankan kontrol mesin.</p><p>Peran berdasarkan isi/header atau interpretasi nama/lokasi. Kolom bukti menjelaskan batas kepastian. Semua sumber tetap utuh.</p><p><a href="PERAN_FOLDER_DAN_FILE.md">Laporan rinci</a> · <a href="inventaris_file.json">Inventaris JSON + SHA-256</a> · <a href="inventaris_folder.json">Semua folder</a></p><input id="q" placeholder="Cari file, folder, fungsi, atau batch…" aria-label="Pencarian"><select id="scope" aria-label="Folder utama"><option value="">Semua folder</option>Storage</option><option>Network</option><option>Temp</option><option>Windows</option><option>Program Files</option><option>My Documents</option><option>Application Data</option></select><p id="count"></p><button id="prev">Sebelumnya</button><button id="next">Berikutnya</button></div><table><thead><tr><th>File</th><th>Ukuran</th><th>Peran</th><th>Dasar / konteks</th></tr></thead><tbody id="body"></tbody></table><script>const data=PAYLOAD;const q=document.getElementById('q'),scope=document.getElementById('scope');let page=0;function draw(){const term=q.value.toLowerCase();const found=data.filter(r=>(!scope.value||r.path.startsWith(scope.value+'/'))&&[r.path,r.role,r.basis,r.context].join(' ').toLowerCase().includes(term));const pages=Math.max(1,Math.ceil(found.length/100));page=Math.min(page,pages-1);document.getElementById('count').textContent=found.length+' file · Halaman '+(page+1)+' / '+pages;const body=document.getElementById('body');body.replaceChildren();for(const r of found.slice(page*100,page*100+100)){const tr=document.createElement('tr');for(const text of [r.path,r.bytes.toLocaleString('id-ID')+' byte',r.role,r.basis+(r.context?' — '+r.context:'')]){const td=document.createElement('td');td.textContent=text;tr.appendChild(td)}body.appendChild(tr)}document.getElementById('prev').disabled=page===0;document.getElementById('next').disabled=page>=pages-1}q.oninput=scope.onchange=()=>{page=0;draw()};document.getElementById('prev').onclick=()=>{page--;draw()};document.getElementById('next').onclick=()=>{page++;draw()};draw();</script></html>'''.replace('PAYLOAD',payload)
# Repair select markup before writing the standalone viewer.
page=page.replace('<option>Storage</option></option>','<option>Storage</option>')
(OUT/'inventaris_file.html').write_text(page,encoding='utf-8')
assert len(rows)==4122 and len({x['path'] for x in rows})==4122
assert not any('belum teridentifikasi' in x['role'] for x in rows), [x['path'] for x in rows if 'belum teridentifikasi' in x['role']]
print(json.dumps({'files':len(rows),'folders':len(dirs),'pe_files':len(pe_rows),'total_bytes':sum(x['bytes'] for x in rows),'report':str(OUT/'PERAN_FOLDER_DAN_FILE.md')},indent=2))
