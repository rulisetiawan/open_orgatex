"""Local planner with explicit opt-in FTP transfer; never issues PLC start commands."""
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import base64, hashlib, io, json, os, re, secrets, struct, subprocess, sys, tempfile, zipfile

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
PORT = int(os.environ.get('PLANNER_PORT', '8768'))
HOST = f'127.0.0.1:{PORT}'
PYTHON = sys.executable

def decode64(s):
    return base64.b64decode(s, validate=True)

def text(b):
    return b.split(b'\0', 1)[0].decode('cp1252')

def put_text(b, offset, length, value, label):
    if not isinstance(value, str) or any(ord(c)<32 for c in value):
        raise ValueError(label + ': teks tidak valid')
    try:
        raw=value.encode('cp1252')
    except UnicodeEncodeError:
        raise ValueError(label + ': karakter tidak didukung CP1252')
    if len(raw)>=length:
        raise ValueError(f'{label}: maksimal {length-1} karakter')
    b[offset:offset+length]=raw.ljust(length,b'\0')

def uint16(value, label):
    if type(value) is not int or not 0<=value<=65535:
        raise ValueError(label+': harus bilangan bulat 0–65535')
    return value

def validate_prg(b):
    if len(b)<449 or b[:4]!=bytes.fromhex('508fc2f5') or (len(b)-384)%65:
        raise ValueError('Format PRG tidak didukung')
    number=struct.unpack_from('<H',b,8)[0]
    count=struct.unpack_from('<H',b,33)[0]
    if not 1<=number<=9999 or not count:
        raise ValueError('Nomor program/jumlah langkah tidak valid')
    mains={}; slots=set()
    for off in range(384,len(b),65):
        step=struct.unpack_from('<H',b,off)[0]; slot=b[off+2]
        if not 1<=step<=count or slot>13:
            raise ValueError('Record langkah/slot PRG tidak valid')
        if slot:
            if (step,slot) in slots: raise ValueError('Slot PRG ganda')
            slots.add((step,slot))
            vals=[struct.unpack_from('<f',b,off+9+i*6)[0] for i in range(6)]
            if not all(__import__('math').isfinite(x) for x in vals): raise ValueError('Parameter PRG tidak finite')
        if slot==1: mains[step]=struct.unpack_from('<H',b,off+4)[0]
    # M_0502 ends with ID 5, while the older B012 templates end with ID 2.
    # Validate framing/main slots without assuming B012 termination semantics.
    if len(mains)!=count or mains.get(1)!=1:
        raise ValueError('PRG perlu fungsi utama tiap langkah dan Program Start')
    return number, text(b[10:31]), count

def prepare(plans):
    if not isinstance(plans,list) or not 1<=len(plans)<=200:
        raise ValueError('Isi 1–200 planning per ekspor')
    refs=set(); names=set(); groups={}; files={}; entries=[]
    for plan in plans:
        ref=plan['reference']; machine=plan['machine']; batch=plan['batch']
        if not isinstance(ref,str) or not re.fullmatch(r'\d{6}',ref) or ref=='000000': raise ValueError('Referensi harus 000001–999999')
        if ref in refs: raise ValueError('Referensi ganda: '+ref)
        refs.add(ref)
        if not isinstance(machine,str) or not re.fullmatch(r'[A-Z0-9]{1,4}',machine): raise ValueError('Mesin: 1–4 huruf/angka kapital')
        if not batch.strip() or (machine,batch) in names: raise ValueError('Nama batch kosong/ganda dalam mesin')
        names.add((machine,batch))
        source=decode64(plan['batchSource']); prg=decode64(plan['program'])
        if len(source)!=762 or source[761]!=0: raise ValueError('Template BATCHREF harus satu program tipe M (762 byte)')
        if ref==text(source[1:8]): raise ValueError('Gunakan referensi baru, berbeda dari batch sumber')
        pn,title,steps=validate_prg(prg)
        params=plan['parameters']; texts=plan['texts']
        if len(params)!=20 or len(texts)!=20: raise ValueError('Diperlukan 20 parameter dan 20 slot teks')
        b=bytearray(source)
        b[0]=0; b[8:26]=bytes(18); b[528:608]=bytes(80); b[688:748]=bytes(60)
        put_text(b,1,7,ref,'Referensi'); put_text(b,748,5,machine,'Mesin')
        struct.pack_into('<H',b,26,pn)
        for i,value in enumerate(texts): put_text(b,28+21*i,21,value,f'Teks {i+1}')
        put_text(b,28,21,batch,'Batch'); put_text(b,427,21,title,'Judul program')
        for i,value in enumerate(params):
            if type(value) not in (int,float) or not __import__('math').isfinite(value): raise ValueError('Parameter batch harus angka finite')
            try: struct.pack_into('<f',b,448+4*i,value)
            except (OverflowError,struct.error): raise ValueError('Parameter di luar rentang float32')
        cfg=uint16(plan['batchConfig'],'Konfigurasi BATCHREF'); qcfg=uint16(plan['queueConfig'],'Konfigurasi queue')
        struct.pack_into('<HHHHB',b,753,1,cfg,0,pn,0)
        queue=bytearray(b[:759]); position=len(groups.setdefault(machine,[]))+1
        struct.pack_into('<HH',queue,755,qcfg,position); groups[machine].append(queue)
        folder=f'OT/BATCH/{ref}'
        files[folder+'/BATCHREF.REF']=bytes(b); files[folder+f'/M_{pn:04}.PRG']=prg
        entries.append({'reference':ref,'batch':batch,'machine':machine,'position':position,'program':pn,'steps':steps,'batch_config':cfg,'queue_config':qcfg,'source_reference':text(source[1:8]),'source_machine':text(source[748:753]),'source_sha256':hashlib.sha256(source).hexdigest(),'program_sha256':hashlib.sha256(prg).hexdigest()})
    return files,groups,entries

