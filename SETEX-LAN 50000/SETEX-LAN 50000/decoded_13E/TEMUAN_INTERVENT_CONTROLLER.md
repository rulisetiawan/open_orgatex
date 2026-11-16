# Bukti Handler Controller & Semantik Jalur Intervent (13E)

Analisis statis lanjutan pada `SecomCE_ProcessInfo_2d.dll` dan `SecomCE_D_BackGround_2d.dll` (build 13E). Tidak menjalankan binary CE dan tidak mengirim paket ke mesin fisik.

---

## 1. Mengapa `SV_CHANGE 106 / object 6` Ditolak (Error 62 `Invalid status`)

Pada router pesan `SecomCE_D_BackGround_2d.dll`:
- Router menerjemahkan kombinasi `(Object ID, Service)` pada RVA `0x2D03A`:
  - `Object 6`, `Service 106` -> Event `0x62`.
  - `Object 6`, `Service 137` -> Event `0x6B`.
  - `Object 41`, `Service 106` -> Event `0x65`.
  - `Object 41`, `Service 137` -> Event `0x6C`.
- Pada seluruh **6 state eksekusi batch/RUN** (`0x16433A`, `0x1647C5`, `0x164CD2`, `0x165140`, `0x165665`, `0x165AD5`):
  - Event `0x62` (Svc 106 / Obj 6) & `0x6B` (Svc 137 / Obj 6) dialihkan ke handler penolakan (`push 0x42` / `push 0x3E` -> `0x12EDD4`), menghasilkan error **`API 19, Error 62` (`Invalid status`)** atau error 66 (`Invalid service`).
  - Sebaliknya, Event `0x65` (Svc 106 / Obj 41) **dan** Event `0x6C` (Svc 137 / Obj 41) langsung diarahkan ke handler perubahan parameter **`0x155E10`**.

**Kesimpulan Fakta:** Object `6` (`OBJID_FUNCTION`) tidak pernah digunakan oleh firmware untuk mengubah parameter langkah yang sedang berjalan (*Intervent*). Jalur Intervent resmi memakai **Object `41` (`OBJID_PARAMETER`)**.

---

## 2. Jalur Lengkap `Service 137 / Object 41` di Controller (`0x155E10`)

Fungsi `0x155E10` di `SecomCE_D_BackGround_2d.dll` menjalankan urutan berikut:

1. **Pemeriksaan Status Batch (`0x155E33`):** Memeriksa bit status `0x10` dan `0x80` pada konteks batch `[this+0x414]+0x20`. Jika aktif (terkunci), tolak dengan error `0x5A` (`90` - *Function active*).
2. **Validasi & Dekode Payload (`0x174E6C`):**
   - `payload[1]` (`entry_count`): harus `1 .. 20`. Jika di luar batas -> **`Error 117` (`0x75`, `Invalid parameter count`)**.
   - `payload[0]` (`flag`): disalin langsung tanpa penolakan.
   - Untuk setiap entri `i` (`stride 6 byte`, dimulai di `payload[2]`):
     - `param_id` (`uint16 LE` di `+2 + 6*i`): harus `1 .. 1000` dan terdaftar (bit `0x80` di konfigurasi parameter). Jika tidak -> **`Error 116` (`0x74`, `Invalid parameter number`)**.
     - `value` (`float32 LE` di `+4 + 6*i`): diclamp dan divalidasi (`0x166B80`, `0x1701AA`) terhadap batas mesin (`TYPECONF.CNF`/`MACHCONF.CNF`) serta dikonversi ke nilai *raw* PLC. Jika di luar batas -> Error `124`/`125` (*Too small/big*).
3. **Pemilihan Target (`target_extra`, `0x155E96`):**
   - Jika `Service == 137 (0x89)`: baca `target_extra` (`uint16 LE`) dari **frame offset `142` (`0x8E`, yaitu `payload[122]`)**.
   - Jika `Service == 106 (0x6A)`: `target_extra` dianggap `0`.
   - Jika `target_extra == 0` atau `1`: panggil `0x141FE7` -> terapkan perubahan ke langkah proses yang **sedang berjalan** di PLC.
   - Jika `target_extra == 0` atau `2`: panggil `0x11C87C` -> perbarui rekaman batch / program berjalan dan picu Event `0x1D` (`29`) yang mencatat perubahan ke `PRxxxxxx.LOG`.
