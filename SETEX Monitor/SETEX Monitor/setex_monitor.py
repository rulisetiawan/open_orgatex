"""SETEX snapshot viewer. Python standard library, Windows only."""
from datetime import datetime
import ctypes
from ctypes import wintypes as W
import ftplib
from urllib.parse import urlsplit, unquote
import json
import multiprocessing as mp
import os
from pathlib import Path
import struct
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

FIELDS = [("Parameter suhu A", 0x16D, "f", 1, "°C kandidat"),
          ("Parameter suhu B", 0x171, "f", 1, "°C kandidat"),
          ("Parameter gradien A", 0x183, "f", 1, "°C/min kandidat"),
          ("Parameter gradien B", 0x187, "f", 1, "°C/min kandidat"),
          ("Parameter waktu mentah", 0x1A1, "H", 1, "bukan countdown")]
CONSUMPTION_FIELDS = [(1,"Total pemakaian air 1",0x2608,"L"),
                      (2,"Total pemakaian air 2",0x2610,"L"),
                      (3,"Total pemakaian air 3",0x2618,"L"),
                      (4,"Total pemakaian air 4",0x2620,"L"),
                      (6,"Total energi listrik",0x2630,"kWh")]
CONFIG = Path(__file__).with_name('monitor_settings.json')

