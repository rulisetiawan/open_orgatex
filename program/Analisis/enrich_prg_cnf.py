from pathlib import Path
from collections import Counter
import json,struct,hashlib,html,re
from cnf_decode import CNFReader,CNF,ROOT,OUT,function,parameter,txt

reader=CNFReader(CNF)
incoming={f['next'] for f in reader.fragments.values() if f['next'] and f['next'][1]!=255}
allrecords={};covered=set();export=[]
for address in reader.fragments:
    if address in incoming:continue
    packed,trace=reader.chain(*address)
    raw,runs=reader.decompress(packed)
    assert len(raw)==290
    key=struct.unpack_from('<3H',raw)
    assert key not in allrecords,('duplicate',key)
    assert all((t['page'],t['slot']) not in covered for t in trace)
    covered.update((t['page'],t['slot']) for t in trace)
    # Preserve the exact compressed stream, boundaries and decoded record for audit.
    item={'key':key,'raw_hex':raw.hex(),'packed_hex':packed.hex(),'fragments':trace}
    rebuilt=bytearray()
    for repeat,n,hexvalue in runs:
        rebuilt+=struct.pack('<H',n)+bytes.fromhex(hexvalue)
    assert bytes(rebuilt)==packed
    allrecords[key]=item;export.append(item)
assert covered==set(reader.fragments)
assert len(allrecords)==3519
assert sum(k[0]==3 for k in allrecords)==105
assert sum(k[0]==2 for k in allrecords)==105

funcs={k[2]:function(bytes.fromhex(v['raw_hex'])) for k,v in allrecords.items() if k[:2]==(3,0)}
params={k[2]:parameter(bytes.fromhex(v['raw_hex'])) for k,v in allrecords.items() if k[:2]==(2,0)}
texts={}
for key,item in allrecords.items():
    if key[0]!=51:continue
    raw=bytes.fromhex(item['raw_hex']);group,value=struct.unpack_from('<Hf',raw,48)
    assert group==key[1]
    texts.setdefault(group,[]).append({'text':txt(raw[27:48]),'value':value,'key':key})

source=ROOT/'Storage/SC777CE/Programs/M_0182.PRG'
original=source.read_bytes();sha=hashlib.sha256(original).hexdigest()
old=json.loads((OUT/'M_0182_decoded.json').read_text(encoding='utf-8'))
assert old['sha256']==sha
used_funcs=sorted({r['function_id'] for r in old['records'] if r['kind']=='function'})
used_params=set();mapped=0;unmapped=[]
for r in old['records']:
    if r['kind']!='function':continue
    f=funcs[r['function_id']];r['name']=f['name'];r['named_parameters']=[]
    for i,p in enumerate(f['parameters']):
        definition=params[p['definition_id']];v=r['parameters'][i]['value'];used_params.add(definition['id'])
        choices=texts.get(definition['scale2']['text_group'],[]) if definition['scale']['mode']==16 else []
        matches=[t['text'] for t in choices if t['value']==v]
        np={'position':i+1,'definition_id':definition['id'],'name':definition['name'],
            'unit':definition['unit'],'value':v,'choice_text':matches[0] if len(matches)==1 else None,
            'choices':choices,'function_limits':p,'definition':definition,
            'attribute':r['parameters'][i]['metadata_u16']&255,
            'formula':r['parameters'][i]['metadata_u16']>>8}
        r['named_parameters'].append(np);mapped+=1
    r['undefined_nonzero_parameters']=[dict(p,reason='Slot di luar parameter_count CNF lokal') for p in r['parameters'][f['parameter_count']:] if p['value']!=0]
    for p in r['undefined_nonzero_parameters']:
        unmapped.append({'step':r['step'],'slot':r['slot'],'function_id':r['function_id'],**p})
    r['cnf_function']=f

