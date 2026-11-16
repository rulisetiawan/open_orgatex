> Pembaruan 29 Oktober 2026: hubungan fungsi dan parameter yang disebut belum terurai pada laporan awal ini kini sudah selesai untuk seluruh M_0182.PRG. Lihat [hasil terbaru](PEMETAAN_PARAMETER_TUNTAS.md).

# Pembacaan konfigurasi CNF dan kaitannya dengan PLC

Pemeriksaan statis 28 Oktober 2026. Sumber di Storage/SC777CE tidak diubah dan tidak dijalankan. Ini pembacaan sebagian struktur dan teks, bukan decoding lengkap database Btrieve.

## Hasil utama

| File | Bukti yang ditemukan | Makna / batas |
|---|---|---|
| MACHCONF.CNF | Format biner; nama host SMM-ORGATEX dan jalur OT telah ditemukan | Pengaturan spesifik mesin/host. Field akun/kode akses tidak diekstrak ke laporan |
| TYPECONF.CNF | Record fungsi dan definisi parameter bernama, satuan, label I/O/alarm | Kamus fungsi/parameter HMI; relasi lengkap dan indeks PLC belum diurai |
| TYPECONT.CNF | plc communication, set temperature, Set/Act temperature, Level MC / Tanks, tipe level detection | Konfigurasi kontrol/tampilan; nama yang terbaca belum membuktikan alamat register |
| TYPEFORM.CNF | Dry Liquor Level, Dye Liquor Level, Fill level-TotalAdd, Filling Quantity | Konfigurasi terkait formula/perhitungan level/volume; rumus internal belum didekode |
| CONFTEXT.CNF | Teks multibahasa terkait fungsi/configuration | Label dan penjelasan tampilan |
| FNLEGEND.CNF | Penjelasan aktivasi, inisialisasi, acknowledgement PLC dan perpindahan langkah | Bukti dokumenter handshake HMI-PLC |
| USERCONF.CNF | Label proses termasuk NETRAL ULANG | Konfigurasi label pengguna; bukan bukti daftar akun |
| PASSCODE.CNF | File tersedia | Isi kode akses tidak dibaca/dipublikasikan |
| CP14.AWL | Biner, string nama project iS2000kg_V2_plc.pro | Artefak program PLC; bukan source .pro lengkap atau listing ladder |
| PLC_IO.CFG | E/EW/A/AW serta tipe modul | Katalog kemampuan I/O, bukan daftar wiring aktual |

## Contoh definisi parameter dari TYPECONF.CNF

Pola key sesuai struktur T_TYPECONF_KEY_1 adalah (ID kategori, type, index), masing-masing uint16. Kandidat berikut ditemukan dengan kategori 2 (ID_CFG_FUNCP), type 0, nomor index di bawah. Teks dan offset adalah pengamatan langsung; batas record belum didekompresi penuh, sehingga token unit di sekitar record belum dipakai untuk menetapkan parameter PRG otomatis.

| Offset desimal | Index kandidat | Teks yang terlihat |
|---|---|---|
| 6162 | 1 | Set Time MA; min |
| 6219 | 2 | Protect Time MA; min |
| 6307 | 3 | Temperature MA |
| 6385 | 4 | Gradient MA; C/min |
| 6465 | 5 | Time MA; min |
| 3487 | 6 | Level MA. P |
| 6746 | 8 | Level MAdig |
| 6670 | 9 | Fill quantity MC |
| 6894 | 10 | Blend water temp. |
| 6980 | 12 | Gradient Blendwater; C/min |
| 6814 | 13 | Rinse Time; min |
| 19543 | 136 | Temperature AT1 |

Contoh ini menguatkan adanya parameter temperatur, gradient dan waktu, tetapi belum membuktikan P1/P2/P3 fungsi 141 tepat menunjuk index 3/4/5. Nilai 132/2/30 pada langkah 35 tetap belum diberi satuan secara pasti.

## Struktur penghubung fungsi dan parameter

Sumber referensi yang diperiksa langsung pada sesi ini: D:/ORGATEX/OrgaTEX/analysis/decompiled/SecomCEDefines/OtxCSLib.Secom.Configuration.

