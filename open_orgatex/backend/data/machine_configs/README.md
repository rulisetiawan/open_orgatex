# Machine Config Repository (OpenOrgaTEX)

Direktori ini digunakan untuk menyimpan seluruh konfigurasi hardware kontroler HMI mesin celup (SETEX / SECOM 777, 737, 838).
Konfigurasi ini memastikan bahwa saat OpenOrgaTEX membuat dan mengompilasi program celup (`.PRG`), fungsi dan parameter yang dihasilkan **100% valid dan cocok dengan spesifikasi fisik masing-masing mesin**.

---

## 1. Struktur Direktori

```text
machine_configs/
├── groups/                                 <-- Konfigurasi per kelompok/tipe mesin
│   ├── GROUP_001_HIGH_TEMP_JET/            <-- Grup Mesin Jet Suhu Tinggi (HT Jet)
│   │   ├── raw/                            <-- File asli dari HMI (\Storage\sc777ce\Config\)
│   │   │   ├── TYPECONF.CNF                <-- [KRUSIAL] Kamus fungsi & parameter PLC
│   │   │   ├── CONFTEXT.CNF                <-- [KRUSIAL] Label teks bahasa & alarm
│   │   │   ├── FNLEGEND.CNF                <-- Penjelasan handshake langkah PLC
│   │   │   └── TYPECONT.CNF                <-- Konfigurasi kontrol & level
│   │   ├── decoded/                        <-- Hasil decoding siap pakai untuk sistem Web
│   │   │   ├── typeconf_functions.json     <-- Kamus fungsi & parameter (JSON)
│   │   │   └── conftext_aligned.json       <-- Kamus label & teks (JSON)
│   │   └── group_info.json                 <-- Profil spesifikasi grup mesin
│   │
│   ├── GROUP_002_ATMOSPHERIC/              <-- Grup Mesin Atmosfer (Winch/Soft Flow Atmos)
│   │   ├── raw/
│   │   ├── decoded/
│   │   └── group_info.json
│   │
│   ├── GROUP_003_YARN_PACKAGE/             <-- Grup Mesin Celup Benang / Cone
│   │   ├── raw/
│   │   ├── decoded/
│   │   └── group_info.json
│   │
│   └── GROUP_TEMPLATE/                     <-- Template untuk grup mesin baru
│       ├── raw/
│       ├── decoded/
│       └── group_info.json
│
├── machines/                               <-- Data spesifik per unit nomor mesin fisik
│   ├── MC_TEMPLATE/                        <-- Template profil per mesin
│   │   ├── MACHCONF.CNF                    <-- [Opsional] File konfigurasi unik per mesin
│   │   └── machine_profile.json            <-- Data kapasitas Kg, IP, tangki
│   └── README.md
│
└── scripts/
    └── import_hmi_config.py                <-- Skrip konversi otomatis raw .CNF ke JSON
```

---

## 2. Cara Mengambil File dari HMI Mesin

1. **Via Storage di HMI**:
   * Tancapkan Storage USB ke HMI kontroler SETEX/SECOM.
   * Masuk ke Windows CE Explorer / file manager di kontroler.
   * Buka folder: `\Storage\sc777ce\Config\` (atau `C:\sc777ce\Config\`).
   * Salin (Copy) file `TYPECONF.CNF`, `CONFTEXT.CNF`, dan `MACHCONF.CNF` ke Storage.

2. **Via FTP (Jaringan LAN Mesin)**:
   * Hubungkan laptop / server ke IP mesin celup (port 21).
   * Download folder `/Storage/sc777ce/Config/`.

---

## 3. Cara Memasang File ke Server OpenOrgaTEX

1. Letakkan file yang sudah diambil dari HMI ke folder grup mesin yang sesuai:
   * Taruh di: `groups/<NAMA_GRUP>/raw/`
2. Jalankan skrip decoding otomatis:
   ```bash
   python scripts/import_hmi_config.py --group GROUP_001_HIGH_TEMP_JET
   ```
3. Skrip akan otomatis mengurai file `TYPECONF.CNF` dan `CONFTEXT.CNF` menjadi JSON di folder `decoded/`.
4. Editor Program Celup OpenOrgaTEX di Web browser akan langsung memuat fungsi dan parameter resmi mesin tersebut!
