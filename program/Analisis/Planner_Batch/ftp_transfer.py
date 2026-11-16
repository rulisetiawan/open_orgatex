"""Explicit operator-triggered FTP transfer. No automatic connection at startup.

FTP cannot lock Btrieve against OrgaTEX/HMI. Writer suspension and externally
reserved references are prerequisites, not claims made by this transport.
"""
from pathlib import Path, PurePosixPath
import ftplib, hashlib, io, json, re, secrets, ssl, subprocess, tempfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
MAX_FILE=32*1024*1024

def digest(b): return hashlib.sha256(b).hexdigest()
def join(base,name):return base.rstrip('/')+'/'+name

def remote_path(s):
    if not isinstance(s,str) or not s.startswith('/') or any(c in s for c in ['\r','\n','\0','\\']) or '..' in s.split('/'):
        raise ValueError('Path FTP harus absolut memakai /, tanpa .. atau karakter kontrol')
    return str(PurePosixPath(s))

def config(raw,machine):
    host=raw.get('host','').strip();user=raw.get('username','');password=raw.get('password','')
    if not host or '://' in host or any(c in host for c in '/\\\r\n\0 ') or not user or any(c in user+password for c in '\r\n\0'):
        raise ValueError('Isi host tanpa ftp://, username, dan kredensial yang valid')
    port=raw.get('port',21)
    if type(port)!=int or not 1<=port<=65535:raise ValueError('Port FTP tidak valid')
    batch=remote_path(raw.get('batchRoot',''))
    queue=remote_path(raw.get('queuePath','').replace('{machine}',machine))
    if not queue.upper().endswith('/QUEUE.BTD'):raise ValueError('Path queue harus berakhir /QUEUE.BTD')
    return dict(host=host,port=port,username=user,password=password,batchRoot=batch,queuePath=queue,tls=raw.get('tls') is True)

class FTPStore:
    def __init__(self,c):
        self.ftp=ftplib.FTP_TLS(context=ssl.create_default_context(),timeout=20) if c['tls'] else ftplib.FTP(timeout=20)
        try:
            self.ftp.connect(c['host'],c['port']);self.ftp.login(c['username'],c['password'])
            if c['tls']:self.ftp.prot_p()
            self.ftp.set_pasv(True)
        except Exception:
            self.ftp.close();raise ValueError('Koneksi/login FTP gagal. Periksa host, port, kredensial, TLS dan jaringan.') from None
    def close(self): self.ftp.close()
    def list(self,path):
        # Fail closed on listing/permission errors. A missing queue is not assumed empty.
        self.ftp.cwd(path)
        return {PurePosixPath(name.rstrip('/')).name for name in self.ftp.nlst()}
    def get(self,path):
        out=io.BytesIO()
        def add(chunk):
            if out.tell()+len(chunk)>MAX_FILE:raise ValueError('File FTP melebihi 32 MB')
            out.write(chunk)
        self.ftp.retrbinary('RETR '+path,add);return out.getvalue()
    def put(self,path,b):self.ftp.storbinary('STOR '+path,io.BytesIO(b))
    def mkdir(self,path):self.ftp.mkd(path)
    def rename(self,a,b):self.ftp.rename(a,b)
    def remove(self,path):self.ftp.delete(path)
    def rmdir(self,path):self.ftp.rmd(path)

