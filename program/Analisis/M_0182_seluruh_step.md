# M_0182.PRG — PRG 47 DYLON 

Diperbarui 29 Oktober 2026: nama dan satuan parameter kini diambil dari TYPECONF.CNF lokal.

58 langkah; 191 record fungsi; 9 komentar; 468 nilai pada parameter terdefinisi dipetakan; 20 definisi fungsi dan 33 definisi parameter digunakan.

## Pemetaan fungsi 141 yang sudah terurai

| Posisi PRG | ID definisi | Nama | Satuan | Batas dalam fungsi |
|---|---|---|---|---|
| P1 | 3 | Temperature MA | °C | 0–150 |
| P2 | 4 | Gradient MA | °C/min | 0–9,9 |
| P3 | 5 | Time MA | min | 0–180 |

index_min/index_max dapat merujuk batas lain. Nilai batas nol atau indeks nonzero tidak diperlakukan sebagai batas engineering final tanpa pembacaan konfigurasi terkait.

## Seluruh langkah dan fungsi

| Step | Slot | ID fungsi | Fungsi | Parameter bernama |
|---|---|---|---|---|
| 1 | 1 | 1 | Program Start | Tidak memiliki parameter proses |
| 2 | 1 | 713 | Fill Level | P1 water type MA = 1 (cold water); P2 Fill quantity MC = 1700 L |
| 2 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 90 % |
| 2 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 220 m/min |
| 3 | 1 | 126 | Check | P1 Alert Time operator = 0 min |
| 3 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 90 % |
| 3 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 220 m/min |
| 3 | 4 | 717 | Filling AT1 Level | P1 Valve AT1 = 2 (liquor); P2 Stirrer AT1 = 1; P3 Level AT1 = 40 %; P4 Temperature AT1 = 0 °C; P5 Dissolving time AT1 = 0 min |
| 4 | Komentar | — | — | -ANTI CREASE |
| 4 | 1 | 237 | Inject AT1 | P1 Check prep. number = 0; P2 Temperature MA = 60 °C; P3 Gradient MA = 0 °C/min; P4 Clean cycl AT1->MA = 1 |
| 4 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 60 % |
| 4 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 150 m/min |
| 5 | 1 | 261 | Load | P1 Alert Time operator = 5 min; P2 Temperature MA = 60 °C; P3 Gradient MA = 0 °C/min |
| 5 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 60 % |
| 5 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 150 m/min |
| 6 | 1 | 144 | Runtime | P1 Time MA = 2 min |
| 6 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 6 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 6 | 4 | 717 | Filling AT1 Level | P1 Valve AT1 = 1 (cold water); P2 Stirrer AT1 = 1; P3 Level AT1 = 55 %; P4 Temperature AT1 = 0 °C; P5 Dissolving time AT1 = 1 min |
| 6 | 5 | 718 | Filling AT2 Level | P1 Valve AT2 = 1 (cold water); P2 Stirrer AT2 = 1; P3 Level AT2 = 55 %; P4 Temperature AT2 = 0 °C; P5 Dissolving time AT2 = 1 min; P6=1 [tanpa definisi CNF lokal; backup grup 002: Mixer Type AT2 = Valve] |
| 7 | 1 | 237 | Inject AT1 | P1 Check prep. number = 0; P2 Temperature MA = 0 °C; P3 Gradient MA = 0 °C/min; P4 Clean cycl AT1->MA = 1 |
| 7 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 7 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 8 | 1 | 238 | Inject AT2 | P1 Check prep. number = 0; P2 Temperature MA = 0 °C; P3 Gradient MA = 0 °C/min; P4 Clean cycl AT2->MA = 1 |
| 8 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 8 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 9 | 1 | 144 | Runtime | P1 Time MA = 3 min |
| 9 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 9 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 9 | 4 | 717 | Filling AT1 Level | P1 Valve AT1 = 1 (cold water); P2 Stirrer AT1 = 1; P3 Level AT1 = 50 %; P4 Temperature AT1 = 0 °C; P5 Dissolving time AT1 = 2 min |
| 10 | 1 | 237 | Inject AT1 | P1 Check prep. number = 0; P2 Temperature MA = 70 °C; P3 Gradient MA = 0 °C/min; P4 Clean cycl AT1->MA = 1 |
| 10 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 10 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 11 | 1 | 141 | Temperature Control | P1 Temperature MA = 95 °C; P2 Gradient MA = 0 °C/min; P3 Time MA = 20 min |
| 11 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 11 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 11 | 6 | 720 | Fill Level ST | P1 Valve ST = 1 (cold water); P2 Stirrer ST = 0; P3 Temperature ST = 60 °C; P4 Level ST = 1100 L; P5 Dissolving Time ST = 0 min |
| 12 | 1 | 747 | Rinsing / Cooling | P1 Gradient MA = 0 °C/min; P2 Temperature MA = 75 °C |
| 12 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 12 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 13 | 1 | 71 | Drain Percent | P1 Level MA. Percent = 0 %; P2 Drain = 1 (drain 1); P3 Remain Time = 1 min |
| 13 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 13 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 14 | 1 | 716 | ST -> Machine | P1 Check prep. number = 0; P2 Fill quantity MC = 2000 L |
| 14 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 14 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 15 | 1 | 144 | Runtime | P1 Time MA = 8 min |
| 15 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 15 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 15 | 6 | 720 | Fill Level ST | P1 Valve ST = 0; P2 Stirrer ST = 0; P3 Temperature ST = 0 °C; P4 Level ST = 1100 L; P5 Dissolving Time ST = 0 min |
| 16 | 1 | 71 | Drain Percent | P1 Level MA. Percent = 0 %; P2 Drain = 1 (drain 1); P3 Remain Time = 1 min |
| 16 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 16 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 17 | 1 | 716 | ST -> Machine | P1 Check prep. number = 0; P2 Fill quantity MC = 1800 L |
| 17 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 17 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 18 | 1 | 144 | Runtime | P1 Time MA = 2 min |
| 18 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 18 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 18 | 5 | 718 | Filling AT2 Level | P1 Valve AT2 = 1 (cold water); P2 Stirrer AT2 = 1; P3 Level AT2 = 55 %; P4 Temperature AT2 = 0 °C; P5 Dissolving time AT2 = 1 min; P6=1 [tanpa definisi CNF lokal; backup grup 002: Mixer Type AT2 = Valve] |
| 19 | Komentar | — | — | CUKA |
| 19 | 1 | 238 | Inject AT2 | P1 Check prep. number = 0; P2 Temperature MA = 0 °C; P3 Gradient MA = 0 °C/min; P4 Clean cycl AT2->MA = 1 |
| 19 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 19 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 20 | 1 | 141 | Temperature Control | P1 Temperature MA = 60 °C; P2 Gradient MA = 0 °C/min; P3 Time MA = 15 min |
| 20 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 20 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 20 | 6 | 720 | Fill Level ST | P1 Valve ST = 0; P2 Stirrer ST = 0; P3 Temperature ST = 0 °C; P4 Level ST = 1100 L; P5 Dissolving Time ST = 0 min |
| 21 | 1 | 71 | Drain Percent | P1 Level MA. Percent = 0 %; P2 Drain = 1 (drain 1); P3 Remain Time = 1 min |
| 21 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 21 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 22 | 1 | 713 | Fill Level | P1 water type MA = 1 (cold water); P2 Fill quantity MC = 1500 L |
| 22 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 22 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 23 | 1 | 144 | Runtime | P1 Time MA = 2 min |
| 23 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 23 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 23 | 5 | 718 | Filling AT2 Level | P1 Valve AT2 = 2 (liquor); P2 Stirrer AT2 = 1; P3 Level AT2 = 50 %; P4 Temperature AT2 = 0 °C; P5 Dissolving time AT2 = 2 min; P6=1 [tanpa definisi CNF lokal; backup grup 002: Mixer Type AT2 = Valve] |
| 24 | Komentar | — | — | AUX  |
| 24 | 1 | 238 | Inject AT2 | P1 Check prep. number = 0; P2 Temperature MA = 60 °C; P3 Gradient MA = 0 °C/min; P4 Clean cycl AT2->MA = 1 |
| 24 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 24 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 25 | 1 | 141 | Temperature Control | P1 Temperature MA = 60 °C; P2 Gradient MA = 0 °C/min; P3 Time MA = 2 min |
| 25 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 25 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 25 | 4 | 717 | Filling AT1 Level | P1 Valve AT1 = 1 (cold water); P2 Stirrer AT1 = 1; P3 Level AT1 = 50 %; P4 Temperature AT1 = 0 °C; P5 Dissolving time AT1 = 2 min |
| 25 | 5 | 718 | Filling AT2 Level | P1 Valve AT2 = 1 (cold water); P2 Stirrer AT2 = 1; P3 Level AT2 = 50 %; P4 Temperature AT2 = 50 °C; P5 Dissolving time AT2 = 2 min; P6=1 [tanpa definisi CNF lokal; backup grup 002: Mixer Type AT2 = Valve] |
| 26 | Komentar | — | — | PH AA |
| 26 | 1 | 237 | Inject AT1 | P1 Check prep. number = 0; P2 Temperature MA = 60 °C; P3 Gradient MA = 0 °C/min; P4 Clean cycl AT1->MA = 1 |
| 26 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 26 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 27 | 1 | 141 | Temperature Control | P1 Temperature MA = 60 °C; P2 Gradient MA = 0 °C/min; P3 Time MA = 2 min |
| 27 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 27 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 28 | Komentar | — | — | - PH B |
| 28 | 1 | 238 | Inject AT2 | P1 Check prep. number = 0; P2 Temperature MA = 60 °C; P3 Gradient MA = 0 °C/min; P4 Clean cycl AT2->MA = 1 |
| 28 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 28 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 29 | 1 | 141 | Temperature Control | P1 Temperature MA = 60 °C; P2 Gradient MA = 0 °C/min; P3 Time MA = 5 min |
| 29 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 29 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 30 | Komentar | — | — | DYES |
| 30 | 1 | 938 | Dosing Prpgression 1 | P1 Temperature MA = 60 °C; P2 Gradient MA = 0 °C/min; P3 Progression = 0 %; P4 Check prep. number = 0; P5 Dosing Time = 15 min |
| 30 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 30 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 31 | 1 | 141 | Temperature Control | P1 Temperature MA = 60 °C; P2 Gradient MA = 0 °C/min; P3 Time MA = 10 min |
| 31 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 31 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 32 | Komentar | — | — | GARAM |
| 32 | 1 | 939 | Dosing Prpgression 2 | P1 Temperature MA = 60 °C; P2 Gradient MA = 0 °C/min; P3 Progression = 0 %; P4 Check prep. number = 0; P5 Dosing Time = 15 min |
| 32 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 32 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 33 | 1 | 141 | Temperature Control | P1 Temperature MA = 60 °C; P2 Gradient MA = 0 °C/min; P3 Time MA = 5 min |
| 33 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 33 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 34 | 1 | 141 | Temperature Control | P1 Temperature MA = 100 °C; P2 Gradient MA = 3 °C/min; P3 Time MA = 5 min |
| 34 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 34 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 35 | 1 | 141 | Temperature Control | P1 Temperature MA = 132 °C; P2 Gradient MA = 2 °C/min; P3 Time MA = 30 min |
| 35 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 35 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 35 | 6 | 720 | Fill Level ST | P1 Valve ST = 1 (cold water); P2 Stirrer ST = 0; P3 Temperature ST = 0 °C; P4 Level ST = 1100 L; P5 Dissolving Time ST = 0 min |
| 36 | 1 | 141 | Temperature Control | P1 Temperature MA = 105 °C; P2 Gradient MA = 0 °C/min; P3 Time MA = 0 min |
| 36 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 36 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 37 | 1 | 747 | Rinsing / Cooling | P1 Gradient MA = 0 °C/min; P2 Temperature MA = 75 °C |
| 37 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 37 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 38 | 1 | 71 | Drain Percent | P1 Level MA. Percent = 0 %; P2 Drain = 1 (drain 1); P3 Remain Time = 2 min |
| 38 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 38 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 39 | 1 | 716 | ST -> Machine | P1 Check prep. number = 0; P2 Fill quantity MC = 1800 L |
| 39 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 39 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 40 | 1 | 144 | Runtime | P1 Time MA = 8 min |
| 40 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 40 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 40 | 6 | 720 | Fill Level ST | P1 Valve ST = 0; P2 Stirrer ST = 0; P3 Temperature ST = 0 °C; P4 Level ST = 1100 L; P5 Dissolving Time ST = 0 min |
| 41 | 1 | 71 | Drain Percent | P1 Level MA. Percent = 0 %; P2 Drain = 1 (drain 1); P3 Remain Time = 2 min |
| 41 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 30 %; P2 Speed pump = 95 % |
| 41 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 42 | 1 | 716 | ST -> Machine | P1 Check prep. number = 0; P2 Fill quantity MC = 1900 L |
| 42 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 42 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 43 | 1 | 144 | Runtime | P1 Time MA = 6 min |
| 43 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 43 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 43 | 4 | 717 | Filling AT1 Level | P1 Valve AT1 = 1 (cold water); P2 Stirrer AT1 = 1; P3 Level AT1 = 50 %; P4 Temperature AT1 = 40 °C; P5 Dissolving time AT1 = 1 min |
| 43 | 6 | 720 | Fill Level ST | P1 Valve ST = 0; P2 Stirrer ST = 0; P3 Temperature ST = 0 °C; P4 Level ST = 1100 L; P5 Dissolving Time ST = 0 min |
| 44 | 1 | 71 | Drain Percent | P1 Level MA. Percent = 0 %; P2 Drain = 1 (drain 1); P3 Remain Time = 1 min |
| 44 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 44 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 45 | 1 | 716 | ST -> Machine | P1 Check prep. number = 0; P2 Fill quantity MC = 1900 L |
| 45 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 45 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 46 | 1 | 144 | Runtime | P1 Time MA = 2 min |
| 46 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 46 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 46 | 4 | 717 | Filling AT1 Level | P1 Valve AT1 = 1 (cold water); P2 Stirrer AT1 = 1; P3 Level AT1 = 40 %; P4 Temperature AT1 = 0 °C; P5 Dissolving time AT1 = 3 min |
| 47 | Komentar | — | — | MASUK SABUN |
| 47 | 1 | 237 | Inject AT1 | P1 Check prep. number = 0; P2 Temperature MA = 70 °C; P3 Gradient MA = 0 °C/min; P4 Clean cycl AT1->MA = 1 |
| 47 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 47 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 48 | Komentar | — | — | TW SABUN |
| 48 | 1 | 141 | Temperature Control | P1 Temperature MA = 85 °C; P2 Gradient MA = 0 °C/min; P3 Time MA = 15 min |
| 48 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 48 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 48 | 6 | 720 | Fill Level ST | P1 Valve ST = 0; P2 Stirrer ST = 1; P3 Temperature ST = 0 °C; P4 Level ST = 1100 L; P5 Dissolving Time ST = 0 min |
| 49 | 1 | 747 | Rinsing / Cooling | P1 Gradient MA = 0 °C/min; P2 Temperature MA = 65 °C |
| 49 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 49 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 50 | 1 | 71 | Drain Percent | P1 Level MA. Percent = 0 %; P2 Drain = 1 (drain 1); P3 Remain Time = 1 min |
| 50 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 50 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 51 | 1 | 716 | ST -> Machine | P1 Check prep. number = 0; P2 Fill quantity MC = 1600 L |
| 51 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 51 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 52 | 1 | 144 | Runtime | P1 Time MA = 6 min |
| 52 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 52 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 52 | 6 | 720 | Fill Level ST | P1 Valve ST = 0; P2 Stirrer ST = 0; P3 Temperature ST = 0 °C; P4 Level ST = 1100 L; P5 Dissolving Time ST = 0 min |
| 53 | 1 | 71 | Drain Percent | P1 Level MA. Percent = 0 %; P2 Drain = 1 (drain 1); P3 Remain Time = 1 min |
| 53 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 53 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 54 | 1 | 716 | ST -> Machine | P1 Check prep. number = 0; P2 Fill quantity MC = 1500 L |
| 54 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 54 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 55 | 1 | 144 | Runtime | P1 Time MA = 3 min |
| 55 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 55 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 56 | 1 | 122 | Unload | P1 Alert Time operator = 15 min |
| 56 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 56 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 56 | 6 | 720 | Fill Level ST | P1 Valve ST = 1 (cold water); P2 Stirrer ST = 0; P3 Temperature ST = 0 °C; P4 Level ST = 1200 L; P5 Dissolving Time ST = 0 min |
| 57 | 1 | 71 | Drain Percent | P1 Level MA. Percent = 0 %; P2 Drain = 1 (drain 1); P3 Remain Time = 2 min |
| 57 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 57 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |
| 58 | 1 | 2 | Program End | Tidak memiliki parameter proses |
| 58 | 2 | 404 | Dye Liquor Pump | P1 Set value variojet = 40 %; P2 Speed pump = 90 % |
| 58 | 3 | 712 | Material Flow | P1 Restarts = 0 (Off); P2 Winch speed = 250 m/min |