def shared_read(path):
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.argtypes = [W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE]
    k.CreateFileW.restype = W.HANDLE
    k.ReadFile.argtypes = [W.HANDLE,W.LPVOID,W.DWORD,ctypes.POINTER(W.DWORD),W.LPVOID]
    k.ReadFile.restype = W.BOOL
    k.CloseHandle.argtypes = [W.HANDLE]
    # GENERIC_READ; FILE_SHARE_READ | FILE_SHARE_WRITE; OPEN_EXISTING.
    h = k.CreateFileW(path, 0x80000000, 3, None, 3, 0, None)
    if h == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        buf = ctypes.create_string_buffer(10189)
        n = W.DWORD()
        if not k.ReadFile(h, buf, len(buf), ctypes.byref(n), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return buf.raw[:n.value]
    finally:
        k.CloseHandle(h)

def decode(data):
    if len(data) not in (10104,10188):
        raise ValueError(f'Ukuran STATUS.ACT {len(data)} byte tidak didukung; gunakan format 10104 atau 10188.')
    extended=len(data)==10188
    step_offset=0x15E if extended else 0x15C
    def text(offset):
        return data[offset:offset+64].split(b'\0',1)[0].decode('ascii', errors='replace')
    return dict(machine=text(11), lot=text(38), program=text(52), description=text(75),
                status_raw=struct.unpack_from('<H',data,16)[0],
                format_bytes=len(data),step_offset=hex(step_offset),
                block_start=hex(0x154 if extended else 0x152),block_stride=205 if extended else 203,
                step=struct.unpack_from('<H',data,step_offset)[0],
                fault_word_raw=struct.unpack_from('<H',data,0x20)[0],
                fault_bits={str(bit):bool(struct.unpack_from('<H',data,0x20)[0] & (1<<bit)) for bit in (4,5,6,7)},
                consumption=[dict(index=index,name=name,offset=hex(offset),raw=struct.unpack_from('<d',data,offset)[0],
                                  unit=unit,type='float64_le',mapping_verified=False,hex=data[offset:offset+8].hex(' '))
                             for index,name,offset,unit in ([] if extended else CONSUMPTION_FIELDS)],
                fields=[dict(name=n,offset=hex(o),raw=struct.unpack_from('<'+f,data,o)[0],
                             value=struct.unpack_from('<'+f,data,o)[0]*scale,unit=u,
                             hex=data[o:o+struct.calcsize(f)].hex(' '))
                        for n,o,f,scale,u in ([] if extended else FIELDS)])

def display_rows(decoded):
    extended=decoded['format_bytes']==10188
    known = not extended and decoded['machine']=='E013' and decoded['step']==3
    rows=[('format','Format STATUS.ACT','—',str(decoded['format_bytes'])+' byte','Blok '+decoded['block_start']+'; stride '+str(decoded['block_stride'])),
          ('machine','Mesin','0x00B',decoded['machine'],'String sampai null'),
          ('lot','Nomor lot','0x026',decoded['lot'],'Identitas batch'),
          ('program','Kode resep','0x034',decoded['program'] or '(kosong)','Tidak disimpulkan dari nama file'),
          ('description','Deskripsi resep','0x04B',decoded['description'],'String sampai null'),
          ('step','Nomor step kandidat',decoded['step_offset'],str(decoded['step']),'Belum cocokkan HMI C011' if extended else 'Mengikuti step 2/3/4/5 pada E013'),
          ('status','Status mentah','0x010',str(decoded['status_raw']),'Bukan pemetaan RUN/BREAK/END')]
    word=decoded['fault_word_raw']
    rows.append(('fault_word','Word flag mentah','0x0020',f'0x{word:04X} / {word:016b}','UInt16 LE; bit lain belum dipetakan'))
    for bit,label,meaning in [(4,'Bit 4 PLC offline?','Error 90 kandidat; mask 0x0010'),
                              (7,'Bit 7 PLC offline?','Error 90 kandidat; mask 0x0080'),
                              (5,'Bit 5 Stop alarm?','Error 91 kandidat; mask 0x0020'),
                              (6,'Bit 6 Hold alarm?','Error 92 kandidat; mask 0x0040')]:
        rows.append((f'fault_bit_{bit}',label,'0x0020',
                     '1 / SET' if word & (1<<bit) else '0 / CLEAR',meaning+'; arti belum terverifikasi'))
    rows.append(('plc_offline_candidate','Gabungan bit 4/7','0x0020',
                 '1 / SET' if word & 0x0090 else '0 / CLEAR','Kandidat Error 90; CLEAR bukan jaminan PLC normal'))
    if extended:
        rows.append(('unmapped','Parameter proses','—','BELUM DIPETAKAN','Offset suhu/gradien E013 tidak dipakai untuk format ini'))
    for f in decoded['fields']:

        note=('Target suhu/gradien; cocok pada Temperature Control' if known else 'Raw; arti tergantung fungsi step')
        if f['offset']==hex(0x1A1):note='Raw; 120 cocok 2 menit, bukan countdown aktif'
        rows.append((f['offset'],f['name'],f['offset'],repr(f['raw']),note))
    for item in decoded['consumption']:
        rows.append(('consumption_'+str(item['index']),item['name']+' ?',item['offset'],
                     repr(item['raw'])+' '+item['unit'],'Float64 LE; nama kanal/unit kandidat, perlu cocokkan HMI'))
    return rows

def ftp_read(url, username='', password='', timeout=8, include_alarm=False):
    target = urlsplit(url)
    if target.scheme != 'ftp' or not target.hostname or target.username is not None or target.query or target.fragment:
        raise ValueError('Gunakan ftp://host/path tanpa kredensial atau query di URL.')
    path = unquote(target.path).rstrip('/')
    if not path.lower().endswith('.act'):
        path += '/STATUS.ACT' if path.lower().endswith('/status') else '/STATUS/STATUS.ACT'
    if any(c in path for c in '\r\n'):
        raise ValueError('Path FTP tidak valid.')
    data = bytearray()
    def receive(block):
        data.extend(block)
        if len(data) > 10188:
            raise ValueError('Unduhan melebihi batas format STATUS.ACT 10188 byte; dihentikan.')
    with ftplib.FTP(timeout=timeout) as ftp:
        ftp.connect(target.hostname, target.port or 21)
        ftp.login(username or 'anonymous', password)
        ftp.set_pasv(True)
        ftp.retrbinary('RETR ' + path, receive, blocksize=4096)
        if include_alarm:
            alarm_data=bytearray()
            def receive_alarm(block):
                alarm_data.extend(block)
                if len(alarm_data)>34:raise ValueError('ALARM.ACT melebihi 34 byte; ditolak.')
            try:
                alarm_path=path.rsplit('/',1)[0]+'/ALARM.ACT'
                ftp.retrbinary('RETR '+alarm_path,receive_alarm,blocksize=64)
                alarm=decode_alarm(bytes(alarm_data))
            except Exception as e:alarm={'error':str(e)}
            return bytes(data),alarm
    return bytes(data)

def local_snapshot_path(path):
    absolute = os.path.abspath(path)
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.GetDriveTypeW.argtypes = [W.LPCWSTR]
    k.GetDriveTypeW.restype = W.UINT
    drive = os.path.splitdrive(absolute)[0]
    if absolute.startswith('\\\\') or not drive or k.GetDriveTypeW(drive + '\\') != 3:
        raise ValueError('Snapshot hanya boleh disimpan pada disk lokal tetap, bukan UNC/network drive.')
    return Path(absolute)

def decode_alarm(data):
    if len(data)!=34:raise ValueError(f'Ukuran ALARM.ACT {len(data)} byte; diharapkan 34.')
    return dict(error='',hex=data.hex(' '),words=list(struct.unpack('<17H',data)))

def worker(path, conn, username="", password="", timeout=8):
    try:
        if path.lower().startswith('ftp://'):
            data,alarm=ftp_read(path,username,password,timeout,include_alarm=True)
        else:
            data=shared_read(path)
            try:alarm=decode_alarm(shared_read(str(Path(path).with_name('ALARM.ACT'))))
            except Exception as e:alarm={'error':str(e)}
        decoded=decode(data);decoded['alarm_act']=alarm
        conn.send(('ok',data,decoded,time.strftime('%Y-%m-%d %H:%M:%S')))
    except Exception as e:conn.send(('error',str(e)))
    finally:conn.close()

def decode_alarm_log(data):
    """Candidate payload scan, not a complete Btrieve record decoder."""
    rows=[];seen=set()
    def timestamp(offset):
        raw=data[offset:offset+6]
        if len(raw)!=6 or not 100<=raw[0]<=150:raise ValueError('Invalid year')
        return datetime(1900+raw[0],raw[1],raw[2],raw[3],raw[4],raw[5])
    for i in range(6,len(data)-11):
        try:
            start=timestamp(i);end=timestamp(i+6)
            code=struct.unpack_from('<H',data,i-6)[0];kind=struct.unpack_from('<H',data,i-2)[0]
            if not 1<=code<=1000 or kind>100 or end<start:continue
            key=(code,start,end)
            if key in seen:continue
            seen.add(key)
            rows.append(dict(offset=hex(i-6),alarm=code,start=start.isoformat(' '),end=end.isoformat(' '),
                             duration_s=int((end-start).total_seconds()),kind_raw=kind))
        except (ValueError,OverflowError):continue
    return sorted(rows,key=lambda row:row['start'],reverse=True)

def alarm_log_worker(path, conn, username='', password='', timeout=60):
    try:
        if path.lower().startswith('ftp://'):
            target=urlsplit(path);remote=unquote(target.path).rstrip('/')
            if target.username is not None or any(c in remote for c in '\r\n'):
                raise ValueError('URL tidak valid')
            if remote.lower().endswith('.act'):remote=remote.rsplit('/',1)[0]
            elif not remote.lower().endswith('/status'):remote+='/STATUS'
            remote+='/ALARMS.LOG'
            data=bytearray()
            def receive(block):
                data.extend(block)
                if len(data)>4*1024*1024:raise ValueError('ALARMS.LOG melebihi batas baca 4 MiB')
            with ftplib.FTP(timeout=timeout) as ftp:
                ftp.connect(target.hostname,target.port or 21);ftp.login(username or 'anonymous',password)
                ftp.set_pasv(True);ftp.retrbinary('RETR '+remote,receive,blocksize=16384)
            data=bytes(data)
        else:
            # Existing bounded shared reader must not truncate the database log.
            source=str(Path(path).with_name('ALARMS.LOG'))
            k=ctypes.WinDLL('kernel32',use_last_error=True)
            k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
            k.ReadFile.argtypes=[W.HANDLE,W.LPVOID,W.DWORD,ctypes.POINTER(W.DWORD),W.LPVOID];k.CloseHandle.argtypes=[W.HANDLE]
            h=k.CreateFileW(source,0x80000000,3,None,3,0,None)
            if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
            try:
                buf=ctypes.create_string_buffer(4*1024*1024+1);n=W.DWORD()
                if not k.ReadFile(h,buf,len(buf),ctypes.byref(n),None):raise ctypes.WinError(ctypes.get_last_error())
                if n.value>4*1024*1024:raise ValueError('ALARMS.LOG melebihi batas baca 4 MiB')
                data=buf.raw[:n.value]
            finally:k.CloseHandle(h)
        conn.send(('log',data,time.strftime('%Y-%m-%d %H:%M:%S'),decode_alarm_log(data)))
    except Exception as e:conn.send(('error',str(e)))
    finally:conn.close()

class App:
    def __init__(self, root):
        self.root=root; root.title('SETEX LAN — pembanding snapshot'); root.geometry('1150x850')
        self.proc=None; self.conn=None; self.running=False; self.last=None; self.closed=False
        self.next_read=0; self.settings={}
        try: self.settings=json.loads(CONFIG.read_text(encoding='utf-8'))
        except (OSError,ValueError): pass
        frame=ttk.Frame(root,padding=15);frame.pack(fill='both',expand=True)
        self.ip=tk.StringVar(value=self.settings.get('ip',''))
        self.folder=tk.StringVar(value=self.settings.get('folder',r'sc777ce'))
        self.interval=tk.StringVar(value=str(self.settings.get('interval',30)))
        self.timeout=tk.StringVar(value='60')
        for label,var in [('IP / hostname HMI',self.ip),('URL FTP / folder share / path lokal / path STATUS.ACT',self.folder)]:
            ttk.Label(frame,text=label).pack(anchor='w');ttk.Entry(frame,textvariable=var).pack(fill='x',pady=(2,8))
        ttk.Label(frame,text=r'Contoh: IP 192.168.1.20 + folder sc777ce → \\192.168.1.20\sc777ce\STATUS\STATUS.ACT').pack(anchor='w')
        ttk.Label(frame,text='Bisa juga isi folder dengan UNC lengkap atau folder salinan lokal; IP boleh kosong.').pack(anchor='w')
        self.username=tk.StringVar();self.password=tk.StringVar()
        login=ttk.Frame(frame);login.pack(fill='x',pady=5)
        ttk.Label(login,text='FTP username (kosong = anonymous)').pack(side='left')
        ttk.Entry(login,textvariable=self.username,width=20).pack(side='left',padx=5)
        ttk.Label(login,text='Password (tidak disimpan)').pack(side='left')
        ttk.Entry(login,textvariable=self.password,show='*',width=20).pack(side='left',padx=5)
        ttk.Label(frame,text='FTP: isi URL lengkap. RETR saja; sharing file ditentukan server HMI. Uji Baca sekali dahulu.').pack(anchor='w')
        options=ttk.Frame(frame);options.pack(fill='x',pady=10)
        for label,var in [('Interval (detik)',self.interval),('Timeout (detik)',self.timeout)]:
            ttk.Label(options,text=label).pack(side='left',padx=5);ttk.Entry(options,textvariable=var,width=6).pack(side='left')
        for label,cmd in [('Baca sekali',self.once),('Mulai cyclic',self.start),('Stop',self.stop),('Simpan snapshot',self.save),('Baca ALARMS.LOG',self.read_alarm_log)]:
            ttk.Button(options,text=label,command=cmd).pack(side='left',padx=4)
        self.state=tk.StringVar(value='Belum membaca.');ttk.Label(frame,textvariable=self.state,wraplength=900).pack(anchor='w',pady=5)
        self.previous_rows={};self.previous_source=None
        cols=('name','offset','value','previous','change','note')
        self.table=ttk.Treeview(frame,columns=cols,show='headings',height=12)
        for c,title,width in zip(cols,['Identitas / parameter','Offset','Nilai sekarang','Nilai sebelumnya','Perubahan','Keterangan'],[170,80,150,140,100,300]):
            self.table.heading(c,text=title);self.table.column(c,width=width)
        self.table.tag_configure('changed',background='#fff0a6',foreground='#703b00')
        table_scroll=ttk.Scrollbar(frame,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=table_scroll.set)
        table_scroll.pack(side='right',fill='y')
        self.table.pack(fill='both',expand=True)
        ttk.Label(frame,text='Sumber: STATUS.ACT + ALARM.ACT (34 byte), dibaca ke RAM. Perubahan alarm mentah bukan konfirmasi alarm aktif.').pack(anchor='w')
        ttk.Label(frame,text='Kuning + BERUBAH: berbeda dari pembacaan sukses sebelumnya pada sumber yang sama. Pembacaan pertama menjadi acuan.\nParameter suhu/gradien hanya cocok pada E013 step 003 Temperature Control yang diuji; step lain ditampilkan sebagai raw.\nFlag 0x20 masih kandidat; CLEAR bukan jaminan bebas gangguan. Status raw bukan RUN/BREAK/END. Interval dihitung setelah pembacaan selesai.',wraplength=1050).pack(anchor='w',pady=10)
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(100,self.tick)
    def parameters(self):
        interval=float(self.interval.get());timeout=float(self.timeout.get())
        if not 2<=interval<=3600 or not 1<=timeout<=120:raise ValueError('Interval 2–3600 detik; timeout 1–120 detik.')
        p=self.folder.get().strip().strip('"')
        if not p:raise ValueError('Isi folder share atau path file.')
        if p.lower().startswith('ftp://'):
            target=urlsplit(p)
            if target.username is not None:raise ValueError('Isi kredensial di kolom login, bukan URL.')
            if interval < 30:raise ValueError('Interval FTP minimal 30 detik untuk pengujian awal.')
            return p,interval,timeout
        if not os.path.isabs(p):
            host=self.ip.get().strip()
            if not host or any(c in host for c in '\\/:'):raise ValueError('Isi IP / hostname tanpa slash.')
            p='\\\\'+host+'\\'+p.strip('\\/')
        if not p.lower().endswith('.act'):
            p=os.path.join(p,'STATUS.ACT') if os.path.basename(p).lower()=='status' else os.path.join(p,'STATUS','STATUS.ACT')
        return p,interval,timeout
    def launch(self):
        if self.proc is not None:return
        try:
            path,interval,timeout=self.parameters()
            self.active_source=path
            self.active_interval=interval
            CONFIG.write_text(json.dumps(dict(ip=self.ip.get(),folder=self.folder.get(),interval=interval),indent=2),encoding='utf-8')
            recv,send=mp.Pipe(duplex=False)
            self.proc=mp.Process(target=worker,args=(path,send,self.username.get(),self.password.get(),timeout),daemon=True);self.conn=recv
            self.proc.start();send.close();self.deadline=time.monotonic()+timeout
            self.state.set('Membaca FTP RETR…' if path.lower().startswith('ftp://') else 'Membaca shared read-only… '+path)
        except Exception as e:
            self.running=False;self.cleanup();messagebox.showerror('Tidak dapat membaca',str(e))
    def once(self):
        self.running=False
        self.launch()
    def start(self):
        try:self.parameters()
        except ValueError as e:messagebox.showerror('Pengaturan',str(e));return
        self.running=True;self.next_read=0
    def cleanup(self):
        if self.proc:
            if self.proc.is_alive():self.proc.terminate()
            self.proc.join(timeout=0.1)
            self.proc=None
        if self.conn:self.conn.close();self.conn=None
    def stop(self):
        self.running=False;self.cleanup();self.state.set('STOP — nilai terakhir STALE; monitoring dihentikan.')
    def tick(self):
        if self.closed:return
        if self.proc is not None:
            result=None
            try:
                if self.conn.poll():result=self.conn.recv()
                elif time.monotonic()>self.deadline:result=('error','Timeout; worker pembaca dihentikan.')
                elif not self.proc.is_alive():result=('error','Worker berhenti tanpa hasil.')
            except (EOFError,OSError) as e:result=('error',str(e))
            if result:
                self.cleanup()
                if result[0]=='log':
                    self.show_alarm_log(result[1],result[2],result[3])
                    self.state.set(f'ALARMS.LOG dibaca manual {result[2]} | {len(result[1])} byte. Cyclic berhenti.')
                elif result[0]=='ok':
                    _,data,decoded,stamp=result;self.last=(data,decoded,stamp)
                    rows=display_rows(decoded)
                    alarm=decoded['alarm_act']
                    if alarm.get('error'):
                        rows.append(('alarm_error','ALARM.ACT','—','GAGAL / STALE',alarm['error']))
                    else:
                        rows.append(('alarm_hex','ALARM.ACT hex','0x00–0x21',alarm['hex'],'Perubahan byte saja; bukan status alarm terverifikasi'))
                        for index,value in enumerate(alarm['words']):
                            rows.append((f'alarm_word_{index}',f'ALARM word[{index}]',hex(index*2),f'{value} / 0x{value:04X}','UInt16 LE mentah; bukan kode alarm terverifikasi'))
                    baseline=self.previous_rows if self.previous_source==self.active_source else {}
                    for item in self.table.get_children():self.table.delete(item)
                    count=0
                    for key,name,offset,value,note in rows:
                        changed=key in baseline and baseline[key]!=value
                        count+=changed
                        self.table.insert('', 'end',values=(name,offset,value,baseline.get(key,'—'),
                            'BERUBAH' if changed else ('SAMA' if key in baseline else 'ACUAN'),note),
                            tags=('changed',) if changed else ())
                    bytes_changed=sum(x!=y for x,y in zip(self.previous_data,data))+abs(len(self.previous_data)-len(data)) if baseline else None
                    self.previous_rows={r[0]:r[3] for r in rows};self.previous_data=data;self.previous_source=self.active_source
                    detail=f'{bytes_changed} byte berbeda' if bytes_changed is not None else 'snapshot acuan'
                    mode='CYCLIC' if self.running else 'SEKALI'
                    self.state.set(f'{mode} | {stamp} | {count} nilai berubah | {detail}. Waktu PC; freshness sumber belum diketahui.')
                else:self.state.set('STALE / GAGAL: '+result[1]+(' Cyclic akan mencoba lagi.' if self.running else ''))
                try:self.next_read=time.monotonic()+max(2,self.active_interval)
                except ValueError:self.running=False
        if self.running and self.proc is None and time.monotonic()>=self.next_read:self.launch()
        self.root.after(100,self.tick)
    def save(self):
        if self.last is None:messagebox.showinfo('Snapshot','Baca satu snapshot dahulu.');return
        path=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('Snapshot JSON','*.json')])
        if path:
            try:
                path=local_snapshot_path(path)
                data,decoded,stamp=self.last
                Path(path).write_text(json.dumps(dict(read_time=stamp,verified_mapping=False,**decoded),indent=2),encoding='utf-8')
                Path(path).with_suffix('.ACT').write_bytes(data)
            except (OSError,ValueError) as e:messagebox.showerror('Gagal menyimpan',str(e))
    def read_alarm_log(self):
        if self.proc is not None:
            messagebox.showinfo('Pembacaan berjalan','Tunggu pembacaan selesai atau klik Stop dahulu.');return
        try:
            path,interval,timeout=self.parameters()
            self.running=False;self.active_interval=interval
            recv,send=mp.Pipe(duplex=False)
            self.conn=recv;self.proc=mp.Process(target=alarm_log_worker,args=(path,send,self.username.get(),self.password.get(),timeout),daemon=True)
            self.proc.start();send.close();self.deadline=time.monotonic()+timeout
            self.state.set('Membaca ALARMS.LOG manual ke RAM; cyclic dihentikan…')
        except Exception as e:
            self.cleanup();messagebox.showerror('Gagal membaca log',str(e))
    def show_alarm_log(self,data,stamp,rows=None):
        window=tk.Toplevel(self.root);window.title('ALARMS.LOG — kandidat riwayat alarm');window.geometry('1000x700')
        ttk.Label(window,text=f'{stamp} | {len(data)} byte | {len(data)//512} blok penuh 512 byte + {len(data)%512} byte',padding=10).pack(anchor='w')
        if rows is None:rows=decode_alarm_log(data)
        ttk.Label(window,text=f'{len(rows)} kandidat entri, terbaru dahulu. Nomor/waktu cocok pada sampel HMI; bukan decoder database lengkap.\nNama alarm, alarm yang masih aktif, acknowledgment dan kelengkapan histori belum dipetakan.',padding=10).pack(anchor='w')
        notebook=ttk.Notebook(window);notebook.pack(fill='both',expand=True)
        history=ttk.Frame(notebook);body=ttk.Frame(notebook)
        notebook.add(history,text='Kandidat riwayat');notebook.add(body,text='Hex mentah')
        columns=('alarm','start','end','duration','offset','kind')
        table=ttk.Treeview(history,columns=columns,show='headings')
        for col,title,width in zip(columns,['Alarm kandidat','Waktu mulai','Waktu selesai','Durasi','Offset payload kandidat','Tipe raw'],[110,180,180,100,170,80]):
            table.heading(col,text=title);table.column(col,width=width)
        scroll=ttk.Scrollbar(history,command=table.yview);table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');table.pack(fill='both',expand=True)
        for row in rows:
            seconds=row['duration_s'];hours,remainder=divmod(seconds,3600);minutes,seconds=divmod(remainder,60)
            table.insert('', 'end',values=(f"{row['alarm']:03d}",row['start'],row['end'],f'{hours:02d}:{minutes:02d}:{seconds:02d}',row['offset'],row['kind_raw']))
        if not rows:ttk.Label(history,text='Tidak ditemukan pasangan waktu sesuai pola. Ini bukan bukti tidak ada alarm.').pack(anchor='w',pady=10)
        text=tk.Text(body,font=('Consolas',10),wrap='none');bar=ttk.Scrollbar(body,command=text.yview);text.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y');text.pack(fill='both',expand=True)
        preview=data[:65536]
        text.insert('end','Offset    Hex                                              ASCII\n')
        for offset in range(0,len(preview),16):
            block=preview[offset:offset+16];ascii_text=''.join(chr(v) if 32<=v<127 else '.' for v in block)
            text.insert('end',f'{offset:08X}  {block.hex(" "):<47}  {ascii_text}\n')
        if len(data)>len(preview):text.insert('end','\nPreview dibatasi 65536 byte; seluruh file telah diterima ke RAM.\n')
        text.configure(state='disabled')
    def close(self):self.closed=True;self.running=False;self.cleanup();self.root.destroy()

if __name__=='__main__':
    mp.freeze_support()
    if os.name!='nt':raise SystemExit('Program ini membutuhkan Windows.')
    App(tk.Tk()).root.mainloop()