def export(payload):
    files,groups,entries=prepare(payload['plans'])
    reports={}
    jobs=ROOT/'jobs'; jobs.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='job_',dir=jobs) as temp:
        temp=Path(temp)
        for machine,records in groups.items():
            rec=temp/(machine+'.records'); out=temp/(machine+'.BTD')
            rec.write_bytes(b''.join(records))
            result=subprocess.run([str(ROOT/'QueueTool.exe'),str(ROOT/'QUEUE.template.BTD'),str(rec),str(out)],capture_output=True,text=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode: raise ValueError('Queue '+machine+': '+(result.stderr or result.stdout).strip())
            files[f'OT/MACHINES/{machine}/BATCHES/QUEUE.BTD']=out.read_bytes()
            reports[machine]=result.stdout.strip()
    manifest={'format':'SETEX-OFFLINE-PLANNING','version':1,'mode':'NEW_QUEUE_NOT_MERGE','verification':'Native local Btrieve engine reopen and byte-exact reads via all five keys; no HMI/PLC runtime test','counter_reserved':False,'next_reference_candidate':max(int(x['reference']) for x in entries)+1,'entries':entries,'queue_checks':reports,'files_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in files.items()},'limitations':['Machine compatibility, recipe quantities and parameter units are not calculated or validated.','BATCHREF template times[20] are preserved; timestamps, consumption and event/alarm counters are reset.','Counter is an offline candidate, not a reservation.','Queue contains only this export; do not replace a live queue with pending jobs.']}
    files['planning-manifest.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    files['BACA_DULU.txt']=('PAKET PLANNING OFFLINE\r\n\r\nQueue baru hanya berisi planning dalam ekspor ini; bukan penggabungan antrean aktif.\r\nBREFNEXT.DAT server tidak diubah dan nomor belum dipesan.\r\nLibrary Btrieve lokal berhasil menulis dan membaca ulang semua record melalui key 0-4.\r\nPenerimaan HMI/PLC, kecocokan konfigurasi mesin, satuan, resep dan dosis belum diuji.\r\nTidak ada perintah transfer atau start mesin. Periksa planning-manifest.json.\r\n').encode()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items(): z.writestr(name,data)
    return stream.getvalue()

class Handler(BaseHTTPRequestHandler):
    def send(self,data,status=200,kind='application/json'):
        self.send_response(status); self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.headers.get('Host')!=HOST: self.send(b'Invalid host',403,'text/plain');return
        if self.path=='/api/state':
            data=json.loads((ROOT/'data.json').read_text('utf-8'));data['token']=TOKEN
            self.send(json.dumps(data,ensure_ascii=False).encode());return
        mapping={'/':ROOT.parent/'Planner_Batch.html','/Planner_Batch.html':ROOT.parent/'Planner_Batch.html','/app.js':ROOT/'app.js','/Planner_Batch/app.js':ROOT/'app.js','/Editor_PRG.html':ROOT.parent/'Editor_PRG.html'}
        p=mapping.get(self.path)
        if not p: self.send(b'Not found',404,'text/plain');return
        self.send(p.read_bytes(),kind='text/javascript; charset=utf-8' if p.suffix=='.js' else 'text/html; charset=utf-8')
    def do_POST(self):
        if self.headers.get('Host')!=HOST or self.headers.get('X-Planner-Token')!=TOKEN or self.headers.get('Origin') not in (None,'http://'+HOST): self.send(b'{"error":"Request ditolak"}',403);return
        if self.path not in ('/api/export','/api/ftp'): self.send(b'{}',404);return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=30_000_000: raise ValueError('Ukuran permintaan tidak valid')
            payload=json.loads(self.rfile.read(length))
            if self.path=='/api/ftp':
                from ftp_transfer import transfer
                data=transfer(payload,prepare)
                self.send(json.dumps(data,ensure_ascii=False).encode())
            else:
                data=export(payload)
                self.send(data,kind='application/zip')
        except Exception as e: self.send(json.dumps({'error':str(e)},ensure_ascii=False).encode(),400)
    def log_message(self,*args): pass

if __name__=='__main__':
    HTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