4. **Balasan (`0x12EDD4`):**
   - Jika `error == 0`: kirim respons `msg_type = 2` (Data Response / ACK, panjang payload 0).
   - Jika `error != 0`: kirim respons `msg_type = 3` (Error: `API = 19`, `Error = error_code`).

---

## 3. Semantik Pasti `flag` (`payload[0]`) dan Record `ProcessInfo` (`+0x43 bit 0`)

- Pada `SecomCE_ProcessInfo_2d.dll`:
  - Record tampilan diambil dari database konfigurasi layar (disimpan di `[0x2777D0]`, ukuran record 79 byte / `0x4F`).
  - Pemanggil di `0x1421F9` (input numerik) & `0x1421B8` (enum) mengambil bit 0 dari `[record + 0x43]` untuk mengisi argumen `flag`.
  - Pemanggil langsung di `0x11139F` dan `0x112AAF` meneruskan **`flag = 1`** secara eksplisit (`push 1`).
  - Semua pemanggil tersebut meneruskan **`target_extra = 0`** (`push 0`).
- Pada sisi Controller (`0x1420EF` di dalam `0x141FE7`):
  - Setelah menulis nilai setpoint baru ke antrian PLC (`Object 1009 / SET words`), `0x1420EF` memeriksa `flag` (`[decoded + 1]`):
  - **Jika `flag != 0` (`flag = 1`)**: Controller menambahkan satu instruksi tulis bit ke antrian PLC (`Object 1079 addr 12 = 1` atau `Object 1002 addr 3512 = 1`) sebelum mengeksekusi transfer (`0x13F8F1`). Bit ini adalah **bit pemicu (trigger) Intervent PLC** agar PLC langsung mengadopsi nilai setpoint baru, sehingga tidak ditimpa kembali oleh siklus program.
  - **Jika `flag == 0`**: Controller memperbarui nilai register dan batch, namun tidak mengirim bit pemicu tersebut.

---

## 4. Masalah Otorisasi / PIN

- Baik wrapper `0x8F607` di `SecomCE_ProcessInfo_2d.dll`, builder `Api_ChangeParameterExtended` (`0x295B2`) di `SecomCE_D_BackGround_2d.dll`, maupun handler Controller (`0x155E10` / `0x174E6C`), **tidak ada satu pun yang membaca, memvalidasi, atau menyisipkan kode PIN/passcode ke dalam payload 124 byte**.
- Dialog PIN pada layar fisik HMI hanya dikelola secara lokal oleh GUI CE sebelum membuka jendela input layar sentuh. Jalur TCP port 50000 tidak menyertakan PIN dalam paket `137 / 41`.

---

## 5. Spesifikasi Paket TCP Final (516 byte)

| Offset Frame | Ukuran | Field | Nilai / Format |
| --- | --- | --- | --- |
| `0..1` | `uint16 LE` | Magic | `2` (`0x0002`) |
| `2..3` | `uint16 LE` | Declared length | `140` (`16 + 124`) |
| `4..6` | `3 bytes` | Routing header | `10, 12, 0` (`0x0A 0x0C 0x00`) |
| `9..10` | `uint16 LE` | Packet flag | `1` |
| `14` | `uint8` | Message Type | `1` (Request) |
| `15` | `uint8` | Service | `137` (`0x89`, `SV_CHANGE_EXTENDED`) |
| `16..17` | `uint16 LE` | Object ID | `41` (`0x0029`, `OBJID_PARAMETER`) |
| `18..19` | `uint16 LE` | Payload length | `124` (`0x007C`) |
| `20` | `uint8` | `flag` | `1` (Trigger bit Intervent PLC) |
| `21` | `uint8` | `count` | `1` (Jumlah entri, maks 20) |
| `22..23` | `uint16 LE` | `param_id` | ID definisi parameter (mis. `3` Suhu, `4` Gradien, `5` Waktu) |
| `24..27` | `float32 LE` | `value` | Nilai setpoint baru dalam **satuan tampilan** (`45.0` °C, dll.) |
| `28..141` | `114 bytes` | Padding / entri lain | `0x00` (untuk 1 entri) |
| `142..143` | `uint16 LE` | `target_extra` | `0` (Terapkan ke step aktif & batch log) |
| `144..515` | `372 bytes` | Frame padding | `0x00` |
