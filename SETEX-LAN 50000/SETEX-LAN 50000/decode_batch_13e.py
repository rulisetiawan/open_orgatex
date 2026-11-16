"""Offline decoder of observed 154-byte 13E batch records; never writes source."""
import hashlib
import json
import struct
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, r'C:\Users\surface\Documents\ORGATEX_SETEX\PRG_Studio')
from cnf_decode import CNFReader

ROOT = Path(r'C:\Users\surface\Documents\ORGATEX_SETEX\13E\SC777CE')
OUT = Path(__file__).resolve().parent / 'decoded_13E'


def decode(path):
    reader = CNFReader(path)
    found, skipped = {}, 0
    for key in reader.fragments:
        try:
            packed, trace = reader.chain(*key)
            raw, _ = reader.decompress(packed)
            if len(raw) != 154:
                skipped += 1
                continue
            seq, event = struct.unpack_from('<HH', raw)
            y, mo, day, hour, minute, second = raw[4:10]
            stamp = datetime(1900+y, mo, day, hour, minute, second).isoformat()
            record = dict(sequence=seq, event=event, timestamp=stamp, raw_hex=raw.hex(),
                          fragments=trace)
            if event == 261:
                subtype = struct.unpack_from('<H', raw, 10)[0]
                record.update(subtype=subtype, batch=raw[12:20].split(b'\0')[0].decode('ascii'),
                              program=struct.unpack_from('<H', raw, 20)[0],
                              step=struct.unpack_from('<H', raw, 22)[0],
                              line=raw[24], function=struct.unpack_from('<H', raw, 25)[0],
                              parameter_pairs=[list(struct.unpack_from('<ff', raw, 30+10*i)) for i in range(6)])
            if seq in found and found[seq]['raw_hex'] != record['raw_hex']:
                raise RuntimeError('Conflicting record sequence')
            found[seq] = record
        except (ValueError, struct.error, UnicodeError):
            skipped += 1
    return dict(source=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                decoded_records=len(found), skipped_fragments=skipped,
                sequence_contiguous=sorted(found)==list(range(1, len(found)+1)),
                records=[found[i] for i in sorted(found)])


def main():
    OUT.mkdir(exist_ok=True)
    result = decode(ROOT / 'BATCH/062900/PR062900.LOG')
    # Cross-check against operator-reported changes and subsequent TCP readback.
    expected = {15: (713, 1, 3000.0), 20: (713, 1, 4000.0),
                31: (141, 0, 41.0), 54: (71, 2, 3.0)}
    indexed = {r['sequence']: r for r in result['records']}
    for seq, (fid, slot, value) in expected.items():
        r = indexed[seq]
        assert r['function'] == fid and r['parameter_pairs'][slot] == [value, value], (seq, r)
    assert result['sequence_contiguous'] and result['decoded_records'] == 75
    (OUT/'batch_062900.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    names = {713: 'Fill Level', 141: 'Temperature Control', 71: 'Drain Percent'}
    lines = ['# Temuan backup 13E yang diperbarui', '',
             'Log batch 062900 berhasil direkonstruksi dari fragment Btrieve dan RLE.',
             f"{result['decoded_records']} record berukuran 154 byte; urutan lengkap: {result['sequence_contiguous']}.",
             f"{result['skipped_fragments']} fragment tidak didekode sebagai record mandiri (termasuk kemungkinan lanjutan).", '',
             '## Perubahan fungsi pada catatan batch', '',
             'Angka subtype 6 muncul pada waktu perubahan yang Anda laporkan melalui HMI.',
             'Makna enum resmi belum ditemukan; pelabelan sebagai perubahan adalah inferensi dari korelasi log.', '',
             '| Waktu mesin | Step | Fungsi | P1 | P2 | P3 |', '| --- | --- | --- | --- | --- | --- |']
    changes = []
    for r in result['records']:
        if r['event']==261 and r['subtype']==6:
            values=[pair[0] for pair in r['parameter_pairs']]
            changes.append(dict(time=r['timestamp'], step=r['step'], function=r['function'], values=values))
            lines.append(f"| {r['timestamp']} | {r['step']} | {r['function']} {names.get(r['function'],'')} | {values[0]:g} | {values[1]:g} | {values[2]:g} |")
    lines += ['', '## Program tersimpan TESTPR', '',
              'Programs/M_0005.PRG dan BATCH/062900/M_0005.PRG sama-sama berisi:',
              '- Step 2: fungsi 713, P1=1, P2=8000 L.',
              '- Step 3: fungsi 141, P1=45 °C, P2=1 °C/min, P3=2 min.',
              '- Step 4: fungsi 71, P1=0%, P2=1, P3=2 min.', '',
              'Catatan batch merekam perubahan yang cocok dengan pembacaan Python setelahnya.',
              'Ini menguatkan pemisahan nilai runtime dan resep, bukan bukti bahwa pembacaan 4000 L salah.', '',
              '## Batas bukti', '',
              'Log batch adalah hasil pencatatan aplikasi, bukan capture paket wire SV_CHANGE.',
              'Belum membuktikan apakah perubahan menggunakan service 106/41 atau 137/41,',
              'dan belum menyelesaikan arti flag perintah. Tidak ada pengiriman ke mesin.', '',
              'Format record/field diinterpretasikan dari struktur lokal dan korelasi tanggal,',
              'ID fungsi, nilai PRG, serta nilai hasil baca. Raw bytes dan lokasi fragment disimpan di JSON.']
    (OUT/'TEMUAN_UPDATE_13E.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
    print(json.dumps(changes,indent=2))


if __name__=='__main__':
    main()