assert next(r for r in old['records'] if r['kind']=='function' and r['step']==35 and r['slot']==1)['named_parameters'][0]['value']==132
assert [p['definition_id'] for p in funcs[141]['parameters']]==[3,4,5]
assert [params[i]['unit'] for i in [3,4,5]]==['°C','°C/min','min']
comparisons=[];legacy=None
for path in sorted((ROOT/'Network').rglob('TYPECONF.CNF')):
    other=CNFReader(path);matches=other.candidates(3,718)
    if len(matches)!=1:continue
    f=function(matches[0]['raw'])
    comparisons.append({'source':str(path),'sha256':hashlib.sha256(other.data).hexdigest(),'function':f})
    if f['parameter_count']==6 and f['parameters'][5]['definition_id']==162:
        pp=other.candidates(2,162);assert len(pp)==1
        pd=parameter(pp[0]['raw']);choices=[]
        inc={x['next'] for x in other.fragments.values() if x['next'] and x['next'][1]!=255}
        for adr in other.fragments:
            if adr in inc:continue
            raw,_=other.decompress(other.chain(*adr)[0]);key=struct.unpack_from('<3H',raw)
            if key[0]==51 and key[1]==pd['scale2']['text_group']:
                group,v=struct.unpack_from('<Hf',raw,48)
                choices.append({'value':v,'text':txt(raw[27:48]),'key':key})
        legacy={'source':str(path),'definition':pd,'choices':choices,
                'interpretation':'Backup group 002 only: P6=1 matches Mixer Type AT2 = Valve. Not defined in current local CNF.'}
assert legacy is not None
for r in old['records']:
    if r['kind']=='function' and r['undefined_nonzero_parameters']:r['legacy_parameter_candidate']=legacy
old['cnf_decode']={'date':'2026-10-29','source':str(CNF),'sha256':hashlib.sha256(reader.data).hexdigest(),
    'decoded_record_count':len(allrecords),'fragment_count':len(reader.fragments),'all_fragments_covered_once':True,
    'unique_keys':True,'record_bytes':290,'function_count':105,'parameter_definition_count':105,
    'program_function_count':len(used_funcs),'program_parameter_definition_count':len(used_params),
    'mapped_parameter_values':mapped,'nonzero_values_without_cnf_definition':unmapped,'functions':{n:funcs[n] for n in used_funcs},
    'parameter_definitions':{n:params[n] for n in sorted(used_params)},
    'function_718_version_comparison':comparisons,'legacy_parameter_candidate':legacy}
old['limitations']=[
    'Function-to-parameter references, names, units and stored values are decoded from local TYPECONF.CNF.',
    'display_position in CNF controls display arrangement; PRG parameter mapping follows definition array order, not that display position.',
    'No live HMI/PLC or vendor editor comparison performed. Register addresses and machine physical behavior remain unverified.',
    'CNF scaling metadata is preserved but not applied again to the engineering values stored in the PRG.',
    'Some zero values may have function-specific behavior; zero gradient is not interpreted as a specific heating/cooling mode.',
    'Text choices are shown only for mode 16 when a unique numeric value matches the configured text group.'
]
(OUT/'M_0182_decoded.json').write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'TYPECONF_records_decoded.json').write_text(json.dumps({'source':str(CNF),'sha256':old['cnf_decode']['sha256'],'records':export},indent=2),encoding='utf-8')
(OUT/'TYPECONF_functions_parameters.json').write_text(json.dumps({'functions':funcs,'parameters':params,'text_choices':texts},ensure_ascii=False,indent=2),encoding='utf-8')

def fmt(n):return format(n,'.8g')
def esc(s):return html.escape(str(s))
def value(p):
    s=fmt(p['value'])+(' '+p['unit'] if p['unit'] else '')
    if p['choice_text']:s+=' ('+p['choice_text']+')'
    return s
md=['# M_0182.PRG — '+old['title'],'','Diperbarui 29 Oktober 2026: nama dan satuan parameter kini diambil dari TYPECONF.CNF lokal.',
    '',f'58 langkah; 191 record fungsi; 9 komentar; {mapped} nilai pada parameter terdefinisi dipetakan; {len(used_funcs)} definisi fungsi dan {len(used_params)} definisi parameter digunakan.',
    '', '## Pemetaan fungsi 141 yang sudah terurai','',
    '| Posisi PRG | ID definisi | Nama | Satuan | Batas dalam fungsi |','|---|---|---|---|---|',
    '| P1 | 3 | Temperature MA | °C | 0–150 |','| P2 | 4 | Gradient MA | °C/min | 0–9,9 |','| P3 | 5 | Time MA | min | 0–180 |',
    '', 'index_min/index_max dapat merujuk batas lain. Nilai batas nol atau indeks nonzero tidak diperlakukan sebagai batas engineering final tanpa pembacaan konfigurasi terkait.',
    '', '## Seluruh langkah dan fungsi','', '| Step | Slot | ID fungsi | Fungsi | Parameter bernama |','|---|---|---|---|---|']
