from pathlib import Path
import json,base64,struct,hashlib

HERE=Path(__file__).parent
ROOT=HERE.parents[1]
analysis=ROOT/'Analisis'
schema=json.loads((analysis/'TYPECONF_functions_parameters.json').read_text(encoding='utf-8'))
rawrecords=json.loads((analysis/'TYPECONF_records_decoded.json').read_text(encoding='utf-8'))['records']
funcs=schema['functions'];resources={};groups=[]
for x in rawrecords:
    b=bytes.fromhex(x['raw_hex']);key=x['key'];name=b[27:48].split(b'\0')[0].decode('cp437')
    if key[0]==78:
        resources[str(key[2])]={'id':key[2],'name':name,'type':struct.unpack_from('<H',b,71)[0],'disabled':bool(b[76])}
    if key[0]==1:
        count=b[76]
        groups.append({'name':name,'line':b[75],'disabled':bool(b[98]),'ids':list(struct.unpack_from('<8H',b,77))[:count]})
for id,f in funcs.items():
    f['lines']=sorted({g['line'] for g in groups if not g['disabled'] and int(id) in g['ids']})
    f['groups']=[g['name'] for g in groups if not g['disabled'] and int(id) in g['ids']]
templates=[];observed={}
for p in sorted((ROOT/'Storage/SC777CE/Programs').glob('*.PRG')):
    b=p.read_bytes();title=b[10:31].split(b'\0')[0].decode('cp437')
    templates.append({'filename':p.name,'title':title,'id':struct.unpack_from('<H',b,8)[0],
                      'steps':struct.unpack_from('<H',b,33)[0],'base64':base64.b64encode(b).decode(),
                      'sha256':hashlib.sha256(b).hexdigest()})
    for off in range(384,len(b),65):
        line=b[off+2]
        if line:observed.setdefault(str(struct.unpack_from('<H',b,off+4)[0]),set()).add(line)
for id,lines in observed.items():
    if id in funcs:funcs[id]['lines']=sorted(set(funcs[id]['lines'])|lines)
data={'templates':templates,'functions':funcs,'parameters':schema['parameters'],'resources':resources,
      'groups':groups,'text_choices':schema['text_choices'],
      'cnf_sha256':hashlib.sha256((ROOT/'Storage/SC777CE/Config/TYPECONF.CNF').read_bytes()).hexdigest(),
      'date':'29 Oktober 2026'}
(HERE/'data.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
template=(HERE/'template.html').read_text(encoding='utf-8')
payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
result=template.replace('/*__ENGINE__*/',(HERE/'engine.js').read_text(encoding='utf-8')).replace('/*__APP__*/',(HERE/'app.js').read_text(encoding='utf-8')).replace('/*__DATA__*/',payload)
(analysis/'Editor_PRG.html').write_text(result,encoding='utf-8')
print(json.dumps({'output':str(analysis/'Editor_PRG.html'),'templates':len(templates),'functions':len(funcs),'selectable_functions':sum(bool(f['lines']) for f in funcs.values()),'bytes':len(result.encode())},indent=2))