def native(args):
    r=subprocess.run([str(ROOT/'QueueTool.exe'),*map(str,args)],capture_output=True,text=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if r.returncode:raise ValueError('Validasi queue gagal: '+(r.stderr or r.stdout).strip())
    return r.stdout.strip()

def merged_queue(original,records,machine):
    jobs=ROOT/'jobs';jobs.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ftp_',dir=jobs) as tmp:
        p=Path(tmp);src=p/'source.BTD';dump=p/'old.records';src.write_bytes(original)
        native(['dump',src,dump]);old=dump.read_bytes()
        old_rows=[old[i:i+759] for i in range(0,len(old),759)]
        def text(b):return b.split(b'\0',1)[0].decode('cp1252')
        if any(text(r[748:753])!=machine for r in old_rows):raise ValueError('Queue berisi mesin lain; periksa path tujuan')
        names={text(r[28:49]).strip() for r in old_rows}
        if any(text(r[28:49]).strip() in names for r in records):raise ValueError('Nomor batch produksi sudah ada di queue')
        payload=p/'new.records';payload.write_bytes(b''.join(records));out=p/'merged.BTD'
        report=native(['merge',src,payload,out]);return out.read_bytes(),len(old_rows),report

def transfer(payload,prepare,store_factory=FTPStore):
    files,groups,entries=prepare(payload['plans'])
    if len(groups)!=1:raise ValueError('Kirim FTP satu mesin per transaksi. Ekspor ZIP tetap mendukung banyak mesin.')
    machine=next(iter(groups));c=config(payload.get('ftp',{}),machine)
    send=payload.get('action')=='send'
    if payload.get('action') not in ('check','send'):raise ValueError('Aksi FTP tidak valid')
    if send and (payload.get('writersPaused') is not True or payload.get('referencesReserved') is not True):
        raise ValueError('Pengiriman memerlukan akses tulis OrgaTEX/HMI dihentikan sementara dan referensi sudah direservasi di luar planner.')
    job=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+secrets.token_hex(4)
    queue=c['queuePath'];parent=str(PurePosixPath(queue).parent);lock=join(parent,'.planner-transfer.lock')
    store=store_factory(c);events=[];lock_owned=False;backup=None;queue_moved=False;published=False
    local_log=ROOT/'ftp_logs';local_log.mkdir(exist_ok=True)
    report={'job':job,'action':payload['action'],'machine':machine,'queue':queue,'events':events,'committed':False}
    try:
        # Existing root and queue are mandatory; do not guess whether a 550 means absent or denied.
        folders=store.list(c['batchRoot']);names=store.list(parent)
        if PurePosixPath(queue).name not in names:raise ValueError('Queue tujuan belum tersedia/tidak terlihat. Siapkan queue mesin yang valid dahulu.')
        if '.planner-transfer.lock' in names:raise ValueError('Ada lock transfer planner. Periksa transaksi sebelumnya sebelum melanjutkan.')
        for e in entries:
            if e['reference'] in folders:raise ValueError('Folder referensi sudah ada: '+e['reference'])
        if send:
            store.mkdir(lock);lock_owned=True
            store.put(lock+'/owner.json',json.dumps({'job':job,'machine':machine}).encode())
        original=store.get(queue);merged,count,validation=merged_queue(original,groups[machine],machine)
        report.update(existing=count,added=len(entries),references=[e['reference'] for e in entries],validation=validation,original_sha256=digest(original),merged_sha256=digest(merged))
        if not send:
            report['message']='Pemeriksaan baca berhasil; queue gabungan tervalidasi lokal. Belum ada file FTP ditulis atau nomor direservasi.'
            return report
        # Preserve an independent local recovery copy before any remote publication.
        (local_log/(job+'_original.BTD')).write_bytes(original)
        staged=[]
        for e in entries:
            ref=e['reference'];base=join(c['batchRoot'],ref);temp=join(c['batchRoot'],'.pending_'+job+'_'+ref)
            store.mkdir(temp);events.append('Stage folder '+temp)
            prefix='OT/BATCH/'+ref+'/'
            for name,data in files.items():
                if name.startswith(prefix):
                    dest=temp+'/'+name[len(prefix):];store.put(dest,data)
                    if digest(store.get(dest))!=digest(data):raise ValueError('Verifikasi unggah paket gagal')
            staged.append((temp,base))
        newqueue=queue+'.pending_'+job;store.put(newqueue,merged)
        if digest(store.get(newqueue))!=digest(merged):raise ValueError('Verifikasi queue sementara gagal')
        if digest(store.get(queue))!=digest(original):raise ValueError('Queue berubah saat proses. Pengiriman dihentikan; hentikan semua penulis queue.')
        for temp,base in staged:
            if PurePosixPath(base).name in store.list(c['batchRoot']):raise ValueError('Referensi dipakai proses lain sebelum publikasi')
            store.rename(temp,base);events.append('Publish folder '+base)
        # A second comparison narrows the race, but does NOT replace external writer suspension.
        if digest(store.get(queue))!=digest(original):raise ValueError('Queue berubah sebelum commit; paket sudah ada tetapi belum didaftarkan')
        backup=queue+'.backup_'+job;report['committed']=None
        store.rename(queue,backup);queue_moved=True;events.append('Backup queue '+backup)
        if digest(store.get(backup))!=digest(original):raise ValueError('Queue berubah pada rename; butuh pemeriksaan manual')
        store.rename(newqueue,queue);published=True
        if digest(store.get(queue))!=digest(merged):raise ValueError('Queue akhir berubah atau hasilnya belum dapat dipastikan')
        report.update(committed=True,backup=backup,message='Folder batch dan queue gabungan berhasil ditulis serta diverifikasi. Ini bukan konfirmasi load/start HMI atau PLC.')
        events.append('Queue gabungan terverifikasi')
        return report
    except Exception as exc:
        # Restore only when final name is demonstrably absent. Never overwrite a concurrently created file.
        if queue_moved and not published:
            try:
                if PurePosixPath(queue).name not in store.list(parent):
                    store.rename(backup,queue);report['committed']=False;events.append('Nama queue lama dipulihkan')
            except Exception:events.append('Pemulihan otomatis tidak dapat dipastikan; gunakan backup dan log')
        detail=str(exc)
        if c['password']:detail=detail.replace(c['password'],'[redacted]')
        report['error']=detail;report['backup']=backup
        raise ValueError(f'Transfer {job}: {detail}. Periksa log lokal ftp_logs; jangan ulangi otomatis jika status commit tidak pasti.') from None
    finally:
        if lock_owned:
            try:store.remove(lock+'/owner.json');store.rmdir(lock)
            except Exception:events.append('Lock planner belum terhapus; periksa manual')
        store.close()
        # No host credentials or payload password are persisted.
        (local_log/(job+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
