from pathlib import Path
from collections import Counter
import struct, json, hashlib, html, re, sys, math

ROOT=Path(r'D:\File HMI')
OUT=ROOT/'Analisis'
sys.path.insert(0,str(OUT/'_deps'))
import xlrd

source=ROOT/'Storage/SC777CE/Programs/M_0182.PRG'
binary=source.read_bytes()
before=hashlib.sha256(binary).hexdigest()
cnf_path=ROOT/'Storage/SC777CE/Config/TYPECONF.CNF'
cnf=cnf_path.read_bytes()
sheet=xlrd.open_workbook(str(ROOT/'Network/F/function-label.xls')).sheet_by_index(0)
mapping={}
for i in range(sheet.nrows):
    num=sheet.cell_value(i,1)
    if isinstance(num,(int,float)) and num>0:
        mapping.setdefault(int(num),[]).append({'row':i+1,'group':sheet.cell_value(i,0),'name':sheet.cell_value(i,2)})

def parse(data):
    assert data[:4]==bytes.fromhex('508fc2f5')
    assert len(data)>=384 and (len(data)-384)%65==0
    count=struct.unpack_from('<H',data,33)[0]
    records=[]
    for index,off in enumerate(range(384,len(data),65)):
        raw=data[off:off+65]
        step=struct.unpack_from('<H',raw)[0];slot=raw[2]
        assert 1<=step<=count
        rec={'index':index,'offset':off,'step':step,'slot':slot,'raw_hex':raw.hex()}
        if slot==0:
            rec.update(kind='comment',text=raw[3:].split(b'\0',1)[0].decode('cp1252'))
        else:
            fn=struct.unpack_from('<H',raw,4)[0]
            rec.update(kind='function',function_id=fn,byte3=raw[3],flag_byte6=raw[6],tail_hex=raw[61:65].hex(),parameters=[])
            for j in range(6):
                meta,value=struct.unpack_from('<Hf',raw,7+6*j)
                assert math.isfinite(value)
                rec['parameters'].append({'position':j+1,'metadata_u16':meta,'value':value,'float_hex':raw[9+6*j:13+6*j].hex()})
            rec['additional_fields']=dict(zip(['protect_time','set_time','operator_txt','modul_no','loop_count','label_type','start_act_value','hold_time','reserved','treatment','treatment_step'],struct.unpack_from('<5HBfHBHH',raw,43)))
            rec['name']=Counter(x['name'] for x in mapping.get(fn,[])).most_common(1)[0][0] if fn in mapping else 'UNKNOWN'
        records.append(rec)
    assert set(r['step'] for r in records)==set(range(1,count+1))
    assert [r['step'] for r in records]==sorted(r['step'] for r in records)
    assert all(sum(r['step']==s and r['slot']==1 for r in records)==1 for s in range(1,count+1))
    return count,records

count,records=parse(binary)
function_ids=sorted({r['function_id'] for r in records if r['kind']=='function'})
labels={}
for fid in function_ids:
    assert fid in mapping
    name=Counter(x['name'] for x in mapping[fid]).most_common(1)[0][0]
    pattern=b'\x03\x00\x00\x00'+struct.pack('<H',fid)
    hits=[]
    for m in re.finditer(re.escape(pattern),cnf):
        window=cnf[m.start()+6:m.start()+100]
        if name.encode('cp1252')[:15] in window:
            hits.append({'offset':m.start(),'window_hex':window.hex()})
    assert hits,(fid,name)
    labels[fid]={'name':name,'xls_matches':mapping[fid],'cnf_matches':hits,'note':'Label mayoritas XLS dicocokkan ke prefix nama pada record TYPECONF lokal. Nama dapat berbeda antargrup.'}

# Validate structural interpretation against all 37 sibling program files.
checks=[]
for p in sorted(source.parent.glob('*.PRG')):
    data=p.read_bytes();n,rr=parse(data)
    checks.append({'file':p.name,'step_count':n,'record_count':len(rr),'all_steps_present':True})

