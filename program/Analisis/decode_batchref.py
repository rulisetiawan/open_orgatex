from pathlib import Path
import struct,json,hashlib,csv
ROOT=Path(r'D:\File HMI')
OUT=ROOT/'Analisis'
def text(b):return b.split(b'\0',1)[0].decode('cp1252',errors='replace').strip()
def decode(p):
 b=p.read_bytes()
 if len(b)<759 or (len(b)-759)%3:return {'path':str(p),'length':len(b),'layout_matches':False}
 ref=text(b[1:8]);prg=struct.unpack_from('<H',b,26)[0]
 programs=[{'number':n,'type':t} for n,t in struct.iter_unpack('<HB',b[759:])]
 return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'length':len(b),'layout_matches':True,
 'reference':ref,'state_raw':b[0],'program_no':prg,'machine':text(b[748:753]),
 'texts':{str(i+1):text(b[28+i*21:49+i*21]) for i in range(20)},
 'parameters_raw_float':list(struct.unpack_from('<20f',b,448)),
 'host_batch':struct.unpack_from('<H',b,753)[0],'host_config_no':struct.unpack_from('<H',b,755)[0],
 'position':struct.unpack_from('<H',b,757)[0],'program_list':programs,
 'sibling_program_files':[x.name for x in p.parent.glob('*.PRG')],
 'folder_matches_reference':p.parent.name==ref}
records=[decode(p) for folder in ['Storage/SC777CE/BATCH','Network/F/OT/BATCH'] for p in sorted((ROOT/folder).rglob('BATCHREF.REF'))]
(OUT/'BATCHREF_decoded.json').write_text(json.dumps({'basis':'Candidate layout from decompiled T_BATCH_HEADER_ELEMENT (759 bytes) + T_PROG_LIST_ELEMENT (3 bytes). Static validation only; field units depend on machine configuration.','records':records},ensure_ascii=False,indent=2),encoding='utf-8')
for r in records:
 if '\\Storage\\' in r['path']:print(json.dumps({k:r.get(k) for k in ['reference','length','state_raw','program_no','machine','texts','parameters_raw_float','program_list','sibling_program_files']},ensure_ascii=False))
print('TOTAL',len(records),'LAYOUT_MATCH',sum(r['layout_matches'] for r in records),'FOLDER_MATCH',sum(r.get('folder_matches_reference',False) for r in records))
