"""Offline CRC-checked inventory of user's timestamped ARCNET capture."""
import json
import struct
from collections import Counter
from datetime import datetime
from pathlib import Path

SOURCE = Path(r'C:\Users\surface\Downloads\MANUAL_20261110_135347_216138.log')
OUT = Path(__file__).resolve().parent / 'decoded_arcnet_manual'


def crc16(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc


def unpack(raw):
    if len(raw) < 8 or raw[0] != 1 or raw[2] != raw[3]:
        raise ValueError('Invalid ARCNET header')
    long = raw[4] == 0
    size = 511-raw[5] if long else 255-raw[4]
    offset = 7 if long else 6
    if len(raw) != size + (9 if long else 8):
        raise ValueError('Frame size mismatch')
    if crc16(raw[:-2]) != int.from_bytes(raw[-2:], 'little'):
        raise ValueError('CRC mismatch')
    info = raw[offset:-2]
    if len(info) < 6:
        raise ValueError('SECOM info shorter than 6 bytes')
    declared = int.from_bytes(info[4:6], 'little')
    if len(info)-6 != declared:
        raise ValueError('SECOM payload size mismatch')
    return raw[1], raw[2], info


def main():
    OUT.mkdir(exist_ok=True)
    frames, events, errors, statuses = [], [], [], []
    counts = Counter()
    for number, line in enumerate(SOURCE.read_text().splitlines(), 1):
        parts = line.split(',')
        if len(parts) >= 5 and parts[2] == 'S':
            statuses.append(dict(time=parts[1], **{k: int(v) for part in parts[4:]
                             if '=' in part for k, v in [part.split('=', 1)] if v.isdigit()}))
        if len(parts) != 5 or parts[2] != 'P':
            continue
        try:
            raw = bytes.fromhex(parts[4])
            src, dst, info = unpack(raw)
            svc, obj = info[1], int.from_bytes(info[2:4], 'little')
            record = dict(line_number=number, time=parts[1], src=src, dst=dst,
                          message_type=info[0], service=svc, object=obj,
                          payload_length=len(info)-6, payload_hex=info[6:].hex(' '))
            counts[(src, dst, svc, obj)] += 1
            frames.append(record)
            if svc in (102, 103, 106, 109, 110, 129, 137, 2, 12):
                record = dict(record, frame_hex=raw.hex(' '))
                if src == 1 and svc == 102 and obj == 1006 and len(info)-6 == 64:
                    data = info[6:]
                    record['function_payload_first_byte'] = data[0]
                    record['function_id'] = int.from_bytes(data[1:3], 'little')
                    record['parameters'] = [dict(slot=i+1, raw=struct.unpack_from('<H', data, 3+8*i)[0],
                           value=struct.unpack_from('<f', data, 5+8*i)[0],
                           parameter_id=struct.unpack_from('<H', data, 9+8*i)[0]) for i in range(6)]
                events.append(record)
        except (ValueError, IndexError, struct.error) as exc:
            errors.append(dict(line_number=number, error=str(exc)))
    result = dict(source=str(SOURCE), packets=len(frames), errors=errors,
                  begin=frames[0]['time'], end=frames[-1]['time'],
                  counts=[dict(src=k[0],dst=k[1],service=k[2],object=k[3],count=v) for k,v in counts.items()],
                  command_events=events,
                  counter_deltas={k: statuses[-1].get(k,0)-statuses[0].get(k,0)
                    for k in ('CRC_OK','CRC_FAIL','USB_DROP','Q_DROP','BQ_DROP')} if len(statuses)>1 else {})
    (OUT/'analysis.json').write_text(json.dumps(result, indent=2),encoding='utf-8')
    names={102:'SV_START',109:'SV_SET_MANUAL',110:'SV_RESET_MANUAL'}
    lines=['# Hasil capture ARCNET MANUAL', '',
           f"Rentang: {result['begin']} sampai {result['end']}.",
           f"Paket lolos pemeriksaan header, ukuran, CRC16 dan panjang payload: {len(frames)}. Ditolak: {len(errors)}.", '',
           '## Transaksi perintah', '', '| Waktu | Arah node | Service | Object | Data penting |',
           '| --- | --- | --- | --- | --- |']
    for r in events:
        detail = r['payload_hex'] if r['payload_length'] <= 6 else f"payload {r['payload_length']} byte"
        if 'parameters' in r:
            detail=f"Fungsi {r['function_id']}; " + '; '.join(f"P{p['slot']} ID {p['parameter_id']} = {p['value']:g} (raw {p['raw']})" for p in r['parameters'] if p['parameter_id'])
        lines.append(f"| {r['time']} | {r['src']} → {r['dst']} | {r['service']} {names.get(r['service'],'')} | {r['object']} | {detail} |")
    lines += ['', '## Batas interpretasi', '',
              'Nama layanan mengikuti Commands.csv SETEX; objek 1004 PLC_PROGRAM, 1005 PLC_STEP, 1006 PLC_FUNCTION.',
              'Rangkaian 109/1004, 102/1006, 110/1004 menunjukkan jalur manual ke PLC.',
              'ACK bertipe 2 dengan payload kosong berarti respons diterima; efek fisik tetap perlu dicocokkan.',
              'Belum dapat dipastikan rangkaian ini berasal dari tombol Intervent saat RUN atau operasi manual terpisah.',
              'Jawaban pengguna "betul" pada pertanyaan pilihan dua mode belum membedakan keduanya.',
              'Tidak ada service 106/137 pada frame yang terekam. Absennya di capture ARCNET tidak membuktikan',
              'ketiadaan layanan internal tersebut: Controller dapat menerjemahkannya ke operasi PLC lain.',
              'Paket ARCNET ini tidak boleh langsung direplay ke TCP port 50000; lapisan header/routing berbeda.',
              'Tidak ada pengiriman, perubahan mode, atau perubahan aplikasi PLC dilakukan oleh analyzer ini.', '',
              '## Counter selama rentang log', '', '```json',json.dumps(result['counter_deltas'],indent=2),'```',
              'Counter CRC/queue adalah statistik alat, bukan jaminan seluruh transaksi berhasil tertangkap.',
              'BQ_DROP perlu ditafsirkan menurut firmware sniffer; belum otomatis berarti paket PLC hilang.']
    (OUT/'HASIL_ARCNET_MANUAL.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('command_events','counts')},indent=2))
    for r in events:
        print(r['time'],r['src'],r['dst'],r['service'],r['object'],
              ([(p['parameter_id'],p['value'],p['raw']) for p in r['parameters'] if p['parameter_id']]
               if 'parameters' in r else r['payload_hex']))


if __name__=='__main__':
    main()