# Rebuild each function record from independently decoded fields and preserved opaque bytes.
rebuilt=bytearray(binary[:384])
for r in records:
    raw=bytes.fromhex(r['raw_hex'])
    if r['kind']=='comment':
        rebuilt.extend(raw);continue
    rr=bytearray(65)
    struct.pack_into('<H',rr,0,r['step']);rr[2]=r['slot'];rr[3]=r['byte3']
    struct.pack_into('<H',rr,4,r['function_id']);rr[6]=r['flag_byte6']
    for p in r['parameters']:
        struct.pack_into('<Hf',rr,7+(p['position']-1)*6,p['metadata_u16'],p['value'])
    rr[43:65]=struct.pack('<5HBfHBHH',*r['additional_fields'].values());assert rr==raw
    rebuilt.extend(rr)
assert bytes(rebuilt)==binary
assert len(records)==200 and count==58
assert sum(r['kind']=='function' for r in records)==191
assert sum(r['kind']=='comment' for r in records)==9
assert all(r['byte3']==0 and r['tail_hex']=='00000000' for r in records if r['kind']=='function')
assert all(p['metadata_u16']==0 for r in records if r['kind']=='function' for p in r['parameters'])
assert hashlib.sha256(source.read_bytes()).hexdigest()==before

data={'source':str(source),'sha256':before,'program_id':struct.unpack_from('<H',binary,8)[0],
      'title':binary[10:33].split(b'\0',1)[0].decode('cp1252'),'step_count':count,
      'header_hex':binary[:384].hex(),'records':records,'function_labels':labels,
      'verification':{'sibling_programs':checks,'byte_roundtrip':True,'source_unchanged':True},
      'limitations':['Layout inferred from local files, not an official vendor format specification.',
      'Six parameter slots per T_PRG_ELEMENT/T_PRG_PARA decoded; parameter names, units, enum meanings and active slot counts are not established.',
      'Byte 3 = label, byte 6 = ack per reference structure. Parameter metadata comprises attribute and formula bytes. Fields after six parameters are separate metadata, not P7-P9; behavior remains unverified.',
      'No execution, PLC connection, or Orgatex editor comparison was performed.']}
