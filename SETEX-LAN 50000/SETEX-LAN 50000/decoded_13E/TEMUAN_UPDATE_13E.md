# Temuan backup 13E yang diperbarui

Log batch 062900 berhasil direkonstruksi dari fragment Btrieve dan RLE.
75 record berukuran 154 byte; urutan lengkap: True.
5 fragment tidak didekode sebagai record mandiri (termasuk kemungkinan lanjutan).

## Perubahan fungsi pada catatan batch

Angka subtype 6 muncul pada waktu perubahan yang Anda laporkan melalui HMI.
Makna enum resmi belum ditemukan; pelabelan sebagai perubahan adalah inferensi dari korelasi log.

| Waktu mesin | Step | Fungsi | P1 | P2 | P3 |
| --- | --- | --- | --- | --- | --- |
| 2026-11-10T12:00:32 | 2 | 713 Fill Level | 1 | 3000 | 0 |
| 2026-11-10T12:00:53 | 2 | 713 Fill Level | 1 | 4000 | 0 |
| 2026-11-10T12:02:40 | 3 | 141 Temperature Control | 41 | 1 | 2 |
| 2026-11-10T12:07:20 | 4 | 71 Drain Percent | 0 | 1 | 3 |

## Program tersimpan TESTPR

Programs/M_0005.PRG dan BATCH/062900/M_0005.PRG sama-sama berisi:
- Step 2: fungsi 713, P1=1, P2=8000 L.
- Step 3: fungsi 141, P1=45 °C, P2=1 °C/min, P3=2 min.
- Step 4: fungsi 71, P1=0%, P2=1, P3=2 min.

Catatan batch merekam perubahan yang cocok dengan pembacaan Python setelahnya.
Ini menguatkan pemisahan nilai runtime dan resep, bukan bukti bahwa pembacaan 4000 L salah.

## Batas bukti

Log batch adalah hasil pencatatan aplikasi, bukan capture paket wire SV_CHANGE.
Belum membuktikan apakah perubahan menggunakan service 106/41 atau 137/41,
dan belum menyelesaikan arti flag perintah. Tidak ada pengiriman ke mesin.

Format record/field diinterpretasikan dari struktur lokal dan korelasi tanggal,
ID fungsi, nilai PRG, serta nilai hasil baca. Raw bytes dan lokasi fragment disimpan di JSON.
