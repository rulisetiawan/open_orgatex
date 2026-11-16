"""Real ftplib transport against a loopback-only in-memory FTP fixture."""
import socket, socketserver, threading, unittest
from pathlib import PurePosixPath
from test_ftp import FakeFTP, payload
import ftp_transfer, server

class Session(socketserver.StreamRequestHandler):
    def reply(self,s):self.wfile.write((s+'\r\n').encode());self.wfile.flush()
    def handle(self):
        self.cwd='/';self.passive=None;self.rename_from=None;self.reply('220 Local test FTP')
        try:
            while True:
                line=self.rfile.readline().decode().rstrip('\r\n')
                if not line:break
                cmd,_,arg=line.partition(' ');f=self.server.store
                try:
                    if cmd=='USER':self.reply('331 Password required')
                    elif cmd=='PASS':self.reply('230 Logged in')
                    elif cmd=='TYPE':self.reply('200 Type set')
                    elif cmd=='CWD':f.list(arg);self.cwd=arg;self.reply('250 Directory changed')
                    elif cmd=='PASV':
                        self.passive=socket.socket();self.passive.bind(('127.0.0.1',0));self.passive.listen(1);port=self.passive.getsockname()[1];self.reply(f'227 Entering Passive Mode (127,0,0,1,{port//256},{port%256})')
                    elif cmd in ('NLST','RETR','STOR'):
                        self.reply('150 Transfer starting');conn,_=self.passive.accept();self.passive.close();self.passive=None
                        with conn:
                            if cmd=='NLST':conn.sendall(('\r\n'.join(sorted(f.list(arg or self.cwd)))+'\r\n').encode())
                            elif cmd=='RETR':conn.sendall(f.get(arg))
                            else:
                                data=bytearray()
                                while True:
                                    b=conn.recv(65536)
                                    if not b:break
                                    data.extend(b)
                                f.put(arg,bytes(data))
                        self.reply('226 Transfer complete')
                    elif cmd=='MKD':f.mkdir(arg);self.reply('257 Directory created')
                    elif cmd=='RMD':f.rmdir(arg);self.reply('250 Removed')
                    elif cmd=='DELE':f.remove(arg);self.reply('250 Deleted')
                    elif cmd=='RNFR':self.rename_from=arg;self.reply('350 Rename destination required')
                    elif cmd=='RNTO':f.rename(self.rename_from,arg);self.reply('250 Renamed')
                    elif cmd=='QUIT':self.reply('221 Bye');break
                    else:self.reply('502 Unsupported')
                except Exception:self.reply('550 Test filesystem operation failed')
        finally:
            if self.passive:self.passive.close()

class TransportTest(unittest.TestCase):
    def test_real_ftp_roundtrip(self):
        with socketserver.TCPServer(('127.0.0.1',0),Session) as ftp:
            ftp.store=FakeFTP();thread=threading.Thread(target=ftp.serve_forever,daemon=True);thread.start()
            try:
                p=payload('check');p['ftp']['host']='127.0.0.1';p['ftp']['port']=ftp.server_address[1]
                before=dict(ftp.store.files);r=ftp_transfer.transfer(p,server.prepare);self.assertEqual(ftp.store.files,before);self.assertEqual(r['existing'],2)
                p['action']='send';r=ftp_transfer.transfer(p,server.prepare);self.assertTrue(r['committed']);self.assertEqual(ftp.store.files[r['backup']],before[ftp.store.queue])
                self.assertIn('/custom/batches/800001/M_0502.PRG',ftp.store.files)
            finally:ftp.shutdown();thread.join()

if __name__=='__main__':unittest.main()
