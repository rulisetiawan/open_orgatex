from pathlib import Path, PurePosixPath
import copy, json, struct, unittest
import server, ftp_transfer
from test_export import plan

class FakeFTP:
    def __init__(self):
        self.dirs={'/','/custom','/custom/batches','/custom/queues','/custom/queues/A001'}
        self.queue='/custom/queues/A001/QUEUE.BTD'
        self.files={self.queue:(Path(__file__).parent/'QUEUE.template.BTD').read_bytes()}
        self.actions=[];self.fail_upload=False;self.change=False;self.queue_reads=0;self.fail_publish=False
    def list(self,p):
        if p not in self.dirs:raise ValueError('Missing folder')
        return {PurePosixPath(x).name for x in self.dirs|set(self.files) if x!=p and str(PurePosixPath(x).parent)==p}
    def get(self,p):
        if p==self.queue:
            self.queue_reads+=1
            if self.change and self.queue_reads==2:self.files[p]+=b'CONCURRENT'
        return self.files[p]
    def put(self,p,b):
        if self.fail_upload and p.endswith('.PRG'):raise ValueError('Injected upload failure')
        self.files[p]=b;self.actions.append(('put',p))
    def mkdir(self,p):
        if p in self.dirs or str(PurePosixPath(p).parent) not in self.dirs:raise ValueError('Cannot mkdir')
        self.dirs.add(p);self.actions.append(('mkdir',p))
    def rename(self,a,b):
        if b in self.files or b in self.dirs:raise ValueError('Destination exists')
        if self.fail_publish and '.pending_' in a and b==self.queue:raise ValueError('Injected commit failure')
        if a in self.files:self.files[b]=self.files.pop(a)
        elif a in self.dirs:
            for f in list(self.files):
                if f.startswith(a+'/'):self.files[b+f[len(a):]]=self.files.pop(f)
            self.dirs.remove(a);self.dirs.add(b)
        else:raise ValueError('Missing source')
        self.actions.append(('rename',a,b))
    def remove(self,p):del self.files[p];self.actions.append(('delete',p))
    def rmdir(self,p):self.dirs.remove(p);self.actions.append(('rmdir',p))
    def close(self):pass

def payload(action='send'):
    return dict(action=action,plans=[plan('800001','A001','FTP-TEST')],writersPaused=True,referencesReserved=True,ftp=dict(host='example.invalid',port=21,username='test',password='DO-NOT-LOG',batchRoot='/custom/batches',queuePath='/custom/queues/{machine}/QUEUE.BTD',tls=False))

class FTPTests(unittest.TestCase):
    def run_transfer(self,store,p=None):return ftp_transfer.transfer(p or payload(),server.prepare,lambda c:store)
    def test_check_readonly(self):
        f=FakeFTP();before=copy.deepcopy(f.files);r=self.run_transfer(f,payload('check'))
        self.assertEqual(f.actions,[]);self.assertEqual(f.files,before);self.assertEqual(r['existing'],2)
    def test_merge_preserves_and_backup(self):
        f=FakeFTP();original=f.files[f.queue];r=self.run_transfer(f)
        self.assertTrue(r['committed']);self.assertEqual(f.files[r['backup']],original);self.assertNotEqual(f.files[f.queue],original)
        self.assertIn('/custom/batches/800001/BATCHREF.REF',f.files);self.assertIn('/custom/batches/800001/M_0502.PRG',f.files)
        self.assertNotIn('/custom/queues/A001/.planner-transfer.lock',f.dirs)
        # Read exported queue through native engine and compare existing payloads byte for byte.
        root=Path(__file__).parent/'jobs';root.mkdir(exist_ok=True)
        import tempfile
        with tempfile.TemporaryDirectory(dir=root) as t:
            p=Path(t);(p/'q.BTD').write_bytes(f.files[f.queue]);ftp_transfer.native(['dump',p/'q.BTD',p/'records'])
            b=(p/'records').read_bytes();self.assertEqual(len(b),3*759)
            self.assertEqual(b[:759],original[0x2406:0x2406+759]);self.assertEqual(b[759:1518],original[0x2006:0x2006+759]);self.assertEqual(struct.unpack_from('<H',b,1518+757)[0],3)
    def test_duplicate_folder_and_ref(self):
        f=FakeFTP();f.dirs.add('/custom/batches/800001')
        with self.assertRaisesRegex(ValueError,'Folder referensi'):self.run_transfer(f)
        f=FakeFTP();p=payload();p['plans'][0]['reference']='062232'
        with self.assertRaisesRegex(ValueError,'Reference already'):self.run_transfer(f,p)
    def test_concurrent_change_aborts(self):
        f=FakeFTP();original=f.files[f.queue];f.change=True
        with self.assertRaisesRegex(ValueError,'Queue berubah'):self.run_transfer(f)
        self.assertEqual(f.files[f.queue],original+b'CONCURRENT')
        self.assertFalse(any(x[0]=='rename' and x[1]==f.queue for x in f.actions))
    def test_failed_upload_preserves_queue(self):
        f=FakeFTP();original=f.files[f.queue];f.fail_upload=True
        with self.assertRaises(ValueError):self.run_transfer(f)
        self.assertEqual(f.files[f.queue],original)
    def test_commit_failure_restores_original(self):
        f=FakeFTP();original=f.files[f.queue];f.fail_publish=True
        with self.assertRaises(ValueError):self.run_transfer(f)
        self.assertEqual(f.files[f.queue],original)
    def test_guards(self):
        for flag in ['writersPaused','referencesReserved']:
            p=payload();p[flag]=False;f=FakeFTP()
            with self.assertRaises(ValueError):self.run_transfer(f,p)
            self.assertFalse(f.actions)
        p=payload();p['plans'].append(plan('800002','E013','SECOND'))
        with self.assertRaisesRegex(ValueError,'satu mesin'):self.run_transfer(FakeFTP(),p)
        p=payload();p['ftp']['queuePath']='/x/../QUEUE.BTD'
        with self.assertRaises(ValueError):self.run_transfer(FakeFTP(),p)
    def test_wrong_machine(self):
        p=payload();p['plans'][0]['machine']='E013';p['ftp']['queuePath']='/custom/queues/A001/QUEUE.BTD'
        with self.assertRaisesRegex(ValueError,'mesin lain'):self.run_transfer(FakeFTP(),p)
    def test_missing_queue(self):
        f=FakeFTP();f.files.clear()
        with self.assertRaisesRegex(ValueError,'belum tersedia'):self.run_transfer(f)
        self.assertFalse(f.actions)

if __name__=='__main__':unittest.main()
