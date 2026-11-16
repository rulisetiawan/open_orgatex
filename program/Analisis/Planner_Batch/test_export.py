from pathlib import Path
import base64, copy, hashlib, io, json, struct, unittest, zipfile
import server

ROOT=Path(__file__).parent
STATE=json.loads((ROOT/'data.json').read_text('utf-8'))
SOURCE=base64.b64decode(STATE['batchSource'])
PROGRAM=STATE['templates'][0]['base64']

def plan(ref='800001',machine='E013',batch='TEST-001'):
    return dict(reference=ref,machine=machine,batch=batch,program=PROGRAM,batchSource=STATE['batchSource'],texts=[server.text(SOURCE[28+i*21:49+i*21]) for i in range(20)],parameters=list(struct.unpack_from('<20f',SOURCE,448)),batchConfig=2,queueConfig=0)

class ExportTests(unittest.TestCase):
    def test_multi_machine_and_payload(self):
        plans=[plan('800001','E013','NEW-ONE'),plan('800003','A001','NEW-TWO'),plan('800002','E013','NEW-THREE')]
        before=hashlib.sha256((ROOT/'QUEUE.template.BTD').read_bytes()).hexdigest()
        data=server.export({'plans':plans})
        z=zipfile.ZipFile(io.BytesIO(data));manifest=json.loads(z.read('planning-manifest.json'))
        self.assertEqual(len(manifest['queue_checks']),2)
        self.assertEqual([e['position'] for e in manifest['entries']],[1,1,2])
        self.assertEqual(hashlib.sha256((ROOT/'QUEUE.template.BTD').read_bytes()).hexdigest(),before)
        for p in plans:
            b=z.read('OT/BATCH/'+p['reference']+'/BATCHREF.REF')
            self.assertEqual(len(b),762);self.assertEqual(server.text(b[1:8]),p['reference'])
            self.assertEqual(server.text(b[748:753]),p['machine']);self.assertEqual(server.text(b[28:49]),p['batch'])
            self.assertEqual(b[8:26],bytes(18));self.assertEqual(b[528:608],bytes(80));self.assertEqual(b[688:748],bytes(60));self.assertEqual(b[608:688],SOURCE[608:688])
            self.assertEqual(struct.unpack_from('<HHHHB',b,753),(1,2,0,502,0))
            self.assertEqual(z.read('OT/BATCH/'+p['reference']+'/M_0502.PRG'),base64.b64decode(PROGRAM))
        for name,digest in manifest['files_sha256'].items(): self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),digest)
        (ROOT/'test_multi_machine.zip').write_bytes(data)
    def test_rejections(self):
        for change in [dict(reference='../../'),dict(machine='../X'),dict(reference='062277'),dict(batch=''),dict(batchConfig=-1),dict(queueConfig=1.5),dict(parameters=[float('nan')]*20),dict(program=base64.b64encode(b'bad').decode()),dict(texts=['X'*30]*20)]:
            p=plan();p.update(change)
            with self.assertRaises((ValueError,KeyError)): server.prepare([p])
        with self.assertRaises(ValueError):server.prepare([plan(),plan()])
        bad=bytearray(base64.b64decode(PROGRAM));bad[384+65+4:384+65+6]=b'\xff\xff'
        p=plan();p['program']=base64.b64encode(bad).decode()
        with self.assertRaises(ValueError):server.prepare([p])
    def test_all_builtin_programs(self):
        for template in STATE['templates']:
            info=server.validate_prg(base64.b64decode(template['base64']))
            self.assertEqual(info[0],template['id'])
    def test_duplicate_secondary_keys(self):
        p=plan();p2=plan('800002',batch='TEST-002');p2['texts'][2]=p['texts'][2]
        self.assertTrue(server.export({'plans':[p,p2]}).startswith(b'PK'))

if __name__=='__main__':unittest.main()