- T_CFG_FUNCT: key fungsi, nama, ack, type, attribute, synchron_marker, jumlah parameter, enam entri T_CFG_FUNCT_PARA, daftar controller/timer/constant, indeks waktu dan marker step0.
- T_CFG_FUNCT_PARA: nomor parameter no, posisi pos, min/max/default, index_min/index_max dan attribute.
- T_CFG_FUNCP: key parameter, nama dua bahasa, scale, attribute, scale2.
- T_CFG_PARAM: definisi parameter lain dengan batas nilai, text_group dan listidx. Kategori ini berbeda dari FUNCP; jangan disamakan.
- T_CFG_SCALE: unit, digit, factor, offset, x1/x2/y1/y2 dan mode. Ini menjelaskan mengapa nilai mentah tidak boleh langsung dianggap satuan teknik.
- T_TYPECONF_KEY_1: id, type, index. ID kategori record berbeda dari ID fungsi 141 dan berbeda lagi dari alamat PLC.
- Typeconf_ID: FUNCT=3, FUNCP=2, PARAM=44, CTRPA=17, PLCCP=37, MODUL=39, IONAM=40, MODUL_CP16=74. Nilai enum adalah definisi tipe record yang didukung, bukan bukti setiap tipe ada/aktif dalam file ini.

Referensi dekompilasi berasal dari paket Orgatex lain yang tersedia lokal. Nama dan sejumlah key cocok dengan konfigurasi ini, tetapi kompatibilitas seluruh versi struktur belum dibuktikan.

## Koreksi decoding PRG sebelumnya

Struktur T_PRG_ELEMENT dan T_PRG_PARA dari folder OtxCSLib.Secom.Messages cocok persis dengan ukuran record 65 byte dan posisi nilai yang diperiksa.

| Offset dalam record | Ukuran | Field |
|---|---|---|
| 0 | 2 | step |
| 2 | 1 | line |
| 3 | 1 | label |
| 4 | 2 | function |
| 6 | 1 | ack |
| 7..42 | 36 | 6 parameter: attribute byte + formula byte + float32 |
| 43 | 2 | protect_time |
| 45 | 2 | set_time |
| 47 | 2 | operator_txt |
| 49 | 2 | modul_no |
| 51 | 2 | loop_count |
| 53 | 1 | label_type |
| 54 | 4 | start_act_value |
| 58 | 2 | hold_time |
| 60 | 1 | reserved |
| 61 | 2 | treatment |
| 63 | 2 | treatment_step |

P7-P9 pada hasil awal merupakan interpretasi sementara atas area metadata dan bukan parameter proses. Tampilan HTML, laporan Markdown, decoder dan JSON sudah diperbarui menjadi P1-P6. Semua 191 record fungsi berhasil disusun ulang identik byte-per-byte. Struktur langkah tetap 58 langkah dan 9 komentar. Field attribute/formula awalnya dilihat sebagai uint16 gabungan; keduanya adalah dua byte terpisah dalam struktur referensi. Pada target nilainya sama-sama nol.

## Hubungan dengan PLC

FNLEGEND.CNF menjelaskan bahwa Program Start menginisialisasi marker fungsi dan setpoint, mereset data konsumsi, lalu mengatur marker START. Perpindahan langkah menunggu konfirmasi PLC. Program End memberi tahu PLC bahwa program selesai dan menunggu konfirmasi sebelum menyelesaikan status. Ini penjelasan dalam file, belum pengujian online.

DLL lokal SecomCE_BtrieveAPI_2d.dll mengekspor CNFT_GetFunction, CNFT_GetFunctionParameter, CNFT_GetFunctionRefTable, CNFT_ReadFunctionConfiguration, CNFT_ReadFunctionParameters serta API pembacaan MACHCONF. Hal ini mendukung pemisahan database konfigurasi dari runtime yang membacanya.

Alur yang didukung bukti: PRG meminta fungsi -> runtime membaca definisi fungsi/parameter dan konfigurasi -> runtime berkomunikasi dengan PLC -> PLC mengembalikan status/ack. ARCNET.CFG memiliki alamat sendiri 1 dan PLC 2. Pilihan protokol aktif, detail telegram, indeks PLC serta mapping output fisik belum terverifikasi.

## Yang belum terjawab

1. Relasi persis setiap posisi parameter fungsi 141/404/dll ke nomor definisi parameter dalam database.
2. Dekompresi/rekonstruksi record Btrieve lengkap, bukan pencarian string saja.
3. Nomor area/index PLC yang menerima setpoint dan mengirim actual value/status.
4. Arti ack=0/1/6, enum parameter, dan aturan eksekusi pada build HMI ini.
5. Logika internal CP14.AWL, I/O fisik dan validasi runtime.

Teks terpilih dari enam CNF beserta offset disimpan dalam CNF_teks_dan_offset.json. Potongan teks dapat terputus oleh struktur biner; bukan ekspor record resmi. Laporan tidak menyertakan dump MACHCONF atau PASSCODE untuk menghindari pencampuran data akses dengan analisis proses.