## Bukti dan batas

- Seluruh 3.519 record data yang direkonstruksi memiliki panjang 290 byte, dengan key unik; semua 4.463 fragmen data tercakup tepat sekali.
- 105 definisi fungsi dan 105 definisi parameter berhasil dibaca. Record text choice turut dibaca untuk nilai pilihan.
- Decoder merangkai fragment pointer dan mendekompresi run literal/repeat sesuai disassembly DLL HMI lokal.
- Seluruh fungsi yang digunakan PRG memiliki definisi lokal dan seluruh referensi parameternya ditemukan.
- Empat record fungsi 718 pada langkah 6, 18, 23, 25 memiliki P6=1 walaupun CNF lokal hanya mendefinisikan lima parameter. Nilai dipertahankan dan ditandai tanpa definisi.
- display_position adalah posisi penyajian CNF; tidak dipakai mengganti urutan nilai parameter dalam PRG.
- factor/offset/scaling disimpan sebagai metadata. Angka PRG ditampilkan dengan satuan definisinya, tidak dikalikan ulang menjadi nilai register.
- Gradient nol, parameter check bernilai nol dan acknowledgement tidak diberi arti perilaku yang belum dibuktikan.
- Mapping alamat register, wiring fisik dan eksekusi langsung PLC belum diverifikasi.

SHA-256 PRG: `5dfc4765f3d73d83ba24ff38011709b4c9b57997cca4ba98dc7bde0b053dc4d8`
SHA-256 CNF: `2936ceff7a238bfff4b9512ca602d9cc85f132086d279674311432f424bd9f57`