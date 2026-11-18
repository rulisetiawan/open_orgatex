# Pemetaan parameter M_0182.PRG selesai

Tanggal: 29 Oktober 2026. Ruang lingkup selesai: hubungan fungsi → urutan parameter → definisi nama/satuan → nilai tersimpan pada seluruh 58 langkah M_0182.PRG.

Hasil: 20 fungsi, 33 definisi parameter, 468 nilai pada parameter terdefinisi, 191 record fungsi dan 9 komentar.

## Fungsi dan definisi parameter

| ID fungsi | Nama | Urutan parameter tersimpan |
|---|---|---|
| 1 | Program Start | Tidak ada |
| 2 | Program End | Tidak ada |
| 71 | Drain Percent | P1 → #6 Level MA. Percent [%]; P2 → #16 Drain; P3 → #18 Remain Time [min] |
| 122 | Unload | P1 → #36 Alert Time operator [min] |
| 126 | Check | P1 → #36 Alert Time operator [min] |
| 141 | Temperature Control | P1 → #3 Temperature MA [°C]; P2 → #4 Gradient MA [°C/min]; P3 → #5 Time MA [min] |
| 144 | Runtime | P1 → #5 Time MA [min] |
| 237 | Inject AT1 | P1 → #60 Check prep. number; P2 → #3 Temperature MA [°C]; P3 → #4 Gradient MA [°C/min]; P4 → #296 Clean cycl AT1->MA |
| 238 | Inject AT2 | P1 → #60 Check prep. number; P2 → #3 Temperature MA [°C]; P3 → #4 Gradient MA [°C/min]; P4 → #298 Clean cycl AT2->MA |
| 261 | Load | P1 → #36 Alert Time operator [min]; P2 → #3 Temperature MA [°C]; P3 → #4 Gradient MA [°C/min] |
| 404 | Dye Liquor Pump | P1 → #75 Set value variojet [%]; P2 → #73 Speed pump [%] |
| 712 | Material Flow | P1 → #84 Restarts; P2 → #83 Winch speed [m/min] |
| 713 | Fill Level | P1 → #7 water type MA; P2 → #9 Fill quantity MC [L] |
| 716 | ST -> Machine | P1 → #60 Check prep. number; P2 → #9 Fill quantity MC [L] |
| 717 | Filling AT1 Level | P1 → #134 Valve AT1; P2 → #138 Stirrer AT1; P3 → #135 Level AT1 [%]; P4 → #136 Temperature AT1 [°C]; P5 → #137 Dissolving time AT1 [min] |
| 718 | Filling AT2 Level | P1 → #154 Valve AT2; P2 → #158 Stirrer AT2; P3 → #155 Level AT2 [%]; P4 → #156 Temperature AT2 [°C]; P5 → #157 Dissolving time AT2 [min] |
| 720 | Fill Level ST | P1 → #174 Valve ST; P2 → #178 Stirrer ST; P3 → #176 Temperature ST [°C]; P4 → #175 Level ST [L]; P5 → #177 Dissolving Time ST [min] |
| 747 | Rinsing / Cooling | P1 → #4 Gradient MA [°C/min]; P2 → #3 Temperature MA [°C] |
| 938 | Dosing Prpgression 1 | P1 → #3 Temperature MA [°C]; P2 → #4 Gradient MA [°C/min]; P3 → #53 Progression [%]; P4 → #60 Check prep. number; P5 → #22 Dosing Time [min] |
| 939 | Dosing Prpgression 2 | P1 → #3 Temperature MA [°C]; P2 → #4 Gradient MA [°C/min]; P3 → #53 Progression [%]; P4 → #60 Check prep. number; P5 → #22 Dosing Time [min] |

## Contoh yang terverifikasi

- Fungsi 141: tiga parameter berurutan dengan ID definisi 3, 4, 5. Parameter 3 = Temperature MA [°C]; 4 = Gradient MA [°C/min]; 5 = Time MA [min].
- Langkah 35: 132 °C, 2 °C/min, 30 min.
- Fungsi 713: P1 Valve MC (pilihan); P2 Fill quantity MC [L]. Langkah 2 menyimpan 1 dan 1700 L.
- Fungsi 404: P1 Set value variojet [%]; P2 Speed pump [%].
- Fungsi 712: P1 Restarts (Off/On dari text group 200); P2 Winch speed [m/min].

## Mengapa sebelumnya belum terbaca

