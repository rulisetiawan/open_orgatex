(function(root){
'use strict';
const bytes=hex=>Uint8Array.from(hex.match(/../g)||[],v=>parseInt(v,16));
const hex=b=>Array.from(b,v=>v.toString(16).padStart(2,'0')).join('');
const view=b=>new DataView(b.buffer,b.byteOffset,b.byteLength);
const clone=o=>JSON.parse(JSON.stringify(o));
function text(b,start,end){let s='';for(let i=start;i<end&&b[i];i++)s+=String.fromCharCode(b[i]);return s;}
function ascii(s,max,label){if(typeof s!=='string'||s.length>max||/[^\x20-\x7e]/.test(s))throw Error(label+' harus berisi maksimal '+max+' karakter ASCII.');}
function parse(input,filename='program.PRG'){
 const b=typeof input==='string'?bytes(input):new Uint8Array(input),d=view(b);
 if(b.length<384||(b.length-384)%65||hex(b.slice(0,4))!=='508fc2f5')throw Error('Format PRG tidak sesuai template SECOM yang didukung.');
 const n=d.getUint16(33,true);if(!n)throw Error('Program tidak mempunyai langkah.');
 const steps=Array.from({length:n},()=>({records:[]}));
 for(let off=384;off<b.length;off+=65){const raw=b.slice(off,off+65),v=view(raw),step=v.getUint16(0,true),line=raw[2];
  if(step<1||step>n)throw Error('Nomor langkah di luar header.');
  steps[step-1].records.push({raw:hex(raw),line,functionId:line?v.getUint16(4,true):null,values:line?Array.from({length:6},(_,i)=>v.getFloat32(9+i*6,true)):[],comment:line?null:text(raw,3,65)});
 }
 if(steps.some(s=>!s.records.length||s.records.filter(r=>r.line===1).length!==1))throw Error('Setiap langkah harus memiliki tepat satu fungsi utama.');
 return {version:1,filename,header:hex(b.slice(0,384)),programId:d.getUint16(8,true),title:text(b,10,31),steps};
}
function definition(data,id){return data.functions[String(id)];}
function defaults(data,id,line){
 const f=definition(data,id);if(!f)throw Error('Fungsi tidak ditemukan pada CNF lokal.');
 const raw=new Uint8Array(65),v=view(raw);raw[2]=line;v.setUint16(4,id,true);raw[6]=f.ack;
 const values=Array(6).fill(0);f.parameters.forEach((p,i)=>{values[i]=Math.fround(p.default);v.setFloat32(9+i*6,values[i],true);});
 return {raw:hex(raw),line,functionId:Number(id),values,comment:null};
}
function comments(step){return step.records.filter(r=>r.line===0).map(r=>r.comment).join(' / ');}
function setComment(step,value){
 ascii(value,61,'Komentar');const existing=step.records.filter(r=>r.line===0);
 if(existing.length>1)throw Error('Langkah ini memiliki beberapa record komentar; pertahankan melalui template.');
 if(!value){step.records=step.records.filter(r=>r.line!==0);return;}
 if(existing.length){existing[0].comment=value;return;}
 const b=new Uint8Array(65);step.records.unshift({raw:hex(b),line:0,functionId:null,values:[],comment:value});
}
function allowed(data,id,line){const f=definition(data,id);return !!f&&f.lines.includes(Number(line));}
function validate(model,data){
 const errors=[],notes=[];
 try{ascii(model.title,20,'Nama program');}catch(e){errors.push(e.message);}
 if(!model.title.trim())errors.push('Nama program belum diisi.');
 if(!Number.isInteger(model.programId)||model.programId<1||model.programId>9999)errors.push('ID program harus bilangan bulat 1–9999.');
 if(!model.steps.length||model.steps.length>65535)errors.push('Jumlah langkah tidak valid.');
 model.steps.forEach((step,si)=>{
  const label='Langkah '+(si+1),seen=new Set();
  if(step.records.filter(r=>r.line===1).length!==1)errors.push(label+': perlu tepat satu fungsi utama.');
  for(const r of step.records){
   const raw=bytes(r.raw);if(raw.length!==65){errors.push(label+': ukuran record tidak valid.');continue;}
   if(!r.line){if(r.comment!==text(raw,3,65))try{ascii(r.comment,61,'Komentar '+label);}catch(e){errors.push(e.message);}continue;}
   if(seen.has(r.line))errors.push(label+': slot '+r.line+' digunakan lebih dari sekali.');seen.add(r.line);
   if(!Number.isInteger(r.line)||r.line<1||r.line>13)errors.push(label+': slot tidak valid.');
   if(r.values.length!==6){errors.push(label+': perlu enam slot nilai.');continue;}
   const f=definition(data,r.functionId),original=view(raw),isOriginal=original.getUint16(4,true)===r.functionId&&raw[2]===r.line;
   if(!f){notes.push(label+': fungsi '+r.functionId+' belum ada dalam CNF; record dipertahankan.');}
   else if(!allowed(data,r.functionId,r.line)){notes.push(label+': fungsi '+f.name+' tidak tercantum pada resource slot '+r.line+' di CNF.');}
   r.values.forEach((value,i)=>{
    if(typeof value!=='number'||!Number.isFinite(value)||!Number.isFinite(Math.fround(value))){errors.push(label+': nilai P'+(i+1)+' tidak valid.');return;}
    const changed=!isOriginal||!Object.is(value,original.getFloat32(9+i*6,true));
    const p=f?.parameters[i];if(!p)return;
    const pd=data.parameters[String(p.definition_id)];
    const issue=[];
    if(!p.index_min&&value<p.minimum-1e-6)issue.push('minimal '+p.minimum);
    if(!p.index_max&&value>p.maximum+1e-6)issue.push('maksimal '+Number(p.maximum.toPrecision(7)));
    const choices=choicesFor(data,pd);
    if(choices.length&&!choices.some(x=>x.value===value))issue.push('pilih nilai dari daftar CNF');
    if(issue.length)(changed?errors:notes).push(label+' · '+pd.name+': '+issue.join(', ')+(changed?'':' (nilai asli template)'));
   });
  }
 });
 const main=s=>s?.records.find(r=>r.line===1)?.functionId;
 if(main(model.steps[0])!==1)errors.push('Langkah pertama harus Program Start (ID 1).');
 if(main(model.steps.at(-1))!==2)errors.push('Langkah terakhir harus Program End (ID 2).');
 return {errors:[...new Set(errors)],notes:[...new Set(notes)]};
}
function serialize(model,data){
 const check=validate(model,data);if(check.errors.length)throw Error(check.errors.slice(0,8).join('\n'));
 const header=bytes(model.header);if(header.length!==384)throw Error('Header template tidak valid.');
 const h=view(header);if(h.getUint16(8,true)!==model.programId)h.setUint16(8,model.programId,true);
 if(text(header,10,31)!==model.title){header.fill(0,10,31);for(let i=0;i<model.title.length;i++)header[10+i]=model.title.charCodeAt(i);}
 h.setUint16(33,model.steps.length,true);
 const rows=[];
 model.steps.forEach((step,si)=>{for(const r of step.records){const raw=bytes(r.raw),d=view(raw);d.setUint16(0,si+1,true);
  if(r.line===0){if(r.comment!==text(raw,3,65)){raw.fill(0,3);for(let i=0;i<r.comment.length;i++)raw[3+i]=r.comment.charCodeAt(i);}}
  else{if(raw[2]!==r.line||d.getUint16(4,true)!==r.functionId)throw Error('Gunakan record fungsi baru saat mengganti fungsi.');
   for(let i=0;i<6;i++)if(!Object.is(r.values[i],d.getFloat32(9+i*6,true)))d.setFloat32(9+i*6,r.values[i],true);
  }rows.push(raw);
 }});
 const out=new Uint8Array(384+rows.length*65);out.set(header);rows.forEach((b,i)=>out.set(b,384+i*65));return out;
}
function choicesFor(data,pd){return pd&&pd.scale.mode===16?(data.text_choices[String(pd.scale2.text_group)]||[]):[];}
function newStep(data,id=3){return {records:[defaults(data,id,1)]};}
const api={bytes,hex,view,clone,text,parse,definition,defaults,comments,setComment,allowed,validate,serialize,choicesFor,newStep};
root.PRG=api;if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
