"""Read-only forensic decoder for the supplied QUEUE.BTD layout; not a Btrieve writer."""
from pathlib import Path
import struct,json,csv,hashlib,re,sys
sys.stdout.reconfigure(encoding='utf-8')
src=Path(r'C:\Users\Lenovo Yoga 7i\Downloads\QUEUE.BTD')
out=Path(r'D:\File HMI\Analisis\QUEUE_20261106')
out.mkdir(exist_ok=True)
b=src.read_bytes();digest=hashlib.sha256(b).hexdigest()
def txt(x):return x.split(b'\0',1)[0].decode('cp1252',errors='replace').strip()
def u16(off):return struct.unpack_from('<H',b,off)[0]
# These offsets are inferred from this sample and checked against its known payload schema.
page_size=u16(8);record_length=u16(22)
assert page_size==1024 and record_length==759 and len(b)%page_size==0
records=[]
for page in range(1,len(b)//page_size):
 off=page*page_size+6;r=b[off:off+759]
 if len(r)!=759 or not re.fullmatch(rb'\d{6}\x00',r[1:8]):continue
 if not re.fullmatch(rb'[A-Z]\d{3}\x00',r[748:753]):continue
 record={'offset':off,'offset_hex':hex(off),'page':page,'status_raw':r[0],
 'reference':txt(r[1:8]),'program_number':struct.unpack_from('<H',r,26)[0],
 'texts':{str(i+1):txt(r[28+i*21:49+i*21]) for i in range(20)},
 'parameters_raw':list(struct.unpack_from('<20f',r,448)),
 'consumption_raw':list(struct.unpack_from('<20f',r,528)),
 'times_raw':list(struct.unpack_from('<20i',r,608)),
 'events_raw':list(struct.unpack_from('<20H',r,688)),
 'alarm_counters_raw':list(struct.unpack_from('<10H',r,728)),
 'dates_hex':r[8:26].hex(),'machine':txt(r[748:753]),
 'host_batch':struct.unpack_from('<H',r,753)[0],
 'host_config':struct.unpack_from('<H',r,755)[0],
 'position':struct.unpack_from('<H',r,757)[0],
 'payload_sha256':hashlib.sha256(r).hexdigest()}
 records.append(record)
assert len(records)==2
records.sort(key=lambda x:x['position'])
assert [r['position'] for r in records]==[1,2]
# Correlate payload keys with the separate index pages in the supplied sample.
for r in records:
 ref=r['reference'].encode()+b'\0'
 assert ref in b[0x400:0x800]
 assert bytes([r['status_raw']])+ref in b[0x800:0xc00]
 assert r['texts']['1'].encode()+b'\0' in b[0xc00:0x1000]
 assert struct.pack('<H',r['position']) in b[0x1410:0x1430]
indexes=[]
for key in range(5):
 start=0x112+30*key
 indexes.append({'key':key,'descriptor_offset':hex(start),
 'candidate_root_page':struct.unpack_from('<I',b,start)[0],
 'payload_offset':u16(start+18),'length':u16(start+20)})
assert [(x['payload_offset'],x['length']) for x in indexes]==[(1,7),(0,8),(28,21),(8,6),(757,2)]
data={'source':str(src),'sha256':digest,'file_bytes':len(b),
 'sample_layout':{'page_bytes':page_size,'pages':len(b)//page_size,'payload_bytes':record_length,
 'record_count':len(records),'key_descriptors':indexes},'records_by_position':records,
 'limitations':['Static extraction, not opened through Btrieve engine.',
 'Sample-specific page/key layout, not a general-purpose Btrieve parser or writer.',
 'Status names follow the available Orgatex library; these are not live PLC states.',
 'Parameter units and time-slot meanings require A001 configuration.']}
(out/'QUEUE_decoded.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
with (out/'QUEUE_batches.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['position','reference','batch','machine','program','title','customer','article','colour_code','colour','recipe','status_raw','parameter_1_raw'])
 for r in records:
  t=r['texts'];w.writerow([r['position'],r['reference'],t['1'],r['machine'],r['program_number'],t['20'],t['3'],t['4'],t['5'],t['6'],t['7'],r['status_raw'],r['parameters_raw'][0]])
lines=['# Isi QUEUE.BTD yang diterima 6 November 2026','',
 'File sumber: '+str(src),'SHA256: '+digest,'',
 'Ditemukan dua payload batch untuk A001. Field posisi dan halaman index mendukung urutan di bawah. Ini pembacaan statis snapshot, bukan status mesin saat ini.','',
 '| Posisi | Referensi | Batch | Mesin | Program | Nama program | Warna | Resep |',
 '|---:|---|---|---|---:|---|---|---|']
for r in records:
 t=r['texts'];lines.append(f"| {r['position']} | {r['reference']} | {t['1']} | {r['machine']} | {r['program_number']} | {t['20']} | {t['6']} | {t['7']} |")
lines+=['','## Struktur dan bukti','',
 '- Ukuran file 12.288 byte; pola halaman 1.024 byte, total 12 halaman.',
 '- Payload 759 byte sesuai T_BATCH_HEADER_ELEMENT. Nilai 759 juga muncul pada header offset 0x16.',
 '- Record 062277 berada di 0x2006 dan berposisi 2; record 062232 berada di 0x2406 dan berposisi 1.',
 '- Referensi ditemukan kembali di halaman index 0x400, status+referensi di 0x800, teks batch di 0xC00, serta posisi di 0x1400.',
 '- Lima descriptor yang teramati memuat offset/panjang payload: key 0 = 1/7, key 1 = 0/8, key 2 = 28/21, key 3 = 8/6, key 4 = 757/2.',
 '- Key 3 menunjuk enam byte pertama field tanggal (dt_terminated) menurut layout library. Semua nilainya nol dalam kedua record, sehingga belum diuji dengan tanggal berbeda.',
 '- Struktur index dan pointer database berada di luar payload. File ini bukan gabungan mentah record 759 byte.',
 '- Kedua status mentah 0 (CREATED pada enum library), host_batch 1, host_config_no 0. Ini tidak membuktikan load release atau mesin running.',
 '- Ketiga field tanggal pada kedua batch masih nol. Field times slot 2 berisi 29835 untuk PJZ828 dan 26651 untuk PKD338; makna/satuan belum ditetapkan.',
 '- Seluruh slot konsumsi, event dan penghitung alarm dalam dua payload bernilai nol.','',
 '## Semua parameter batch mentah','',
 '| Slot | PJZ828 | PKD338 |','|---:|---:|---:|']
for i in range(20):lines.append(f"| {i+1} | {records[0]['parameters_raw'][i]:.8g} | {records[1]['parameters_raw'][i]:.8g} |")
lines+=['','Angka tersebut adalah parameter batch, bukan P1-P6 per fungsi PRG. Slot 1 dinamai WEIGHT pada konstanta library, tetapi satuan dan pemakaian aktual harus diverifikasi pada konfigurasi A001.','',
 '## Hubungan paket batch','',
 'Dengan pola folder yang sudah ditemukan, pasangan yang perlu dicocokkan berikutnya adalah OT/BATCH/062232/BATCHREF.REF + M_0622.PRG serta OT/BATCH/062277/BATCHREF.REF + M_0502.PRG. Nama/path tersebut diturunkan dari referensi dan nomor program; keberadaan paketnya belum diperiksa dari server aktif.','',
 '## Batas untuk pembuatan batch baru','',
 'Analisis ini cukup untuk membaca dua payload dan mengetahui urutannya, tetapi belum menjadi implementasi penulisan Btrieve. Penambahan record harus menjaga page/index, definisi key, pointer, locking dan sinkronisasi dengan paket batch. Jangan mengubah nomor referensi dengan hex editor lalu menganggap seluruh index telah ikut berubah.','',
 'Sumber layout: D:/ORGATEX/OrgaTEX/analysis/decompiled/SecomCEDefines/OtxCSLib.Secom/T_BATCH_HEADER_ELEMENT.cs. Sumber pemilihan index 0 dan 4: D:/ORGATEX/OrgaTEX/analysis/decompiled/CommunicationServiceTasks/SetexCommunication.VirtualController/HostBatchList.cs.','',
 'File sumber tidak diubah. Decoder ini sengaja membatasi dirinya pada pola sampel yang diperiksa.']
(out/'ISI_QUEUE.md').write_text('\n'.join(lines),encoding='utf-8')
assert hashlib.sha256(src.read_bytes()).hexdigest()==digest
print(json.dumps({'records':[{k:r[k] for k in ['reference','position','program_number','machine']} for r in records],'indexes':indexes,'output':str(out),'source_unchanged':True},ensure_ascii=False,indent=2))
