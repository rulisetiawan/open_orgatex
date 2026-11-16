using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Collections.Generic;
using System.Runtime.InteropServices;

// Offline adapter for the locally supplied SETEX BtrieveInterface.dll.
// Only files beneath this tool's directory may be opened or written.
class QueueTool {
 [DllImport("BtrieveInterface.dll", EntryPoint="BTRCALL")]
 static extern short Call(ushort op, [In,Out] byte[] pos, [In,Out] byte[] data, ref int length, [In,Out] byte[] key, byte keyLength, byte keyNo);
 static byte[] pos=new byte[128];
 static void Check(short code,string action){if(code!=0)throw new Exception(action+": Btrieve status "+code);}
 static string Local(string path){string p=Path.GetFullPath(path),root=Path.GetFullPath(AppDomain.CurrentDomain.BaseDirectory);if(!p.StartsWith(root,StringComparison.OrdinalIgnoreCase))throw new Exception("Path outside offline workspace");return p;}
 static void Open(string path){var k=Encoding.Default.GetBytes(Local(path)+"\0");if(k.Length>255)throw new Exception("Path too long");int n=1;Check(Call(0,pos,new byte[1],ref n,k,(byte)k.Length,0),"Open");}
 static void Close(){int n=0;Check(Call(1,pos,null,ref n,null,0,0),"Close");pos=new byte[128];}
 static List<byte[]> Read(byte keyNo){var rows=new List<byte[]>();var k=new byte[255];ushort op=12;while(true){var d=new byte[759];int n=d.Length;short rc=Call(op,pos,d,ref n,k,255,keyNo);if(rc==9)break;Check(rc,"Read key "+keyNo);if(n!=759)throw new Exception("Unexpected record length");rows.Add(d);if(rows.Count>10000)throw new Exception("Too many rows");op=6;}return rows;}
 static string Ref(byte[] b){return Encoding.ASCII.GetString(b,1,6);}
 static void Verify(string path,List<byte[]> wanted){Open(path);try{for(byte key=0;key<5;key++){var got=Read(key);if(got.Count!=wanted.Count)throw new Exception("Count mismatch key "+key);var seen=new HashSet<string>();foreach(var row in got){var match=wanted.SingleOrDefault(x=>Ref(x)==Ref(row));if(match==null||!match.SequenceEqual(row)||!seen.Add(Ref(row)))throw new Exception("Payload mismatch key "+key);}if(key==4){int last=0;foreach(var row in got){int p=BitConverter.ToUInt16(row,757);if(p<=last)throw new Exception("Position order mismatch");last=p;}}} }finally{Close();}}
 static int Main(string[] args){try{
  if(args.Length==2&&args[0]=="inspect"){Open(args[1]);try{for(byte k=0;k<5;k++)Console.WriteLine("key="+k+" refs="+String.Join(",",Read(k).Select(Ref)));}finally{Close();}return 0;}
  if(args.Length==3&&args[0]=="dump"){Open(args[1]);List<byte[]> records;try{records=Read(4);}finally{Close();}File.WriteAllBytes(Local(args[2]),records.SelectMany(x=>x).ToArray());return 0;}
  if(args.Length==4&&args[0]=="merge"){
   string original=Local(args[1]),incoming=Local(args[2]),merged=Local(args[3]);if(File.Exists(merged))throw new Exception("Output already exists");
   Open(original);List<byte[]> old;try{old=Read(4);}finally{Close();}
   byte[] buf=File.ReadAllBytes(incoming);if(buf.Length==0||buf.Length%759!=0||buf.Length/759>200)throw new Exception("Invalid incoming payload");
   var all=new List<byte[]>(old);var added=new List<byte[]>();int next=old.Count==0?0:old.Max(x=>(int)BitConverter.ToUInt16(x,757));
   for(int i=0;i<buf.Length;i+=759){var row=new byte[759];Buffer.BlockCopy(buf,i,row,0,759);if(all.Any(x=>Ref(x)==Ref(row)))throw new Exception("Reference already in queue: "+Ref(row));if(++next>65535)throw new Exception("Queue position overflow");Buffer.BlockCopy(BitConverter.GetBytes((ushort)next),0,row,757,2);added.Add(row);all.Add(row);}
   File.Copy(original,merged);Open(merged);try{foreach(var row in added){int n=759;Check(Call(2,pos,row,ref n,new byte[255],255,0),"Insert merged row");}}finally{Close();}
   Verify(merged,all);Console.WriteLine("OK: preserved "+old.Count+", added "+added.Count+"; verified keys 0-4");return 0;
  }
  if(args.Length!=3)throw new Exception("Usage: QueueTool payloads.bin output.BTD | inspect file.BTD");
  string template=Local(args[0]),payload=Local(args[1]),output=Local(args[2]);
  if(File.Exists(output))throw new Exception("Output already exists");
  byte[] input=File.ReadAllBytes(payload);if(input.Length==0||input.Length%759!=0||input.Length/759>1000)throw new Exception("Invalid payload file");
  var wanted=new List<byte[]>();for(int i=0;i<input.Length;i+=759){var row=new byte[759];Buffer.BlockCopy(input,i,row,0,759);wanted.Add(row);}
  if(wanted.Select(Ref).Distinct().Count()!=wanted.Count)throw new Exception("Duplicate references");
  File.Copy(template,output);Open(output);try{
   int count=0;while(true){var d=new byte[759];int n=759;var key=new byte[255];short rc=Call(12,pos,d,ref n,key,255,0);if(rc==9)break;Check(rc,"Read before delete");n=0;Check(Call(4,pos,null,ref n,key,255,0),"Delete copied row");if(++count>10000)throw new Exception("Deletion limit");}
   foreach(var row in wanted){int n=759;Check(Call(2,pos,row,ref n,new byte[255],255,0),"Insert");}
  }finally{Close();}
  Verify(output,wanted);Console.WriteLine("OK: "+wanted.Count+" records; reopened and verified through keys 0-4");return 0;
 }catch(Exception e){Console.Error.WriteLine(e.Message);return 1;}}
}
