from pathlib import Path
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
import hashlib,json

folder=Path(r'C:\Users\Lenovo Yoga 7i\Documents\PT.SMM\DIGITAL AUTOMATION DEPARTEMENT\DOKUMENTASI DAN NOTE\Dokumentasi\Internal Dokumen')
source=folder/'Pengajuan_Project_Digitalisasi_Dan_Otomatisasi_PT_SMM.docx'
output=folder/'Pengajuan_Project_Digitalisasi_Dan_Otomatisasi_PT_SMM_Ringkas.docx'
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
d=Document();sec=d.sections[0]
sec.page_width=Inches(8.5);sec.page_height=Inches(11)
sec.top_margin=Inches(.75);sec.bottom_margin=Inches(.7);sec.left_margin=sec.right_margin=Inches(.8)
normal=d.styles['Normal'];normal.font.name='Calibri';normal.font.size=Pt(11)
normal.paragraph_format.space_after=Pt(7);normal.paragraph_format.line_spacing=1.1
for name,size in [('Title',19),('Heading 1',12)]:
 s=d.styles[name];s.font.name='Calibri';s.font.size=Pt(size);s.font.color.rgb=RGBColor(0,0,0)
 s.font.bold=True;s.paragraph_format.space_before=Pt(12 if name!='Title' else 0);s.paragraph_format.space_after=Pt(7)
 s.paragraph_format.keep_with_next=True
for name in ['List Bullet','List Number']:
 s=d.styles[name];s.font.name='Calibri';s.font.size=Pt(11)
 s.paragraph_format.space_after=Pt(5);s.paragraph_format.line_spacing=1.1
 s.paragraph_format.keep_together=True
d.core_properties.title='Pengajuan Project Digitalisasi dan Otomatisasi PT SMM'
d.core_properties.author='Adylla Habibie Fachri Ramadhan'
d.core_properties.subject='Tujuan dan rencana pelaksanaan digitalisasi dan otomatisasi'

def p(text,style=None):return d.add_paragraph(text,style)
def h(text):return p(text,'Heading 1')
def bullet(text):return p(text,'List Bullet')
def lead(name,text,style='Normal'):
 para=p('',style);para.add_run(name+': ').bold=True;para.add_run(text);return para

p('Pengajuan Project Digitalisasi\ndan Otomatisasi PT SMM','Title')
p('PT. Sarana Makin Mulya | Padalarang')
for label,value in [('Pengusul','Adylla Habibie Fachri Ramadhan - Digital Automation Departement'),('Sponsor','Direksi'),('Dokumen','001 | Revisi 00 | Pengajuan 26 Oktober 2026')]:
 para=lead(label,value);para.paragraph_format.space_after=Pt(3)

h('1 Tujuan Project')
p('Project ini diajukan untuk menghubungkan data mesin, produksi, engineering, utilitas dan ERP dalam satu sistem. Data aktual ditampilkan di dashboard dan disimpan sebagai historis agar proses bisa dipantau, ditelusuri dan dianalisa berdasarkan data.')
bullet('Setiap batch memiliki record proses mesin, parameter yang digunakan dan hasil produksinya.')
bullet('Mengurangi input manual dan perubahan parameter yang tidak sesuai dengan kebutuhan proses.')
bullet('Mengetahui waktu running, downtime, alarm dan riwayat kerusakan untuk membantu perbaikan serta maintenance.')
bullet('Mengetahui konsumsi listrik, air, steam dan chemical agar penggunaan serta biaya proses bisa dievaluasi.')

h('2 Ruang Lingkup')
p('Cakupan project meliputi mesin produksi dan utilitas PT. SMM. Mesin produksi mencakup Kalender, Jetflow, Calator, Mercerize, Continous, Finish, Setting Dongnam, Inspecting dan Sleeting. Utilitas mencakup boiler, kompresor, cubical, WWTP/IPAL, pompa dan sensor pendukung.')
p('Pekerjaan meliputi pembacaan data controller/PLC dan inverter, penambahan sensor atau gateway, dashboard dan database, integrasi batch dengan ERP, serta pengembangan otomatisasi sesuai kebutuhan mesin. Jumlah unit dan parameter final ditetapkan setelah survei.')

d.add_page_break()
h('3 Rencana Pekerjaan')
lead('Pendataan mesin dan utilitas','Cek controller, sensor, komunikasi dan parameter yang tersedia. Tentukan data yang perlu dibaca serta perangkat tambahan seperti flow meter, power meter atau gateway.')
lead('Monitoring dan historis','Hubungkan data ke dashboard. Simpan nilai aktual, alarm, running dan downtime agar bisa dilihat per mesin, per batch dan per rentang waktu.')
lead('Integrasi planning dan produksi','Hubungkan nomor batch, jenis kain, berat, resep dan hasil QC dengan record proses mesin. Produksi diarahkan berjalan setelah batch terdaftar pada planning, dengan alur yang disesuaikan pada mesin.')
lead('Pengaturan parameter','Siapkan parameter proses berdasarkan jenis kain dan mesin yang digunakan. Perubahan parameter dibatasi sesuai hak akses dan dicatat agar bisa ditelusuri.')
lead('Pengembangan aplikasi utama','Dashboard dikembangkan untuk mencakup fungsi Orgatex pada proses celup dan monitoring mesin sebelum maupun setelah pencelupan. Perpindahan penggunaan dilakukan setelah fungsi terkait diuji.')
lead('Otomatisasi dan utilitas','Otomatiskan pekerjaan manual yang lambat atau berulang. Pengaturan supply utilitas dikembangkan mengikuti kebutuhan aktual mesin agar pemakaiannya lebih efisien.')
lead('Analisa dan AI','Setelah data cukup dan pembacaannya sudah sesuai, kembangkan analisa pola kerusakan, perbandingan hasil produksi dan rekomendasi parameter. Hasil analisa menjadi bahan evaluasi engineering dan produksi.')

