"""Read-only CNF fragment and RLE reconstruction, derived from local HMI DLL."""
from pathlib import Path
import struct, re, json, hashlib, math

ROOT=Path(r'D:\File HMI')
CNF=ROOT/'Storage/sc777ce/Config/TYPECONF.CNF'
OUT=ROOT/'Analisis'

class CNFReader:
    def __init__(self,path):
        self.path=Path(path);self.data=self.path.read_bytes();self.fragments={};self.offsets={}
        for page in range(1,len(self.data)//512):
            p=self.data[page*512:(page+1)*512]
            n=struct.unpack_from('<H',p,10)[0]
            if not 0<n<100:continue
            offsets=[struct.unpack_from('<H',p,510-i*2)[0] for i in range(n+1)]
            valid=[x&0x7fff for x in offsets if x!=65535]
            if not valid or any(not 12<=x<=512-2*(n+1) for x in valid):continue
            for slot in range(n):
                try:
                    frag=self.fragment(page,slot)
                    if frag['data']:
                        self.fragments[page,slot]=frag
                        self.offsets[frag['offset']]=(page,slot)
                except (ValueError,struct.error):pass

    def fragment(self,page,slot):
        p=self.data[page*512:(page+1)*512]
        if len(p)!=512:raise ValueError('page outside file')
        n=struct.unpack_from('<H',p,10)[0]
        if not 0<=slot<n<100:raise ValueError('slot')
        a=struct.unpack_from('<H',p,510-slot*2)[0]
        if a==65535:raise ValueError('unused slot')
        start=a&32767
        end=None
        for j in range(slot+1,n+1):
            z=struct.unpack_from('<H',p,510-j*2)[0]
            if z!=65535:end=z&32767;break
        if end is None or not 12<=start<end<=512-2*(n+1):raise ValueError('bounds')
        nxt=None
        if a&32768:
            link=p[start:start+4]
            nxt=(int.from_bytes(link[1:3],'little')+link[0]*65536,link[3])
            start+=4
        return {'offset':page*512+start,'data':p[start:end],'next':nxt,'page':page,'slot':slot}

    def chain(self,page,slot):
        packed=bytearray();trace=[];seen=set()
        while True:
            if (page,slot) in seen:raise ValueError('fragment loop')
            seen.add((page,slot));f=self.fragment(page,slot)
            packed+=f['data'];trace.append({k:v for k,v in f.items() if k!='data'})
            if not f['next'] or f['next'][1]==255:break
            page,slot=f['next']
        return bytes(packed),trace

    @staticmethod
    def decompress(packed):
        p=0;out=bytearray();repeat=False;runs=[]
        while p<len(packed):
            if p+2>len(packed):raise ValueError(('incomplete count',p,len(packed)))
            n=struct.unpack_from('<H',packed,p)[0];p+=2
            need=1 if repeat else n
            if p+need>len(packed):raise ValueError(('truncated',p,n,repeat,len(packed)))
            value=packed[p:p+need];out+=value*n if repeat else value;p+=need
            runs.append((repeat,n,value.hex()))
            if len(out)>65536:raise ValueError('oversize')
            repeat=not repeat
        return bytes(out),runs

    def candidates(self,kind,index):
        key=struct.pack('<3H',kind,0,index);results=[]
        for m in re.finditer(re.escape(key),self.data):
            address=self.offsets.get(m.start()-2)
            if address is None:continue
            try:
                packed,trace=self.chain(*address);raw,runs=self.decompress(packed)
                if len(raw)!=290 or raw[:6]!=key:continue
                results.append({'raw':raw,'packed':packed,'runs':runs,'trace':trace})
            except (ValueError,struct.error):pass
        return results

def txt(b):return b.split(b'\0',1)[0].decode('cp857',errors='replace').strip()

def function(raw):
    n=raw[80]
    if n>6:raise ValueError('parameter count')
    p=[]
    for i in range(n):
        vals=struct.unpack_from('<HBfffHHBH',raw,81+i*22)
        p.append(dict(zip(['definition_id','display_position','minimum','maximum','default','index_min','index_max','attribute','reserved'],vals)))
    return {'id':struct.unpack_from('<H',raw,4)[0],'name_local':txt(raw[6:27]),'name':txt(raw[27:48]),
            'ack':raw[74],'type':raw[75],'parameter_count':n,'parameters':p}

def parameter(raw):
    scale=struct.unpack_from('<BB6fB',raw,70)
    return {'id':struct.unpack_from('<H',raw,4)[0],'name_local':txt(raw[6:27]),'name':txt(raw[27:48]),
            'unit_local':raw[48:59].split(b'\0',1)[0].decode('cp437',errors='replace').strip(),
            'unit':raw[59:70].split(b'\0',1)[0].decode('cp437',errors='replace').strip(),
            'scale':dict(zip(['digits_before','digits_after','factor','offset','x1','x2','y1','y2','mode'],scale)),
            'attribute':struct.unpack_from('<H',raw,97)[0],
            'scale2':dict(zip(['text_group','basetype','index_factor','index_offset','reserved1','reserved2'],struct.unpack_from('<6H',raw,101)))}

if __name__=='__main__':
    c=CNFReader(CNF)
    print('fragments',len(c.fragments))
    for kind,ids in [(3,[1,2,71,122,126,141,144,237,238,261,404,712,713,716,717,718,720,747,938,939]),(2,[1,2,3,4,5,6,7,9,16,18,22,36,53,60,73,75,83,84,134,135,136,137,138,154,155,156,157,158,174,175,176,177,178,296,298])]:
        for index in ids:
            found=c.candidates(kind,index)
            if len(found)!=1:print('MISSING/AMBIGUOUS',kind,index,len(found));continue
            r=found[0];v=function(r['raw']) if kind==3 else parameter(r['raw'])
            print(kind,index,v)
