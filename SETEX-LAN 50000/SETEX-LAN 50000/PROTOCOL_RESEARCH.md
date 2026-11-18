# Penelusuran jalur Controller — 10 November 2026

Target: baca register melalui layanan Controller TCP, tanpa remote keyboard,
remote mouse, atau pemindahan menu HMI. Ini belum implementasi LIVE.

## Bukti dari binary asli (pemeriksaan statis, tidak menjalankan DLL)

`RemoteClient/RemoteClient/RCClient.ini` mencantumkan Controller_Port=50000
dan RCServer_Port=50010. Konfigurasi ini bukan bukti port aktif pada mesin.

Pada SecomPC_BGUtils_1.dll:

- BGU_TranslateMessageSC737toTCP pada RVA 0x5d60 menulis uint16 2 di offset 0,
  membaca uint16 pada SC737_T_MSG+0x12, menambahkan 0x10, dan menyimpan
  hasil di TCPMessage+2. Kemudian menyalin 502 byte dari SC737_T_MSG+4
  ke TCPMessage+4. Ini bukan fungsi yang menyisipkan header 74 byte.
- BGU_TranslateMessageTCPtoSC737 pada RVA 0x5dc0 melakukan salinan balik
  502 byte dan menulis nol pada empat byte pertama struktur internal.
- Implementasi CE di 6A/sc777ce/SecomCE_BGUtils_2d.dll memiliki operasi
  yang sama pada RVA 0x333c dan 0x33a6.
- CComServiceClient::SendMessageA pada RVA 0xb2a0 memakai jalur lain:
  menyalin header 74 byte, menulis panjang data uint32 pada offset header
  0x10, dan mengirim header+data langsung melalui CUniNetwork::SendData.
  Responsnya juga dimulai dengan header 74 byte. Tidak terlihat pemanggilan
  pembungkus SC737 di fungsi ini. Jangan gabungkan kedua format tanpa
  menelusuri pemilihan port dan penerima pada server.
- Fungsi tersebut memeriksa ID pada offset 0, jenis respons pada offset 4
  (2 untuk data, 3 untuk error), panjang pada offset 0x10, dan kode error
  pada offset 0x14. Ini hanya berlaku untuk jalur fungsi tersebut.

Pada 6A/sc777ce/SecomCE_TCP_2d.dll:

- TCP_StartServer pada RVA 0x33ff menerima nomor port dari pemanggil lalu
  meneruskannya ke fungsi internal pada RVA 0x23d9. Belum membuktikan bentuk
  pesan layanan baca IW maupun bahwa jalur 74 byte digunakan di port 50000.

## Yang masih harus ditemukan

1. Loop penerima TCP Controller dan aturan panjang frame di jaringan.
2. Field header SC737, routing/node, identitas transaksi, dan handshake.
3. Handler SV_READ + OBJID_PLC_INFO_WORTE: payload indeks dan respons/error.
4. Perbedaan alamat satuan, block, dan list; batas panjang tiap transaksi.
5. Validasi dengan kontroler yang sama, satu alamat dahulu, lalu cyclic.

Tidak ada paket aplikasi dikirim ke mesin dalam pemeriksaan ini.
Tidak ada jaminan kompatibilitas LIVE atau jaminan nol dampak HMI.

## Mengulangi pemeriksaan

`inspect_dll.py` membaca export PE dan menampilkan disassembly x86 statis.
Dependensi riset pefile dan capstone disimpan lokal dalam tools_deps;
tidak dibutuhkan oleh antarmuka setex_reader.py.

Contoh: `python inspect_dll.py PATH_DLL TranslateMessage`