(OUT/'M_0182_decoded.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

id_names={1:'Mulai program',2:'Selesai program',71:'Drain / pengosongan',122:'Unload / keluarkan kain',126:'Pemeriksaan',141:'Kontrol temperatur',144:'Waktu sirkulasi / runtime',237:'Injeksi AT1',238:'Injeksi AT2',261:'Load / masukkan kain',404:'Pompa larutan dyeing',712:'Aliran kain / material',713:'Pengisian level',716:'Transfer ST ke mesin',717:'Pengisian AT1',718:'Pengisian AT2',720:'Pengisian ST',747:'Pembilasan / pendinginan',938:'Dosing progresif 1',939:'Dosing progresif 2'}
fmt=lambda x:format(x,'.8g')
def params(r):return ', '.join('P'+str(p['position'])+'='+fmt(p['value']) for p in r['parameters'])
def esc(x):return html.escape(str(x))
md=['# Decode M_0182.PRG — '+data['title'],'',
    '**58 langkah, 191 record fungsi, 9 komentar.** Semua 200 record setelah header tercakup. File asli tidak diubah.',
    '', '**Batas:** urutan, ID fungsi, komentar dan nilai float berhasil diekstrak. P1–P6 adalah posisi nilai dalam record, bukan nama parameter yang sudah diverifikasi. Satuan, enum, jumlah parameter aktif, dan logika internal PLC belum dipastikan. Nol bisa berarti nilai nol atau slot tidak digunakan. Hasil ini adalah rekonstruksi statis, belum dibandingkan dengan editor resmi.',
    '', '## Seluruh langkah dan fungsi', '', '| Step | Slot | ID | Fungsi | Nilai tersimpan / komentar |','|---|---|---|---|---|']
cards=[]
for st in range(1,59):
    rr=[r for r in records if r['step']==st];comments=[r['text'] for r in rr if r['kind']=='comment']
    main=next(r for r in rr if r['slot']==1)
    title=id_names[main['function_id']]
    table=[]
    for r in rr:
        if r['kind']=='comment':
            md.append(f'| {st} | Komentar | — | — | {r["text"]} |');continue
        md.append(f'| {st} | {r["slot"]} | {r["function_id"]} | {r["name"]} | {params(r)} |')
        cells=''.join('<td>'+esc(fmt(p['value']))+'</td>' for p in r['parameters'])
        table.append(f'<tr><td>{r["slot"]}</td><td><b>{esc(r["name"])}</b><small>ID {r["function_id"]} · offset 0x{r["offset"]:04X} · flag {r["flag_byte6"]}</small></td>{cells}</tr>')
    annotation=(' · '+ ' / '.join(comments)) if comments else ''
    cards.append(f'<section class="step" id="step-{st}"><h2><span>{st:02d}</span> {esc(title)} <em>{esc(annotation)}</em></h2><div class="scroll"><table><thead><tr><th>Slot</th><th>Fungsi</th>'+''.join(f'<th>P{i}</th>' for i in range(1,7))+'</tr></thead><tbody>'+''.join(table)+'</tbody></table></div></section>')
md+=['','## Bukti struktur dan pengujian','',
    '- Header 384 byte; 200 record × 65 byte = 13.000 byte; total 13.384 byte.',
    '- Offset 8: ID program 182. Offset 10: judul PRG 47 DYLON. Nomor dalam judul berbeda dari ID berkas.',
    '- Offset 33: jumlah langkah 58; record mencakup langkah 1–58 tanpa celah.',
    '- Record: uint16 step di +0; slot byte di +2; untuk record komentar (slot 0), teks mulai +3.',
    '- Record fungsi: byte +3 label; uint16 ID fungsi +4; byte +6 ack menurut struktur referensi. Arti nilai ack belum diuji.',
    '- Koreksi berdasarkan T_PRG_ELEMENT/T_PRG_PARA: enam parameter mulai +7, masing-masing attribute byte, formula byte, float32. Byte +43..64 adalah protect_time, set_time, operator_txt, modul_no, loop_count, label_type, start_act_value, hold_time, reserved, treatment, treatment_step; bukan P7-P9.',
    '- Semua attribute/formula serta empat byte terakhir pada file target bernilai nol; flag bernilai 0, 1 atau 6. Flag tidak diperlakukan sebagai perintah tanpa bukti tambahan.',
    '- Pola header/record dan urutan langkah lolos pemeriksaan pada 37 file Programs. Ini penguat struktur, bukan validasi seluruh semantik format.',
    '- Penyusunan ulang record fungsi dari field hasil parse menghasilkan byte identik; header dan komentar dipertahankan. Semua byte sumber tercakup.',
    '- 20 ID fungsi ditemukan dalam function-label.xls; prefix label dicocokkan dengan record TYPECONF.CNF lokal.',
    '- Slot 1 memuat fungsi utama; slot 2/3 berulang untuk pump/material flow, slot 4/5/6 berisi fungsi tangki. Pengelompokan mengikuti struktur tersimpan, bukan 191 langkah berurutan.',
    '', '## Sumber','',f'- PRG: `{source}`',f'- SHA-256: `{before}`',f'- Konfigurasi: `{cnf_path}`',f'- Label: `{ROOT / "Network/F/function-label.xls"}`',
    '- Manual ProgramEditor, halaman PDF 11–13: satu langkah memuat fungsi utama, fungsi resource paralel dan komentar. Versi manual bukan bukti spesifikasi biner ini.',
    '', 'Data seluruh field, hex setiap record, kandidat label per grup, dan hasil pemeriksaan disimpan di M_0182_decoded.json.']
(OUT/'M_0182_seluruh_step.md').write_text('\n'.join(md),encoding='utf-8')
page='''<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PRG 47 DYLON — 58 langkah</title><style>
*{box-sizing:border-box}body{margin:0;background:#eef2f5;color:#183044;font:15px system-ui}main{max-width:1320px;margin:auto;padding:28px}header{background:#173b50;color:white;padding:30px;border-radius:14px}h1{margin:8px 0;font-size:32px}header p{max-width:950px;line-height:1.6}.badge{display:inline-block;padding:7px 12px;background:#28566f;border-radius:5px;margin:4px 5px 4px 0}.notice{background:#fff6db;border-left:4px solid #c58b12;padding:18px;line-height:1.6;margin:18px 0}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:20px 0}input{padding:12px;min-width:310px;border:1px solid #acbdc8;border-radius:7px}a{color:#116680}button{padding:10px;border:1px solid #bac8d2;background:white;border-radius:6px;cursor:pointer}.step{background:white;border:1px solid #d9e1e7;border-radius:10px;margin:16px 0;overflow:hidden}.step h2{font-size:18px;margin:0;padding:16px;background:#f8fafc}.step h2 span{background:#126e76;color:white;padding:5px 9px;border-radius:5px;margin-right:10px}em{font-style:normal;color:#855c16}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px;border-top:1px solid #e4e9ed;text-align:left;white-space:nowrap}th{color:#566a7b;font-size:12px}small{display:block;font-size:11px;color:#6c7f8e;margin-top:4px}footer{line-height:1.6;color:#526677}details{margin:20px 0;padding:16px;background:white}code{font-size:12px;word-break:break-all}@media print{.toolbar{display:none}body{background:white}main{padding:0}.step{break-inside:avoid}header{background:white;color:black}.badge{background:#ddd}.notice{font-size:11px}}</style><main>
<header><div>DECODE STATIS · SECOM / ORGATEX</div><h1>PRG 47 DYLON</h1><p>ID berkas/program: 182 · M_0182.PRG · 13.384 byte</p><span class="badge">58 langkah</span><span class="badge">191 record fungsi</span><span class="badge">9 komentar</span><p>Seluruh urutan yang tersimpan ditampilkan di bawah, termasuk fungsi tambahan pada setiap langkah. Label fungsi berasal dari ekspor Orgatex dan dicocokkan dengan konfigurasi HMI lokal. Struktur diperbarui: enam slot parameter; P7–P9 pada versi awal bukan parameter proses.</p></header>
<div class="notice"><b>Cara membaca:</b> P1–P6 adalah nilai numerik tersimpan menurut posisinya. Nama parameter, satuan, arti pilihan angka, dan slot mana yang aktif belum dipastikan. Nilai 0 dapat berarti nol atau slot yang tidak digunakan. Tabel ini belum merupakan hasil verifikasi di editor Orgatex atau mesin. Slot menunjukkan fungsi dalam langkah yang sama, bukan langkah proses berikutnya.</div>
<div class="toolbar"><input id="search" aria-label="Cari langkah" placeholder="Cari komentar, fungsi, atau nomor step…"><button onclick="window.print()">Cetak / simpan PDF</button><a href="M_0182_seluruh_step.md">Laporan teks lengkap</a><a href="M_0182_decoded.json">Data decode + bukti</a><span id="count">58 langkah ditampilkan</span></div>
CARDS
<details><summary>Bukti decoding dan batas interpretasi</summary><p>Header 384 byte + 200 record × 65 byte = 13.384 byte. Nilai jumlah langkah dalam header cocok dengan semua nomor 1–58. Struktur yang sama diperiksa pada 37 program. Record fungsi berhasil disusun ulang byte-per-byte. Seluruh 20 ID fungsi memiliki label yang dicocokkan ke konfigurasi lokal.</p><p>Koreksi: hanya P1–P6 adalah slot parameter menurut struktur T_PRG_ELEMENT. Area yang sebelumnya diberi label P7–P9 adalah metadata lain. Arti nama/satuan parameter dan perilaku ack belum diverifikasi. Tidak ada kontrol PLC atau executable sumber yang dijalankan.</p><p>SHA-256 sumber: <code>HASH</code></p></details><footer>Analisis 28 Oktober 2026. File PRG asli tetap utuh. Semua 200 record tersedia dalam JSON, termasuk offset dan hex.</footer></main><script>const input=document.getElementById('search');input.addEventListener('input',()=>{let n=0;const q=input.value.trim().toLowerCase();for(const section of document.querySelectorAll('.step')){const matched=!q||section.textContent.toLowerCase().includes(q)||section.id==='step-'+q;section.hidden=!matched;if(matched)n++}document.getElementById('count').textContent=n+' langkah ditampilkan'});</script></html>'''.replace('CARDS',''.join(cards)).replace('HASH',before)
(OUT/'M_0182_seluruh_step.html').write_text(page,encoding='utf-8')
print(json.dumps({'steps':count,'function_records':191,'comments':9,'function_ids':function_ids,'sibling_files_verified':len(checks),'roundtrip':True,'source_unchanged':True,'html':str(OUT/'M_0182_seluruh_step.html')},indent=2))