cards=[]
for st in range(1,59):
    records=[r for r in old['records'] if r['step']==st]
    comment=' / '.join(r['text'] for r in records if r['kind']=='comment')
    main=next(r for r in records if r['kind']=='function' and r['slot']==1)
    rows=[]
    for r in records:
        if r['kind']=='comment':
            md.append(f'| {st} | Komentar | — | — | {r["text"]} |');continue
        pp=r['named_parameters']
        desc='; '.join('P'+str(p['position'])+' '+p['name']+' = '+value(p) for p in pp) or 'Tidak memiliki parameter proses'
        if r['undefined_nonzero_parameters']:desc+='; P6=1 [tanpa definisi CNF lokal; backup grup 002: Mixer Type AT2 = Valve]'
        md.append(f'| {st} | {r["slot"]} | {r["function_id"]} | {r["name"]} | {desc} |')
        parameter_cells=''.join('<div class="param"><small>P'+str(p['position'])+' · definisi '+str(p['definition_id'])+'</small><span>'+esc(p['name'])+'</span><b>'+esc(value(p))+'</b></div>' for p in pp) or '<span class="muted">Tidak memiliki parameter proses</span>'
        if r['undefined_nonzero_parameters']:parameter_cells+='<div class="param"><small>P6 · tanpa definisi CNF lokal</small><span>Backup grup 002: Mixer Type AT2</span><b>1 → Valve (backup)</b></div>'
        raw='; '.join('P'+str(p['position'])+'='+fmt(p['value']) for p in r['parameters'])
        rows.append('<tr><td>'+str(r['slot'])+'</td><td><b>'+esc(r['name'])+'</b><small>ID '+str(r['function_id'])+' · offset 0x'+format(r['offset'],'04X')+'</small></td><td><div class="params">'+parameter_cells+'</div><details><summary>Nilai mentah / metadata</summary><p>'+esc(raw)+'</p><p>ack='+str(r['flag_byte6'])+' · '+esc(json.dumps(r['additional_fields']))+'</p></details></td></tr>')
    cards.append('<section class="step" id="step-'+str(st)+'"><h2><span>'+f'{st:02d}'+'</span> '+esc(main['name'])+(' <em>· '+esc(comment)+'</em>' if comment else '')+'</h2><div class="scroll"><table><thead><tr><th>Slot</th><th>Fungsi</th><th>Nilai parameter sesuai CNF</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>')

md+=['','## Bukti dan batas','',
    '- Seluruh 3.519 record data yang direkonstruksi memiliki panjang 290 byte, dengan key unik; semua 4.463 fragmen data tercakup tepat sekali.',
    '- 105 definisi fungsi dan 105 definisi parameter berhasil dibaca. Record text choice turut dibaca untuk nilai pilihan.',
    '- Decoder merangkai fragment pointer dan mendekompresi run literal/repeat sesuai disassembly DLL HMI lokal.',
    '- Seluruh fungsi yang digunakan PRG memiliki definisi lokal dan seluruh referensi parameternya ditemukan.',
    '- Empat record fungsi 718 pada langkah 6, 18, 23, 25 memiliki P6=1 walaupun CNF lokal hanya mendefinisikan lima parameter. Nilai dipertahankan dan ditandai tanpa definisi.',
    '- display_position adalah posisi penyajian CNF; tidak dipakai mengganti urutan nilai parameter dalam PRG.',
    '- factor/offset/scaling disimpan sebagai metadata. Angka PRG ditampilkan dengan satuan definisinya, tidak dikalikan ulang menjadi nilai register.',
    '- Gradient nol, parameter check bernilai nol dan acknowledgement tidak diberi arti perilaku yang belum dibuktikan.',
    '- Mapping alamat register, wiring fisik dan eksekusi langsung PLC belum diverifikasi.',
    '',f'SHA-256 PRG: `{sha}`',f'SHA-256 CNF: `{old["cnf_decode"]["sha256"]}`']
