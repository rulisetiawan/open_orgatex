"""Read-only export of 13E configuration. No network or device writes."""
import hashlib
import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path

REFERENCE = Path(r'C:\Users\surface\Documents\ORGATEX_SETEX\PRG_Studio')
sys.path.insert(0, str(REFERENCE))
from cnf_decode import CNFReader, function, parameter

SOURCE = Path(r'C:\Users\surface\Documents\ORGATEX_SETEX\13E\SC777CE\Config')
OUTPUT = Path(__file__).resolve().parent / 'decoded_13E'


def decode_catalog(path):
    reader = CNFReader(path)
    found = {2: {}, 3: {}}
    failures = 0
    for key in reader.fragments:
        try:
            packed, trace = reader.chain(*key)
            raw, runs = reader.decompress(packed)
            if len(raw) != 290:
                continue
            kind, typ, index = struct.unpack_from('<HHH', raw)
            if kind not in found or typ != 0:
                continue
            decoded = parameter(raw) if kind == 2 else function(raw)
            item = dict(data=decoded, raw_hex=raw.hex(), source_fragments=trace,
                        packed_bytes=len(packed), decoded_bytes=len(raw))
            found[kind].setdefault(index, {})[raw.hex()] = item
        except (ValueError, struct.error):
            failures += 1
    return found, failures


def main():
    OUTPUT.mkdir(exist_ok=True)
    found, failures = decode_catalog(SOURCE / 'TYPECONF.CNF')
    params = {i: next(iter(items.values())) for i, items in found[2].items() if len(items) == 1}
    functions = {i: next(iter(items.values())) for i, items in found[3].items() if len(items) == 1}
    awl = (SOURCE / 'CP14.AWL').read_bytes()
    strings = [s.decode('ascii') for s in re.findall(rb'[ -~]{8,}', awl)
               if any(x in s.lower() for x in (b'.pro', b'codesys', b'temper'))]
    report = dict(source=str(SOURCE), source_sha256={name: hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()
                   for name in ('TYPECONF.CNF', 'CP14.AWL')},
                  parameters=params, functions=functions,
                  ambiguous={str(k): [i for i, items in values.items() if len(items)>1] for k, values in found.items()},
                  skipped_fragment_decodes=failures,
                  awl=dict(size=len(awl), first_32_bytes=awl[:32].hex(' '), relevant_strings=strings,
                           status='Binary inspected, not a verified instruction/operand disassembly.'))
    (OUTPUT / 'catalog.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    lines = ['# Parameter dan fungsi mesin 13E', '',
             'Sumber: `13E/SC777CE/Config/TYPECONF.CNF`, rekonstruksi fragment dan RLE.',
             'Ini ID definisi parameter/fungsi; belum otomatis merupakan alamat SV_CHANGE.', '',
             f'Ditemukan {len(params)} definisi parameter dan {len(functions)} fungsi unik.', '',
             '## Temperature Control', '']
    for fid, item in sorted(functions.items()):
        f = item['data']
        if 'temperature control' not in f['name'].lower():
            continue
        lines += [f"Fungsi **{fid}: {f['name']}**.", '',
                  '| Slot fungsi | ID definisi | Parameter | Satuan | Batas fungsi | Faktor konfigurasi | Mode skala |',
                  '| --- | --- | --- | --- | --- | --- | --- |']
        for slot, entry in enumerate(f['parameters'], 1):
            p = params.get(entry['definition_id'], {}).get('data', {})
            scale = p.get('scale', {})
            lines.append(f"| P{slot} | {entry['definition_id']} | {p.get('name','?')} | {p.get('unit','?')} | "
                         f"{entry['minimum']:g}–{entry['maximum']:g} | {scale.get('factor','?')} | {scale.get('mode','?')} |")
    lines += ['', '## Semua definisi parameter', '', '| ID definisi | Nama | Satuan |', '| --- | --- | --- |']
    for pid, item in sorted(params.items()):
        p = item['data']
        lines.append(f"| {pid} | {p['name'].replace('|','/')} | {p['unit'].replace('|','/')} |")
    lines += ['', '## Batas decoding AWL', '',
              'CP14.AWL adalah biner; belum berhasil didekode menjadi instruksi PLC dan operand yang tervalidasi.',
              'Jadi laporan ini tidak mengklaim relasi register SET/ACT dari logika AWL.', '',
              '## SV_CHANGE', '',
              'Commands.csv memisahkan 106/6 (fungsi), 106/41 (parameter), dan 137/6 (extended).',
              'ID fungsi, slot P1/P2/P3, ID definisi parameter, dan register SET adalah ruang nomor berbeda.',
              'Payload dan arti field target/konteks harus dicocokkan dengan pemanggil HMI/handler runtime.',
              'Belum ada paket SV_CHANGE yang dikirim oleh alat ini.']
    (OUTPUT / 'PARAMETER_13E.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(dict(parameters=len(params), functions=len(functions),
                         temperature=[f['data'] for f in functions.values() if 'temperature control' in f['data']['name'].lower()],
                         awl=report['awl'], output=str(OUTPUT)), indent=2))


if __name__ == '__main__':
    main()
