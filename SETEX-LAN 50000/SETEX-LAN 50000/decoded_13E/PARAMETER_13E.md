# Parameter dan fungsi mesin 13E

Sumber: `13E/sc777ce/Config/TYPECONF.CNF`, rekonstruksi fragment dan RLE.
Ini ID definisi parameter/fungsi; belum otomatis merupakan alamat SV_CHANGE.

Ditemukan 107 definisi parameter dan 105 fungsi unik.

## Temperature Control

Fungsi **141: Temperature Control**.

| Slot fungsi | ID definisi | Parameter | Satuan | Batas fungsi | Faktor konfigurasi | Mode skala |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | 3 | Temperature MA | °C | 0–150 | 66.66000366210938 | 0 |
| P2 | 4 | Gradient MA | °C/min | 0–9.9 | 66.66000366210938 | 2 |
| P3 | 5 | Time MA | min | 0–180 | 60.0 | 0 |

## Semua definisi parameter

| ID definisi | Nama | Satuan |
| --- | --- | --- |
| 1 | Set Time MA | min |
| 2 | Protect Time MA | min |
| 3 | Temperature MA | °C |
| 4 | Gradient MA | °C/min |
| 5 | Time MA | min |
| 6 | Level MA. Percent | % |
| 7 | water type MA |  |
| 8 | Level MAdig |  |
| 9 | Fill quantity MC | L |
| 10 | Blend water temp. | °C |
| 11 | Rinse Mode |  |
| 12 | Gradient Blendwater | °C/min |
| 13 | Rinse Time | min |
| 14 | Rinse quantity | L |
| 16 | Drain |  |
| 17 | Akis Lt/dak. | Lt/min. |
| 18 | Remain Time | min |
| 22 | Dosing Time | min |
| 27 | Dosing Time ADD2 | min |
| 36 | Alert Time operator | min |
| 53 | Progression | % |
| 57 | Progression 2, | % |
| 60 | Check prep. number |  |
| 67 | Parameter 1 |  |
| 68 | Parameter 2 |  |
| 69 | Parameter 3 |  |
| 70 | Parameter 4 |  |
| 71 | Set Time Pump | min |
| 72 | Protect Time Pump | min |
| 73 | Speed pump | % |
| 74 | Nozzle pressure | bar |
| 75 | Set value variojet | % |
| 81 | Set Time Speed | min |
| 82 | Protect Time Speed | min |
| 83 | Winch speed | m/min |
| 84 | Restarts |  |
| 131 | Set time AT1 | min |
| 132 | Protect time AT1 | min |
| 134 | Valve AT1 |  |
| 135 | Level AT1 | % |
| 136 | Temperature AT1 | °C |
| 137 | Dissolving time AT1 | min |
| 138 | Stirrer AT1 |  |
| 139 | Circulat. time AT1 | min |
| 140 | Recipe number AT1 |  |
| 141 | Preparation no AT1 |  |
| 143 | Tank No. AT1 |  |
| 144 | Prep. release AT1 |  |
| 145 | Station No. AT1 |  |
| 147 | Alert Time op. AT1 | min |
| 148 | batch release AT1 |  |
| 149 | needed for AT1 in | min |
| 151 | Set time AT2 | min |
| 152 | Protect time AT2 | min |
| 154 | Valve AT2 |  |
| 155 | Level AT2 | % |
| 156 | Temperature AT2 | °C |
| 157 | Dissolving time AT2 | min |
| 158 | Stirrer AT2 |  |
| 159 | Circulat. time ADD2 | min |
| 160 | Recipe number AT2 |  |
| 161 | Preparation no AT2 |  |
| 163 | Tank no. AT2 |  |
| 164 | Prep. release AT2 |  |
| 165 | Station No AT2 |  |
| 167 | Alert Time op. AT2 | min |
| 168 | Batch release AT2 |  |
| 169 | Needed for AT2 in | min |
| 171 | Set time ST | min |
| 172 | Protect time ST | min |
| 173 | Fill Quantity ST | L |
| 174 | Valve ST |  |
| 175 | Level ST | L |
| 176 | Temperature ST | °C |
| 177 | Dissolving Time ST | min |
| 178 | Stirrer ST |  |
| 180 | Rezept Nummer NB1 |  |
| 181 | Preparation no ST |  |
| 183 | Tank No. ST |  |
| 184 | Prep. release ST |  |
| 185 | Station No ST |  |
| 187 | Alert Time op. ST | min |
| 188 | Batch release ST |  |
| 189 | Needed for ST in | min |
| 201 | pH Value |  |
| 271 | pH min |  |
| 272 | pH max |  |
| 273 | On Time | Sec. |
| 274 | Off Time | Sec. |
| 275 | Winch speed 1 | m/min |
| 276 | Winch speed 2 | m/min |
| 277 | Winch speed 3 | m/min |
| 278 | Winch speed 4 | m/min |
| 279 | Winch speed 5 | m/min |
| 280 | Winch speed 6 | m/min |
| 281 | Sodaash Quantity | L |
| 282 | Fill quantity AT2 | L |
| 283 | On/Off |  |
| 284 | Conductivity Value | ms |
| 285 | Winch speed 7 | m/min |
| 286 | Winch speed 8 | m/min |
| 287 | Level |  |
| 295 | Clean cycles ST |  |
| 296 | Clean cycl AT1->MA |  |
| 297 | Clean cycl AT1->ST |  |
| 298 | Clean cycl AT2->MA |  |
| 299 | Clean cycl AT2->ST |  |

## Batas decoding AWL

CP14.AWL adalah biner; belum berhasil didekode menjadi instruksi PLC dan operand yang tervalidasi.
Jadi laporan ini tidak mengklaim relasi register SET/ACT dari logika AWL.

## SV_CHANGE

Commands.csv memisahkan 106/6 (fungsi), 106/41 (parameter), dan 137/6 (extended).
ID fungsi, slot P1/P2/P3, ID definisi parameter, dan register SET adalah ruang nomor berbeda.
Payload dan arti field target/konteks harus dicocokkan dengan pemanggil HMI/handler runtime.
Belum ada paket SV_CHANGE yang dikirim oleh alat ini.
