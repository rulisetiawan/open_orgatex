# SV_CHANGE pada binary 13E

Pemeriksaan statis; tidak mengirim paket ke kontroler dan tidak mengubah aplikasi v0.5.

## Tiga ruang nomor

- Fungsi Temperature Control: **141**, dari TYPECONF.CNF kategori fungsi.
- Slot fungsi: **P1/P2/P3**, masing-masing merujuk definisi **3/4/5**.
- Register PLC SET: ruang nomor lain, object **1009**. Tidak identik secara otomatis.

Nomor `003` pada daftar langkah layar juga bukan bukti function ID = 3.

## Jalur parameter: service 106, object 41

`SecomCE_D_BackGround_2d.dll`, export `Api_ChangeParameters`, RVA **0x29485**:

| Offset absolut dalam struktur/frame SC737 | Ukuran | Bukti |
| --- | --- | --- |
| 14 | 1 | Jenis pesan 1 (request) |
| 15 | 1 | Service 106 / 0x6A |
| 16 | 2 | Object 41 / 0x0029 |
| 18 | 2 | Panjang payload 124 / 0x007C |
| 20 | 1 | Byte konteks dari argumen pemanggil; arti belum dipastikan |
| 21 | 1 | Jumlah entri perubahan |
| 22 + 6*i | 2 | Nomor entri dari T_MSG_CHANGED_PARA |
| 24 + 6*i | 4 | Nilai entri; representasi float32 didukung signature extended |

Payload diinisialisasi nol. Field +20 tidak boleh diisi tebakan.

`Api_ChangeParameterExtended`, RVA **0x295B2**, memakai service **137**,
object **41**, payload 124, satu entri, dan menulis field uint16 tambahan
pada offset **142** (offset payload 122). Signature `...GGMEHH...` mendukung
dua argumen uint16 dan satu float32. Arti target tambahan masih perlu dilacak.
Kamus Commands.csv mencantumkan service 137 untuk object 6; implementasi
builder menunjukkan object 41 juga dipakai pada jalur lain. Karena itu
Commands.csv bukan definisi lengkap semua struktur API.

## Bukti jalur dialog HMI

`SecomCE_Service_2d.dll`:
- Export `ServiceAPI_ChangeParameters`, RVA **0x20B3C8**, menerima
  `T_MSG_CHANGE_PARAMETER*` dan membentuk dialog perubahan.
- Pemanggilan `Api_ChangeParameters` pada RVA **0x1F850D** meneruskan
  byte pertama buffer dialog sebagai konteks, byte kedua sebagai jumlah,
  dan array buffer+2 sebagai entri perubahan.
- Ini membuktikan format daftar berasal dari dialog HMI, tetapi belum
  membuktikan cara buffer tersebut diisi dari identitas parameter proses.

## Jalur fungsi: service 106, object 6

`Api_ChangeFunction` dan `Api_Rem_ChangeFunction` memanggil builder internal
RVA **0x28CC8**, berbeda dari `Api_ChangeParameters`:
- Object 6, service 106, payload 64 byte.
- Ada byte target pada offset 20, field uint16 pada 21, dan enam nilai
  32-bit pada offset 25, 33, 41, 49, 57, 65.
- Field tambahan ditulis pada 75, 79, 82.
- Identitas field dan semantik nilai yang tidak diubah belum tervalidasi.
  Jangan mengisi slot lain dengan nol karena belum terbukti bermakna keep.

## Apa yang dapat dipakai sekarang

ID definisi 3/4/5 beserta nama, unit, faktor skala, batas fungsi, dan posisi
P1/P2/P3 dapat dipakai untuk membuat katalog parameter pada aplikasi.
Belum dapat dipromosikan menjadi alamat kirim SV_CHANGE yang terverifikasi.

Yang masih diperlukan: menelusuri pembentukan T_MSG_CHANGE_PARAMETER dan
handler runtime, atau mencocokkan satu capture perubahan Intervent yang
diketahui target/nilai lamanya. Capture layar remote saja belum tentu memuat
paket SV_CHANGE karena klik dapat diproses menjadi pesan internal di HMI.

## Batas AWL

CP14.AWL (369666 byte) mengandung nama proyek `iS2000kg_V2_plc.pro`.
Belum ada decoder instruksi/operand yang tervalidasi untuk file tersebut.
Katalog hasil sesi ini berasal dari TYPECONF.CNF, bukan disassembly penuh AWL.