(OUT/'M_0182_seluruh_step.md').write_text('\n'.join(md),encoding='utf-8')

page='''<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PRG 47 DYLON — parameter terbaca</title><style>
*{box-sizing:border-box}body{margin:0;background:#eef2f5;color:#183044;font:15px system-ui}main{max-width:1300px;margin:auto;padding:26px}header{background:#173b50;color:white;padding:28px;border-radius:12px}h1{margin:8px 0;font-size:32px}p{line-height:1.6}.badge{display:inline-block;padding:7px 12px;background:#28566f;border-radius:5px;margin:4px 6px 4px 0}.notice{background:#e6f3ef;border-left:4px solid #18866a;padding:18px;margin:18px 0;line-height:1.6}.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:20px 0}input{padding:12px;min-width:320px;border:1px solid #aebdc8;border-radius:7px}a{color:#116680}button{padding:10px;border:1px solid #bac8d2;background:white;border-radius:6px;cursor:pointer}.step{background:white;border:1px solid #d9e1e7;border-radius:10px;margin:16px 0;overflow:hidden}.step h2{font-size:18px;margin:0;padding:16px;background:#f8fafc}.step h2 span{background:#126e76;color:white;padding:5px 9px;border-radius:5px;margin-right:10px}em{font-style:normal;color:#855c16}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:12px;border-top:1px solid #e4e9ed;text-align:left;vertical-align:top}th{color:#566a7b;font-size:12px}td:nth-child(2){min-width:190px;width:24%}small{display:block;font-size:11px;color:#6c7f8e;margin:3px 0}.params{display:flex;flex-wrap:wrap;gap:8px}.param{background:#f1f6f8;border:1px solid #dee8ed;border-radius:6px;padding:8px 11px;min-width:135px}.param span{display:block;font-size:12px}.param b{display:block;margin-top:5px;font-size:17px;color:#116773}.muted,footer{color:#627787}details{font-size:12px;color:#627787;margin-top:10px}footer{line-height:1.6}#example{background:white;padding:18px;border-radius:8px}@media print{.toolbar,details{display:none}body{background:white}main{padding:0}.step{break-inside:avoid}header{background:white;color:black}.badge{background:#ddd}.param b{color:black}}</style><main>
<header><div>ORGATEX / SECOM · PARAMETER DARI CNF LOKAL</div><h1>PRG 47 DYLON</h1><p>M_0182.PRG · ID program 182 · Diperbarui 29 Oktober 2026</p><span class="badge">58 langkah</span><span class="badge">191 record fungsi</span><span class="badge">20 definisi fungsi cocok</span><p>Nama, satuan, dan referensi parameter kini terbaca dari TYPECONF.CNF. Fungsi tambahan dalam setiap langkah tetap ditampilkan.</p></header>
<div class="notice"><b>Pemetaan selesai untuk program ini:</b> parameter yang didefinisikan CNF kini memiliki nama dan satuan. Empat record fungsi 718 memiliki P6=1 di luar lima parameter yang didefinisikan CNF; nilainya ditandai tanpa definisi. Slot dalam satu langkah berisi fungsi yang berbeda. Angka pilihan hanya diberi teks ketika cocok dengan daftar pilihan CNF. Nilai nol tidak ditafsirkan sebagai perilaku tertentu tanpa bukti tambahan.</div>
<div id="example"><b>Contoh langkah 35 — Temperature Control</b><p>Temperature MA: <b>132 °C</b> · Gradient MA: <b>2 °C/min</b> · Time MA: <b>30 min</b></p></div>
<div class="toolbar"><input id="search" aria-label="Cari langkah" placeholder="Cari step, fungsi, parameter, atau komentar…"><button onclick="window.print()">Cetak / simpan PDF</button><a href="M_0182_seluruh_step.md">Teks lengkap</a><a href="M_0182_decoded.json">JSON program</a><a href="PEMETAAN_PARAMETER_TUNTAS.md">Laporan bukti</a><span id="count">58 langkah ditampilkan</span></div>CARDS
<footer><p>Pembacaan statis; sumber asli utuh. Seluruh 3.519 record CNF direkonstruksi dari 4.463 fragmen. Hubungan fungsi → parameter telah dibaca; alamat register PLC dan perilaku mesin langsung belum diverifikasi. Satuan yang ditampilkan berasal dari definisi parameter. Skala transfer ke PLC tidak diterapkan ulang pada angka program.</p></footer></main><script>const input=document.getElementById('search');input.addEventListener('input',()=>{let n=0;const q=input.value.trim().toLowerCase();for(const section of document.querySelectorAll('.step')){const match=!q||section.textContent.toLowerCase().includes(q)||section.id==='step-'+q;section.hidden=!match;if(match)n++}document.getElementById('count').textContent=n+' langkah ditampilkan'});</script></html>'''.replace('CARDS',''.join(cards))
(OUT/'M_0182_seluruh_step.html').write_text(page,encoding='utf-8')

