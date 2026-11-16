# WORKSPACE PROGRAM MESIN CELUP (OPENORGATEX)

Direktori ini dirancang khusus untuk mengelola **konfigurasi mesin fisik** dan **program celup biner (`.PRG`)** secara terisolasi **per masing-masing mesin**.

Dengan struktur ini, program celup yang Anda buat di OpenOrgaTEX akan selalu menggunakan definisi fungsi, batasan suhu, dan jumlah tangki yang **100% akurat sesuai mesin yang Anda pilih**.

---

## 1. Struktur Folder Per Mesin

Setiap mesin memiliki foldernya sendiri (misal `MESIN_1A`, `MESIN_A002`, `MESIN_TD12`, dst.) dengan 4 subfolder bernomor urut jelas:

```text
WORKSPACE_PROGRAM_MESIN/
│
├── _TEMPLATE_MESIN_BARU/                  <-- Template acuan untuk menambah mesin baru
│   ├── 01_CONFIG_DARI_HMI/                <-- [PASTE DI SINI] File download dari HMI (\Storage\SC777CE\Config\)
│   │   ├── TYPECONF.CNF                   <-- Kamus fungsi & parameter PLC
│   │   ├── CONFTEXT.CNF                   <-- Label teks bahasa & teks alarm
│   │   ├── MACHCONF.CNF                   <-- Konfigurasi kapasitas kg & tangki mesin
│   │   └── PETUNJUK_DOWNLOAD_DARI_HMI.txt
│   ├── 02_CONFIG_SIAP_PAKAI/              <-- Hasil decoding JSON yang dibaca Web OpenOrgaTEX
│   │   ├── typeconf_functions.json
│   │   ├── conftext_aligned.json
│   │   └── machine_profile.json
│   ├── 03_CONTOH_PRG_DARI_HMI/            <-- Simpan copy program lama (M_xxxx.PRG) sebagai acuan/template
│   └── 04_HASIL_PROGRAM_CELUP/            <-- Hasil compile program baru (.PRG) siap copy ke flashdisk/FTP
│
├── MESIN_1A/                              <-- Workspace Mesin 1A (IP: 172.16.110.101)
├── MESIN_A002/                            <-- Workspace Mesin A002 (IP: 172.16.110.102)
├── MESIN_TD12/                            <-- Workspace Mesin TD12
├── MESIN_TD13/                            <-- Workspace Mesin TD13
├── MESIN_TD14/                            <-- Workspace Mesin TD14
│
├── kelola_mesin.py                        <-- Skrip CLI otomatis
└── README.md
```

---

## 2. Alur Kerja Praktis (SOP)

### Langkah 1: Download File Konfigurasi dari HMI Mesin
1. Di layar HMI mesin celup (SETEX / SECOM 777/737), tancapkan flashdisk USB.
2. Buka folder: `\Storage\SC777CE\Config\` (atau `C:\SC777CE\Config\`).
3. Copy 3 file utama:
   - `TYPECONF.CNF`
   - `CONFTEXT.CNF`
   - `MACHCONF.CNF` *(jika ada)*
4. *(Opsional)* Ambil juga 1 contoh program yang sudah terbukti stabil di mesin tersebut dari `\Storage\SC777CE\Programs\` (misal `M_0001.PRG`).

### Langkah 2: Paste File ke Komputer Server
1. Buka folder mesin tujuan di komputer ini, misal:
   `WORKSPACE_PROGRAM_MESIN/MESIN_TD12/01_CONFIG_DARI_HMI/`
2. Paste file `TYPECONF.CNF` dan `CONFTEXT.CNF` di situ.
3. Jika Anda mengambil contoh program lama, paste ke:
   `WORKSPACE_PROGRAM_MESIN/MESIN_TD12/03_CONTOH_PRG_DARI_HMI/`

### Langkah 3: Sinkronkan ke OpenOrgaTEX
Jalankan perintah di terminal:
```bash
python WORKSPACE_PROGRAM_MESIN/kelola_mesin.py --sync TD12
```
Sistem akan otomatis mengonversi file biner HMI menjadi JSON di folder `02_CONFIG_SIAP_PAKAI`.

### Langkah 4: Buat Program di Web OpenOrgaTEX
1. Buka OpenOrgaTEX Program Editor.
2. Pilih **Mesin: TD12**.
3. Sistem secara otomatis membatasi pilihan F-Code, parameter suhu, gradien, dan tangki sesuai spesifikasi mesin TD12.
4. Klik **Simpan & Kompilasi**.

### Langkah 5: Ambil File Program Hasil Kompilasi
File biner `.PRG` yang telah dikompilasi akan langsung tersedia di:
`WORKSPACE_PROGRAM_MESIN/MESIN_TD12/04_HASIL_PROGRAM_CELUP/M_xxxx.PRG`
Anda tinggal menyalin file ini ke flashdisk untuk dimasukkan ke mesin, atau langsung dikirim via FTP.

---

## 3. Perintah Bantuan (`kelola_mesin.py`)

* **Cek status semua mesin:**
  ```bash
  python WORKSPACE_PROGRAM_MESIN/kelola_mesin.py --status
  ```
* **Sinkronkan 1 mesin:**
  ```bash
  python WORKSPACE_PROGRAM_MESIN/kelola_mesin.py --sync TD12
  ```
* **Sinkronkan seluruh mesin sekaligus:**
  ```bash
  python WORKSPACE_PROGRAM_MESIN/kelola_mesin.py --sync-all
  ```
* **Menambah mesin baru:**
  ```bash
  python WORKSPACE_PROGRAM_MESIN/kelola_mesin.py --tambah-mesin TD15
  ```