Record CNF tidak selalu berurutan secara fisik. File memiliki halaman 512 byte, direktori slot di akhir halaman, flag 0x8000 untuk fragment link, serta pointer page/slot. Sebuah record dapat tersebar di beberapa halaman/slot. Setelah fragmen disambung, data masih dikompresi dengan run literal dan run pengulangan. Pencarian string saja tidak menyelesaikan hubungan ini.

## Bukti implementasi

- DLL sumber: Storage/sc777ce/SecomCE_BGUtils_2d.dll. ImageBase 0x100000.
- Api_Btrieve_Decompress RVA 0x2c19 → CBtrieveInterface::Decompress RVA 0x5a9f → routine RVA 0x19aa6. Routine bergantian membaca jumlah literal uint16 + data dan jumlah repeat uint16 + byte berulang.
- Routine pembaca record RVA 0x26fba: flag slot 0x8000 menandakan empat byte pointer lanjutan, directory offset dimask 0x7fff. Helper pointer RVA 0x26708; helper offset slot RVA 0x3871a.
- Sumber struktur: referensi dekompilasi lokal SecomCEDefines/OtxCSLib.Secom.Configuration/T_CFG_FUNCT.cs, T_CFG_FUNCT_PARA.cs, T_CFG_FUNCP.cs, T_CFG_SCALE.cs, T_CFG_SCALE2.cs, T_CFG_TEXTP.cs. Ukuran union lokal cocok dengan 290 byte hasil decode.
- Semua 4.463 fragmen dari halaman data yang valid tercakup tepat sekali dalam 3.519 rantai record. Semua hasil 290 byte, tidak ada key ganda, tidak ada rantai putus/loop pada set record yang diparse.
- 105 record fungsi dan 105 record definisi parameter terbaca, bukan hanya 20 fungsi yang dipakai PRG.
- Seluruh referensi dari 20 definisi fungsi yang dipakai PRG ditemukan. Empat nilai P6=1 fungsi 718 tidak memiliki definisi CNF lokal pada langkah 6, 18, 23, 25.
- Byte PRG asli diverifikasi terhadap hash sebelum pengayaan; hash CNF dicocokkan terhadap inventaris asli.

## Perbedaan versi fungsi 718

CNF lokal, konfigurasi Update, grup 001, backup grup 001, dan grup 002 saat ini mendefinisikan lima parameter. Backup grup 002 mendefinisikan enam; parameter keenam adalah definisi 162, Mixer Type AT2. Daftar text group 32 pada backup: 0=Motor, 1=Valve, 2=Motor/Valve. Jadi P6=1 memiliki padanan Valve pada versi backup tersebut, tetapi tidak memiliki definisi pada CNF lokal. Ini bukti perbedaan konfigurasi, bukan bukti bahwa backup itu sedang dipakai mesin.

## Batas yang masih berlaku

Parameter program adalah nilai proses yang disimpan dalam PRG, bukan alamat register. factor/offset/mode dari CNF disimpan dalam JSON untuk analisis transfer; tidak dikalikan ulang pada tampilan program. index_min/index_max bukan otomatis alamat PLC fisik. display_position adalah posisi tampilan, bukan nomor slot parameter PRG.

Pemetaan nama/satuan parameter yang didefinisikan CNF lokal selesai. Empat nilai P6 fungsi 718 di luar definisi tidak diberi arti. Pemetaan alamat PLC, pembuktian scaling di telegram, makna gradient nol dan verifikasi eksekusi mesin merupakan lingkup lanjutan yang belum dinyatakan selesai.

## Artefak

- M_0182_seluruh_step.html: semua 58 langkah dengan nama/satuan dan pilihan teks yang cocok.
- M_0182_seluruh_step.md: versi teks seluruh langkah.
- M_0182_decoded.json: program plus named_parameters, definisi dan bukti CNF.
- TYPECONF_records_decoded.json: key, byte dekompresi, stream kompresi dan fragmen seluruh 3.519 record.
- TYPECONF_functions_parameters.json: 105 fungsi, 105 parameter dan daftar pilihan teks.
- cnf_decode.py dan enrich_prg_cnf.py: decoder/pengayaan; pembacaan sumber saja.

SHA-256 PRG: `5dfc4765f3d73d83ba24ff38011709b4c9b57997cca4ba98dc7bde0b053dc4d8`
SHA-256 CNF: `2936ceff7a238bfff4b9512ca602d9cc85f132086d279674311432f424bd9f57`