report=['# Pemetaan parameter M_0182.PRG selesai','',
    'Tanggal: 29 Oktober 2026. Ruang lingkup selesai: hubungan fungsi → urutan parameter → definisi nama/satuan → nilai tersimpan pada seluruh 58 langkah M_0182.PRG.',
    '',f'Hasil: {len(used_funcs)} fungsi, {len(used_params)} definisi parameter, {mapped} nilai pada parameter terdefinisi, 191 record fungsi dan 9 komentar.',
    '', '## Fungsi dan definisi parameter','', '| ID fungsi | Nama | Urutan parameter tersimpan |','|---|---|---|']
for n in used_funcs:
    f=funcs[n];parts=[]
    for i,p in enumerate(f['parameters']):
        pd=params[p['definition_id']]
        parts.append('P'+str(i+1)+' → #'+str(pd['id'])+' '+pd['name']+(' ['+pd['unit']+']' if pd['unit'] else ''))
    report.append('| '+str(n)+' | '+f['name']+' | '+('; '.join(parts) or 'Tidak ada')+' |')
report+=['','## Contoh yang terverifikasi','',
    '- Fungsi 141: tiga parameter berurutan dengan ID definisi 3, 4, 5. Parameter 3 = Temperature MA [°C]; 4 = Gradient MA [°C/min]; 5 = Time MA [min].',
    '- Langkah 35: 132 °C, 2 °C/min, 30 min.',
    '- Fungsi 713: P1 Valve MC (pilihan); P2 Fill quantity MC [L]. Langkah 2 menyimpan 1 dan 1700 L.',
    '- Fungsi 404: P1 Set value variojet [%]; P2 Speed pump [%].',
    '- Fungsi 712: P1 Restarts (Off/On dari text group 200); P2 Winch speed [m/min].',
    '', '## Mengapa sebelumnya belum terbaca','',
    'Record CNF tidak selalu berurutan secara fisik. File memiliki halaman 512 byte, direktori slot di akhir halaman, flag 0x8000 untuk fragment link, serta pointer page/slot. Sebuah record dapat tersebar di beberapa halaman/slot. Setelah fragmen disambung, data masih dikompresi dengan run literal dan run pengulangan. Pencarian string saja tidak menyelesaikan hubungan ini.',
    '', '## Bukti implementasi','',
    '- DLL sumber: Storage/SC777CE/SecomCE_BGUtils_2d.dll. ImageBase 0x100000.',
    '- Api_Btrieve_Decompress RVA 0x2c19 → CBtrieveInterface::Decompress RVA 0x5a9f → routine RVA 0x19aa6. Routine bergantian membaca jumlah literal uint16 + data dan jumlah repeat uint16 + byte berulang.',
    '- Routine pembaca record RVA 0x26fba: flag slot 0x8000 menandakan empat byte pointer lanjutan, directory offset dimask 0x7fff. Helper pointer RVA 0x26708; helper offset slot RVA 0x3871a.',
    '- Sumber struktur: referensi dekompilasi lokal SecomCEDefines/OtxCSLib.Secom.Configuration/T_CFG_FUNCT.cs, T_CFG_FUNCT_PARA.cs, T_CFG_FUNCP.cs, T_CFG_SCALE.cs, T_CFG_SCALE2.cs, T_CFG_TEXTP.cs. Ukuran union lokal cocok dengan 290 byte hasil decode.',
    '- Semua 4.463 fragmen dari halaman data yang valid tercakup tepat sekali dalam 3.519 rantai record. Semua hasil 290 byte, tidak ada key ganda, tidak ada rantai putus/loop pada set record yang diparse.',
    '- 105 record fungsi dan 105 record definisi parameter terbaca, bukan hanya 20 fungsi yang dipakai PRG.',
    '- Seluruh referensi dari 20 definisi fungsi yang dipakai PRG ditemukan. Empat nilai P6=1 fungsi 718 tidak memiliki definisi CNF lokal pada langkah 6, 18, 23, 25.',
    '- Byte PRG asli diverifikasi terhadap hash sebelum pengayaan; hash CNF dicocokkan terhadap inventaris asli.',
    '', '## Perbedaan versi fungsi 718','',
    'CNF lokal, konfigurasi Update, grup 001, backup grup 001, dan grup 002 saat ini mendefinisikan lima parameter. Backup grup 002 mendefinisikan enam; parameter keenam adalah definisi 162, Mixer Type AT2. Daftar text group 32 pada backup: 0=Motor, 1=Valve, 2=Motor/Valve. Jadi P6=1 memiliki padanan Valve pada versi backup tersebut, tetapi tidak memiliki definisi pada CNF lokal. Ini bukti perbedaan konfigurasi, bukan bukti bahwa backup itu sedang dipakai mesin.',
    '', '## Batas yang masih berlaku','',
    'Parameter program adalah nilai proses yang disimpan dalam PRG, bukan alamat register. factor/offset/mode dari CNF disimpan dalam JSON untuk analisis transfer; tidak dikalikan ulang pada tampilan program. index_min/index_max bukan otomatis alamat PLC fisik. display_position adalah posisi tampilan, bukan nomor slot parameter PRG.',
    '', 'Pemetaan nama/satuan parameter yang didefinisikan CNF lokal selesai. Empat nilai P6 fungsi 718 di luar definisi tidak diberi arti. Pemetaan alamat PLC, pembuktian scaling di telegram, makna gradient nol dan verifikasi eksekusi mesin merupakan lingkup lanjutan yang belum dinyatakan selesai.',
    '', '## Artefak','',
    '- M_0182_seluruh_step.html: semua 58 langkah dengan nama/satuan dan pilihan teks yang cocok.',
    '- M_0182_seluruh_step.md: versi teks seluruh langkah.',
    '- M_0182_decoded.json: program plus named_parameters, definisi dan bukti CNF.',
    '- TYPECONF_records_decoded.json: key, byte dekompresi, stream kompresi dan fragmen seluruh 3.519 record.',
    '- TYPECONF_functions_parameters.json: 105 fungsi, 105 parameter dan daftar pilihan teks.',
    '- cnf_decode.py dan enrich_prg_cnf.py: decoder/pengayaan; pembacaan sumber saja.',
    '',f'SHA-256 PRG: `{sha}`',f'SHA-256 CNF: `{old["cnf_decode"]["sha256"]}`']
(OUT/'PEMETAAN_PARAMETER_TUNTAS.md').write_text('\n'.join(report),encoding='utf-8')

# Preserve older analysis, but make its now-resolved limitations explicit.
older=OUT/'ANALISIS_CNF_PLC.md'
s=older.read_text(encoding='utf-8')
note='> Pembaruan 29 Oktober 2026: hubungan fungsi dan parameter yang disebut belum terurai pada laporan awal ini kini sudah selesai untuk seluruh M_0182.PRG. Lihat [hasil terbaru](PEMETAAN_PARAMETER_TUNTAS.md).\n\n'
if not s.startswith('> Pembaruan 29 Oktober 2026:'):older.write_text(note+s,encoding='utf-8')
inventory=json.loads((OUT/'inventaris_file.json').read_text(encoding='utf-8'))
for path in ['Storage/SC777CE/Config/TYPECONF.CNF','Storage/SC777CE/Programs/M_0182.PRG']:
    entry=next(x for x in inventory if x['path']==path)
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==entry['sha256']
print(json.dumps(old['cnf_decode'] | {'functions':'omitted','parameter_definitions':'omitted'},indent=2))