h('4 Tahapan Pelaksanaan')
for title,text in [
 ('Survei dan penentuan prioritas','Susun daftar mesin, parameter, kondisi awal dan kebutuhan perangkat.'),
 ('Uji pada area prioritas','Pasang koneksi atau sensor, lalu cocokkan data dashboard dengan pembacaan mesin.'),
 ('Perluasan monitoring','Terapkan sistem pada mesin dan utilitas berikutnya setelah hasil uji sesuai.'),
 ('Integrasi dan otomatisasi','Hubungkan data batch dan ERP, lalu uji pengaturan parameter serta kontrol yang dibutuhkan.'),
 ('Evaluasi dan pengembangan','Bandingkan hasil dengan kondisi awal, lalu lanjutkan analisa dan AI berdasarkan data yang terkumpul.')]:
 lead(title,text,'List Number')
p('Jadwal setiap tahap disusun setelah survei, penentuan prioritas dan persetujuan kebutuhan perangkat. Instalasi dan perubahan program dikoordinasikan dengan produksi dan engineering.')

d.add_page_break()
h('5 Hasil yang Diharapkan dan Pengujian')
bullet('Nilai di dashboard sesuai dengan pembacaan HMI atau alat ukur di mesin. Interval pencatatan disesuaikan dengan kebutuhan proses dan kemampuan koneksi.')
bullet('Historis, trend, alarm, running dan downtime dapat ditelusuri berdasarkan mesin, waktu dan nomor batch.')
bullet('Data batch, planning dan hasil produksi terhubung dengan record mesin. Input resep atau parameter yang diotomatisasi sudah diuji kesesuaiannya.')
bullet('Konsumsi utilitas tercatat dan dapat dibandingkan dengan kondisi awal untuk menilai penggunaan serta biaya proses.')
bullet('Pengguna dapat menjalankan dashboard dan memahami penanganan alarm. Fungsi pembacaan, pengiriman data dan kontrol diuji sebelum digunakan pada produksi.')

h('6 Estimasi Investasi')
p('Estimasi awal investasi adalah Rp1.000.000.000 sampai Rp2.000.000.000. Kebutuhannya meliputi controller/gateway, sensor, meter, jaringan, perangkat pendukung dan pengembangan sistem. Nilai final mengikuti hasil survei, jumlah unit dan rincian perangkat yang disetujui.')
p('Penghematan dan ROI dihitung dari data sebelum dan sesudah penerapan, terutama konsumsi utilitas, downtime, pengulangan proses dan waktu pekerjaan manual. Nilai penghematan belum ditetapkan sebelum data pembanding tersedia.')

h('7 Pelaksanaan dan Persetujuan yang Diajukan')
p('Pelaksanaan dikoordinasikan oleh Digital Automation Departement bersama produksi, engineering, utilitas dan pengelola ERP. Persetujuan yang diajukan meliputi:')
bullet('Akses data produksi dan konsumsi utilitas untuk survei, integrasi dan pembanding hasil.')
bullet('Pengadaan perangkat berdasarkan kebutuhan serta anggaran yang disetujui, termasuk penambahan atau modifikasi controller dan program mesin untuk integrasi.')
bullet('Keterlibatan Digital Automation dalam pemilihan mesin atau controller baru agar tetap bisa diintegrasikan dengan aplikasi utama PT. SMM.')

h('Pengesahan')
t=d.add_table(rows=2,cols=3);t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
labels=['Penyusun','Pemeriksa','Pemberi persetujuan']
names=['Adylla Habibie FR\nKa. Departement DA','Edwin Benedict Abed Nego\nMR','Josef Abed Nego\nBOD']
for i in range(3):
 t.columns[i].width=Inches(2.3)
 for ri,text in [(0,labels[i]),(1,names[i])]:
  c=t.cell(ri,i);c.text=text;c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
  tcPr=c._tc.get_or_add_tcPr();marg=OxmlElement('w:tcMar')
  for side in ['top','left','bottom','right']:
   item=OxmlElement('w:'+side);item.set(qn('w:w'),'100');item.set(qn('w:type'),'dxa');marg.append(item)
  tcPr.append(marg)
  if ri==0:
   shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'F2F2F2');tcPr.append(shade)
  for para in c.paragraphs:
   para.alignment=WD_ALIGN_PARAGRAPH.CENTER;para.paragraph_format.space_after=Pt(2);para.paragraph_format.space_before=Pt(2)
   for run in para.runs:run.font.size=Pt(9);run.bold=ri==0
tblpr=t._tbl.tblPr;borders=OxmlElement('w:tblBorders')
for name in ['top','left','bottom','right','insideH','insideV']:
 e=OxmlElement('w:'+name);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
tblpr.append(borders)

for border in list(d.styles.element.iter(qn('w:pBdr'))):
 border.getparent().remove(border)
d.save(output)
assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
Path(r'D:\File HMI\Analisis\Dokumen_Project\verifikasi_sumber.json').write_text(json.dumps({'source':str(source),'sha256':source_hash,'output':str(output)},indent=2),encoding='utf-8')
print(output)
print('words',sum(len(p.text.split()) for p in d.paragraphs))
