# Hasil capture ARCNET MANUAL

Rentang: 2026-11-10T13:53:47.331+07:00 sampai 2026-11-10T13:56:04.210+07:00.
Paket lolos pemeriksaan header, ukuran, CRC16 dan panjang payload: 1674. Ditolak: 0.

## Transaksi perintah

| Waktu | Arah node | Service | Object | Data penting |
| --- | --- | --- | --- | --- |
| 2026-11-10T13:54:04.686+07:00 | 1 → 2 | 102 SV_START | 1004 | payload 70 byte |
| 2026-11-10T13:54:04.702+07:00 | 2 → 1 | 102 SV_START | 1004 |  |
| 2026-11-10T13:54:05.731+07:00 | 1 → 2 | 102 SV_START | 1005 | payload 484 byte |
| 2026-11-10T13:54:05.818+07:00 | 2 → 1 | 102 SV_START | 1005 |  |
| 2026-11-10T13:54:06.904+07:00 | 1 → 2 | 102 SV_START | 1005 | payload 484 byte |
| 2026-11-10T13:54:06.950+07:00 | 2 → 1 | 102 SV_START | 1005 |  |
| 2026-11-10T13:54:13.986+07:00 | 1 → 2 | 109 SV_SET_MANUAL | 1004 |  |
| 2026-11-10T13:54:20.180+07:00 | 1 → 2 | 102 SV_START | 1006 | Fungsi 713; P1 ID 7 = 1 (raw 1); P2 ID 9 = 2000 (raw 2000) |
| 2026-11-10T13:54:20.272+07:00 | 2 → 1 | 102 SV_START | 1006 |  |
| 2026-11-10T13:54:20.872+07:00 | 1 → 2 | 110 SV_RESET_MANUAL | 1004 |  |
| 2026-11-10T13:54:20.874+07:00 | 2 → 1 | 110 SV_RESET_MANUAL | 1004 |  |
| 2026-11-10T13:54:25.740+07:00 | 1 → 2 | 102 SV_START | 1005 | payload 484 byte |
| 2026-11-10T13:54:25.785+07:00 | 2 → 1 | 102 SV_START | 1005 |  |
| 2026-11-10T13:54:29.369+07:00 | 1 → 2 | 109 SV_SET_MANUAL | 1004 |  |
| 2026-11-10T13:54:29.525+07:00 | 2 → 1 | 109 SV_SET_MANUAL | 1004 |  |
| 2026-11-10T13:54:34.447+07:00 | 1 → 2 | 102 SV_START | 1006 | Fungsi 141; P1 ID 3 = 40 (raw 2666); P2 ID 4 = 1 (raw 67); P3 ID 5 = 2 (raw 120) |
| 2026-11-10T13:54:34.592+07:00 | 2 → 1 | 102 SV_START | 1006 |  |
| 2026-11-10T13:54:35.123+07:00 | 1 → 2 | 110 SV_RESET_MANUAL | 1004 |  |
| 2026-11-10T13:54:35.257+07:00 | 2 → 1 | 110 SV_RESET_MANUAL | 1004 |  |

## Batas interpretasi

Nama layanan mengikuti Commands.csv SETEX; objek 1004 PLC_PROGRAM, 1005 PLC_STEP, 1006 PLC_FUNCTION.
Rangkaian 109/1004, 102/1006, 110/1004 menunjukkan jalur manual ke PLC.
ACK bertipe 2 dengan payload kosong berarti respons diterima; efek fisik tetap perlu dicocokkan.
Belum dapat dipastikan rangkaian ini berasal dari tombol Intervent saat RUN atau operasi manual terpisah.
Jawaban pengguna "betul" pada pertanyaan pilihan dua mode belum membedakan keduanya.
Tidak ada service 106/137 pada frame yang terekam. Absennya di capture ARCNET tidak membuktikan
ketiadaan layanan internal tersebut: Controller dapat menerjemahkannya ke operasi PLC lain.
Paket ARCNET ini tidak boleh langsung direplay ke TCP port 50000; lapisan header/routing berbeda.
Tidak ada pengiriman, perubahan mode, atau perubahan aplikasi PLC dilakukan oleh analyzer ini.

## Counter selama rentang log

```json
{
  "CRC_OK": 1655,
  "CRC_FAIL": 0,
  "USB_DROP": 0,
  "Q_DROP": 0,
  "BQ_DROP": 375429
}
```
Counter CRC/queue adalah statistik alat, bukan jaminan seluruh transaksi berhasil tertangkap.
BQ_DROP perlu ditafsirkan menurut firmware sniffer; belum otomatis berarti paket PLC hilang.
