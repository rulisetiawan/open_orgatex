from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from copy import deepcopy
import hashlib,json

base=Path(r'C:\Users\Lenovo Yoga 7i\Documents\PT.SMM\DIGITAL AUTOMATION DEPARTEMENT\DOKUMENTASI DAN NOTE\Dokumentasi\Internal Dokumen')
src=base/'Pengajuan_Project_Digitalisasi_Dan_Otomatisasi_PT_SMM.docx'
out=base/'Pengajuan_Project_Digitalisasi_Dan_Otomatisasi_PT_SMM_Dilengkapi.docx'
work=Path(r'D:\File HMI\Analisis\Dokumen_Project')
original=Document(src);d=Document(src);source_hash=hashlib.sha256(src.read_bytes()).hexdigest()

fill={
27:'Direksi, MR, Digital Automation Departement, produksi, engineering, utilitas dan bagian pengelola ERP yang berkaitan dengan pelaksanaan project.',
161:'Pengembangan system diarahkan untuk membantu pekerjaan operator, engineering dan bagian administrasi. Pekerjaan input, pencatatan dan pemantauan yang berulang dibuat otomatis agar karyawan bisa lebih fokus pada proses produksi, pemeriksaan hasil dan penyelesaian masalah.',
163:'Operator diberikan pelatihan penggunaan dashboard dan input batch. Engineering mempelajari pembacaan trend, alarm dan komunikasi controller. Digital Automation mengembangkan integrasi bersama bagian terkait agar system yang dibuat sesuai dengan kebutuhan pekerjaan sehari hari.',
165:'Pemakaian listrik, air, steam, udara bertekanan dan utilitas lainnya dicatat sesuai titik pemakaiannya. Data tersebut menjadi acuan untuk melihat pemborosan, membandingkan konsumsi antar proses dan menentukan pengaturan supply berdasarkan kebutuhan actual mesin.',
167:'System perlu memiliki backup data dan program agar proses bisa dipulihkan ketika terjadi gangguan. Pengadaan perangkat mengikuti kebutuhan mesin dan ketersediaan pengganti, sehingga kerusakan satu perangkat tidak menghambat keseluruhan pengembangan.',
169:'Pengembangan dimulai dari pendataan dan monitoring, dilanjutkan integrasi batch dan ERP, lalu otomatisasi parameter serta utilitas. Analisa AI dikembangkan setelah data actual dan historical sudah tersedia dan pembacaannya sudah sesuai.',
173:'Project menjadi dasar pelaksanaan digitalisasi dan otomatisasi mesin serta utilitas PT. SMM. Pekerjaan dilakukan bertahap berdasarkan prioritas kebutuhan, hasil survei dan persetujuan perusahaan terhadap perangkat maupun perubahan yang diperlukan.',
175:'Sponsor project adalah Direksi dan manajer project adalah Adylla Habibie Fachri Ramadhan. Digital Automation Departement mengkoordinasikan pengembangan dengan produksi, engineering, utilitas dan pengelola ERP sesuai pekerjaan yang sedang dilakukan.',
177:'Pelaksana (R) adalah Digital Automation bersama bagian terkait. Penanggung jawab (A) adalah manajer project. Bagian yang dikonsultasikan (C) adalah produksi, engineering, utilitas dan pengelola ERP. Direksi dan MR menerima informasi perkembangan serta kebutuhan keputusan (I).',
179:'Produksi menyampaikan kebutuhan proses dan hasil produksi. Engineering membantu pemeriksaan mesin dan controller. Utilitas menyediakan data konsumsi serta kebutuhan supply. Pengelola ERP membantu integrasi data administrasi, sedangkan vendor dilibatkan sesuai kebutuhan perangkat dan pekerjaan.',
181:'Keputusan teknis dikoordinasikan oleh manajer project bersama bagian terkait. Kebutuhan biaya, perubahan cakupan dan pekerjaan yang mempengaruhi operasional diajukan kepada pihak yang berwenang. Kendala yang tidak dapat diselesaikan pada pelaksanaan disampaikan kepada Direksi dan MR.',
183:'Tahapan persetujuan meliputi penentuan prioritas, kebutuhan perangkat dan biaya, hasil uji, lalu penerapan pada produksi. Setiap tahap diperiksa sebelum dilanjutkan agar pekerjaan yang belum sesuai tidak langsung diperluas ke mesin lainnya.',
189:'System harus membantu pemantauan dan pekerjaan actual di lapangan. Data yang ditampilkan mudah dipahami, dapat ditelusuri per mesin dan batch, serta dapat digunakan oleh management, produksi, engineering dan utilitas sesuai kebutuhan dan hak aksesnya.',
191:'Fungsi utama meliputi pembacaan nilai actual, penyimpanan historical, trend, alarm, data batch, integrasi ERP dan pengiriman parameter. System juga perlu memiliki backup, hak akses, pencatatan perubahan dan penanganan ketika komunikasi atau perangkat mengalami gangguan.',
193:'Hasil kerja berupa daftar mesin dan parameter, koneksi data, dashboard, database, integrasi batch, program kontrol yang diperlukan dan dokumentasi. Hasil diterima setelah pembacaan sesuai HMI atau alat ukur, data tersimpan dan fungsi yang diterapkan sudah diuji bersama pengguna terkait.',
195:'Pekerjaan dibagi menjadi survei dan pendataan, penentuan perangkat, pemasangan, pembacaan data, pembuatan dashboard dan database, integrasi ERP, otomatisasi, pengujian dan pelatihan. Pembagian ini digunakan untuk menentukan kebutuhan biaya, pelaksana dan urutan pekerjaan.',
197:'Pelaksanaan bergantung pada kondisi controller, ketersediaan dokumentasi, sensor, jaringan, data ERP dan waktu akses ke mesin. Setiap parameter yang digunakan harus memiliki sumber data, satuan dan fungsi yang jelas agar hasil pembacaan maupun pengiriman datanya dapat ditelusuri.',
204:'Perangkat disesuaikan dengan kondisi setiap mesin. Controller atau inverter yang sudah mendukung komunikasi dimanfaatkan terlebih dahulu. Sensor, power meter, flow meter, gateway atau actuator tambahan dipasang pada titik yang datanya belum tersedia atau masih membutuhkan pengaturan otomatis.',
206:'Jaringan disiapkan untuk menghubungkan mesin dan utilitas dengan server aplikasi serta database. Kebutuhan koneksi serial atau Ethernet mengikuti controller yang digunakan. Server menyimpan data, menjalankan aplikasi dan menyediakan backup agar historical tetap dapat ditelusuri.',
222:'Pelaksanaan dilakukan bertahap: survei dan penentuan prioritas, uji pembacaan pada mesin yang dipilih, pembuatan dashboard dan historical, perluasan koneksi, integrasi batch dan ERP, lalu otomatisasi serta analisa AI. Setiap tahap diperiksa hasilnya sebelum pekerjaan berikutnya diterapkan.',
224:'Jadwal rinci ditentukan setelah survei dan kebutuhan perangkat selesai. Milestone utamanya adalah pembacaan data sesuai, dashboard dan historical berjalan, batch terhubung dengan mesin, pengiriman parameter teruji, lalu evaluasi penerapan. Ketersediaan perangkat, akses controller dan jadwal produksi menjadi penentu urutan pekerjaan.',
226:'Kebutuhan pelaksana meliputi pengembangan aplikasi dan database, komunikasi PLC atau controller, pemasangan listrik dan sensor, integrasi ERP serta pengujian proses. Pekerjaan dikoordinasikan oleh Digital Automation dengan dukungan bagian terkait atau vendor sesuai kebutuhan.',
228:'Kebutuhan awal meliputi controller/gateway, sensor, meter, jaringan, power supply, panel pendukung, server dan perangkat untuk pengecekan. Jenis serta jumlahnya mengikuti hasil survei dan parameter yang akan dimonitoring atau dikontrol pada masing masing mesin.',
230:'Pengadaan dilakukan berdasarkan spesifikasi yang sudah disepakati. Pemilihan perangkat dan vendor mempertimbangkan kecocokan komunikasi, fungsi, harga, dokumentasi, ketersediaan barang serta dukungan perbaikan. Perangkat yang berkaitan dengan mesin baru perlu dipastikan dapat diintegrasikan dengan aplikasi SMM.',
232:'Pemasangan dan perubahan program dijadwalkan bersama produksi dan engineering. Program serta konfigurasi lama dibackup sebelum perubahan. Uji dilakukan terlebih dahulu, lalu penggunaan system baru diterapkan bertahap dengan cara pemulihan yang disiapkan apabila terjadi kendala.',
236:'Estimasi biaya menggunakan kebutuhan hardware per asset yang sudah diperkirakan, dengan penyesuaian pada kondisi controller, jumlah parameter dan sensor tambahan. Harga serta pekerjaan pemasangan diperiksa kembali setelah survei agar kebutuhan setiap mesin tidak disamakan tanpa pengecekan.',
238:'RAB dirinci menjadi controller/gateway, sensor dan meter, actuator, jaringan, panel dan power supply, server, pekerjaan pemasangan serta pengembangan aplikasi. Estimasi awal project tetap mengacu pada Rp1.000.000.000 sampai Rp2.000.000.000 dan akan diperjelas berdasarkan rincian kebutuhan yang disetujui.',
240:'Biaya operasi meliputi kebutuhan server, penyimpanan data, jaringan, pengecekan sensor, penggantian perangkat dan pemeliharaan aplikasi. Kebutuhan ini dicatat agar system tetap berjalan dan data yang digunakan tetap sesuai selama masa pemakaian.',
242:'Cadangan biaya disiapkan untuk kebutuhan lapangan yang belum terlihat pada survei awal, seperti penyesuaian komunikasi, penambahan sensor atau perbaikan jaringan. Nilainya diajukan setelah kebutuhan dan risiko tiap tahap diperiksa, tanpa menetapkan persentase sebelum ada perhitungan.',
244:'Sumber pendanaan diajukan kepada perusahaan sesuai tahap pekerjaan yang disetujui. Jadwal pembayaran mengikuti kesepakatan pengadaan atau kontrak dan kemajuan pekerjaan. Pembelian perangkat diprioritaskan berdasarkan kebutuhan tahap yang akan dilaksanakan.',
246:'Anggaran yang sudah disetujui menjadi acuan pengadaan. Realisasi pembelian dan pekerjaan dibandingkan dengan anggaran tersebut. Tambahan kebutuhan atau perubahan biaya dicatat beserta alasannya dan diajukan untuk persetujuan sebelum dilaksanakan.',
250:'Risiko diperiksa dari kondisi mesin, komunikasi, data, keselamatan, jadwal produksi dan biaya. Prioritas penanganan ditentukan dari kemungkinan kejadian serta dampaknya pada pekerjaan dan operasional perusahaan.',
252:'Risiko utama meliputi data yang tidak sesuai, komunikasi terputus, controller tanpa dokumentasi, kehilangan data dan gangguan saat perubahan program. Penanganannya berupa validasi nilai, uji koneksi, riset controller, backup dan penjadwalan perubahan bersama bagian terkait.',
254:'Peluang pengembangan diambil dari data pemborosan, pekerjaan manual dan masalah berulang yang ditemukan selama pelaksanaan. Setiap kendala dicatat dengan kondisi kejadian, tindakan yang sudah dilakukan dan bagian yang perlu menindaklanjuti.',
256:'Mutu diperiksa dengan membandingkan nilai dashboard terhadap HMI atau alat ukur, memastikan satuan dan waktu pencatatan sesuai, serta menguji fungsi penyimpanan, alarm dan pengiriman parameter. Hasil pemeriksaan dicatat sebelum pekerjaan diterima.',
258:'Pemasangan mengikuti ketentuan keselamatan dan prosedur perusahaan yang berlaku. Perubahan pada mesin atau utilitas dikoordinasikan dengan bagian penanggung jawab agar tidak mengganggu perlindungan mesin, pekerjaan operator maupun pengelolaan lingkungan.',
260:'Hasil pekerjaan dan temuan diperiksa pada setiap tahap. Nilai yang belum sesuai, fungsi yang gagal atau dokumentasi yang belum lengkap dicatat untuk diperbaiki, kemudian diuji kembali sebelum tahap terkait dinyatakan selesai.',
264:'Kemajuan diukur dari daftar mesin yang sudah terhubung, parameter yang sudah tervalidasi, fungsi dashboard yang berjalan dan integrasi yang sudah diuji. Hasil tersebut dibandingkan dengan target tahap yang disepakati.',
266:'Laporan perkembangan memuat pekerjaan selesai, pekerjaan berikutnya, kendala, kebutuhan keputusan dan realisasi biaya. Manfaat yang sudah dapat dihitung dilaporkan berdasarkan data actual, bukan hanya berdasarkan perkiraan penghematan.',
268:'Koordinasi dilakukan dengan bagian yang berkaitan sebelum instalasi, perubahan program dan pengujian. Rapat perkembangan membahas kemajuan, kendala serta keputusan yang dibutuhkan. Hasil keputusan dicatat agar tindak lanjut dan tanggung jawabnya jelas.',
270:'Perubahan kebutuhan diajukan dengan penjelasan tujuan, dampak teknis, biaya dan jadwalnya. Perubahan yang mempengaruhi anggaran, cakupan atau operasional harus mendapat persetujuan pihak yang berwenang sebelum diterapkan.',
272:'Program PLC, konfigurasi, daftar parameter, diagram dan aplikasi disimpan dengan identitas versi serta tanggal perubahan. Backup dilakukan sebelum perubahan agar versi sebelumnya dapat ditelusuri dan digunakan untuk pemulihan bila diperlukan.',
274:'Temuan komunikasi, pola kerusakan, hasil pengujian dan cara penanganan disimpan sebagai dokumentasi bersama. Informasi ini digunakan untuk mempercepat pekerjaan pada mesin berikutnya dan mengurangi pengulangan pengecekan yang sama.',
278:'Pengujian mengikuti fungsi yang dibutuhkan pada setiap mesin. Daftar uji mencakup pembacaan nilai, historical, alarm, batch, hak akses dan pengiriman parameter agar setiap kebutuhan memiliki hasil pemeriksaan yang jelas.',
280:'Uji awal dilakukan pada perangkat atau aplikasi sebelum pemasangan sesuai kebutuhan pekerjaan. Setelah terpasang, uji lapangan dilakukan bersama bagian terkait untuk memeriksa koneksi, nilai actual, fungsi kontrol dan kesesuaian dengan proses mesin.',
282:'Commissioning dilakukan setelah instalasi dan komunikasi siap. Data mesin dicocokkan dengan dashboard, integrasi batch dan ERP diperiksa, lalu fungsi kontrol diuji bertahap. Uji operasi dilakukan pada kondisi yang disepakati bersama produksi dan engineering.',
284:'Periksa ketepatan nilai, kelengkapan penyimpanan data, respon alarm dan pembatasan hak akses. Kondisi kehilangan komunikasi dan gangguan perangkat juga diuji agar system memberikan informasi yang jelas dan kontrol mesin tetap mengikuti fungsi perlindungannya.',
286:'Pengguna diberi pelatihan sesuai perannya, mulai dari pemantauan dashboard, pemilihan batch, penggunaan resep sampai penanganan alarm. SOP dibuat berdasarkan fungsi yang sudah diuji dan memuat langkah penggunaan serta tindak lanjut saat terjadi gangguan.',
288:'Serah terima dilakukan setelah hasil uji, program, konfigurasi dan dokumentasi tersedia. Dukungan perbaikan, garansi perangkat dan pihak yang dihubungi mengikuti kesepakatan pengadaan atau pelaksanaan pekerjaan terkait.',
292:'Manfaat dipantau bersama bagian yang menggunakan data. Produksi mengevaluasi hasil dan waktu proses, engineering mengevaluasi downtime serta kerusakan, dan utilitas mengevaluasi konsumsi. Digital Automation membantu penyediaan data dan pengembangan analisa yang dibutuhkan.',
294:'Hasil penerapan dibandingkan dengan kondisi awal pada proses yang sebanding. Perbandingan meliputi konsumsi utilitas, waktu proses, downtime, pengulangan produksi dan waktu pekerjaan manual agar perubahan kinerja dapat dinilai berdasarkan data.',
296:'System dipelihara melalui pengecekan koneksi, validasi sensor, backup dan perbaikan aplikasi. Pengembangan berikutnya mengikuti kebutuhan operasional serta hasil evaluasi data, termasuk perluasan otomatisasi dan penerapan AI.',
298:'Temuan yang masih terbuka diselesaikan dan diperiksa kembali. Pekerjaan vendor, dokumentasi serta kewajiban sesuai kontrak ditinjau sebelum tahap pekerjaan atau project ditutup.',
300:'Laporan akhir memuat cakupan yang sudah diterapkan, daftar mesin terhubung, hasil pengujian, realisasi biaya, manfaat yang dapat dibuktikan dan kebutuhan lanjutan. Kendala serta penyelesaiannya dicatat sebagai pembelajaran untuk pengembangan berikutnya.',
302:'Penutupan diajukan setelah hasil kerja diterima dan tindak lanjut utama sudah jelas. Penggunaan serta pemeliharaan system diserahkan kepada bagian yang ditetapkan, dengan persetujuan penutupan dari pihak yang berwenang.',
306:'Acuan ISO yang tercantum digunakan sebagai rujukan penyusunan dan pengelolaan project. Dokumen pendukungnya meliputi daftar kebutuhan, rencana pekerjaan, catatan perubahan, hasil pengujian dan berita acara sesuai tahap pelaksanaan.',
308:'Lampiran memuat daftar mesin dan utilitas, jenis controller, komunikasi, sensor, parameter yang tersedia dan kebutuhan tambahan. Data hasil survei menjadi dasar penetapan jumlah unit serta prioritas pekerjaan.',
310:'Lampiran memuat alur data mesin ke dashboard dan database, hubungan dengan ERP, jaringan serta gambar pemasangan yang diperlukan. Diagram disesuaikan dengan hasil survei dan rancangan yang disepakati.',
312:'Lampiran memuat jenis, jumlah, fungsi dan spesifikasi controller/gateway, sensor, meter, jaringan serta perangkat pendukung yang akan digunakan. Daftar diperbarui mengikuti hasil pengecekan dan persetujuan pengadaan.',
314:'Lampiran memuat pembagian pekerjaan, urutan pelaksanaan, pelaksana dan jadwal tiap tahap. Jadwal terperinci disusun setelah prioritas, ketersediaan perangkat dan waktu akses ke mesin sudah diketahui.',
316:'Lampiran memuat rincian biaya perangkat, pemasangan, pengembangan dan pemeliharaan. Perhitungan penghematan serta pengembalian investasi dilengkapi setelah data kondisi awal dan hasil penerapan tersedia.',
318:'Lampiran memuat pihak terkait, kebutuhan keterlibatan, risiko utama dan perubahan yang diajukan. Setiap catatan disertai penanggung jawab tindak lanjut serta status penyelesaiannya.',
320:'Lampiran memuat kebutuhan fungsi, cara pengujian, hasil yang diperoleh dan keputusan penerimaannya. Ketidaksesuaian dicatat untuk diperbaiki dan diuji kembali.',
322:'Lampiran memuat formulir persetujuan kebutuhan, perubahan, hasil pengujian dan berita acara serah terima. Pengesahan diisi oleh pihak yang berwenang pada saat tahap terkait dilaksanakan.',
324:'Lampiran digunakan untuk menyimpan manual controller, dokumentasi komunikasi, data hasil pengukuran, spesifikasi vendor dan referensi lain yang digunakan selama pengembangan.',
156:'Perhitungan penghematan dan ROI akan dilengkapi setelah data waktu proses, downtime, pengulangan produksi dan konsumsi utilitas tersedia. Angka yang sudah tercantum pada tabel perlu diverifikasi dan belum digunakan sebagai hasil penghematan actual.',
}
append={
13:'Internal perusahaan',
153:'penerapan otomatisasi akan dihitung dengan membandingkan durasi pekerjaan sebelum dan sesudah system digunakan.',
154:'ulang akan dihitung berdasarkan jumlah pengulangan, waktu tambahan dan pemakaian utilitas serta chemical yang dapat dikurangi.',
155:'bagian administrasi dalam pencatatan dan penelusuran data. Nilainya dihitung dari waktu pekerjaan yang benar benar berkurang setelah penerapan.',
159:'project ini adalah nilai actual mesin dapat dimonitoring dan disimpan, record proses terhubung dengan batch, serta penggunaan utilitas dan downtime dapat dihitung. Jumlah mesin terhubung, kelengkapan parameter dan hasil pengujian menjadi indikator kemajuan tiap tahap.',
187:'serta listrik, steam, chemical, runtime, downtime, alarm dan hasil produksi yang berkaitan dengan setiap batch. Cakupan juga meliputi integrasi ERP, pengaturan parameter dan otomatisasi utilitas. Pelaksanaannya bertahap mengikuti prioritas dan kesiapan setiap mesin.',
201:'menghubungkan controller dan sensor mesin ke gateway atau jaringan yang sesuai, lalu meneruskan datanya ke server aplikasi dan database. Dashboard menampilkan nilai actual, historical, trend, alarm serta informasi batch dalam satu system.',
202:' akan memiliki identitas dan daftar parameter agar sumber nilai yang dibaca dapat diketahui. Data produksi dari ERP dihubungkan menggunakan identitas mesin dan batch, sedangkan pengiriman parameter mengikuti fungsi serta batas yang ditetapkan pada mesin.',
209:'akan disimpan bersama nomor batch, waktu proses dan hasil QC. Dengan hubungan ini, kondisi mesin saat menghasilkan kain yang bagus maupun bermasalah dapat dibandingkan dan ditelusuri kembali.',
213:'bagian pengembangan setelah data mesin, batch dan hasil produksi sudah terkumpul. Analisa digunakan untuk membandingkan pola proses, mencari hubungan dengan hasil kain, mendeteksi abnormal dan membantu memberikan rekomendasi perbaikan atau parameter berdasarkan record yang sesuai.',
217:'mencegah akses dan perubahan oleh pihak yang tidak berwenang. Hak monitoring, perubahan parameter dan pengelolaan system dibedakan sesuai tugas pengguna. Aktivitas perubahan dicatat, koneksi diamankan dan backup disiapkan untuk pemulihan data.',
}

for i,text in fill.items():
 assert not original.paragraphs[i].text.strip(),(i,original.paragraphs[i].text)
 p=d.paragraphs[i];p.add_run(text)
for i,text in append.items():d.paragraphs[i].add_run(text)

# Fill one previously empty revision row; keep all other rows and the ROI table intact.
for cell,text in zip(d.tables[0].rows[1].cells,['00','29 Oktober 2026','Melengkapi bagian kosong dan kalimat yang belum selesai tanpa menghapus isi awal.','Digital Automation Departement']):
 assert not cell.text;cell.paragraphs[0].add_run(text)
for cell,text in zip(d.tables[1].rows[2].cells,['Input data manual','Data awal','Hasil uji','Selisih waktu','Belum dihitung','Belum dihitung','Belum dihitung']):
 assert not cell.text;cell.paragraphs[0].add_run(text)

# Navigation metadata is the only existing numeric text that is refreshed.
# Bookmarks retain headings and the existing table-of-contents layout.
targets=[15,46,92,157,171,185,199,220,234,248,262,276,290,304]
for n,idx in enumerate(targets):
 p=d.paragraphs[idx];start=OxmlElement('w:bookmarkStart');start.set(qn('w:id'),str(1000+n));start.set(qn('w:name'),'scope_section_'+str(n))
 end=OxmlElement('w:bookmarkEnd');end.set(qn('w:id'),str(1000+n));p._p.insert(1 if p._p.pPr is not None else 0,start);p._p.append(end)
for n,idx in enumerate(range(31,45)):
 p=d.paragraphs[idx];texts=p._p.xpath('.//w:t');last=texts[-1]
 assert last.text and last.text.strip().isdigit(),(idx,last.text)
 run=last.getparent();pos=p._p.index(run)
 # A tab inside a field result is removed by Word's field update, so keep it outside.
 tabs=run.xpath('./w:tab')
 if tabs:
  tabrun=OxmlElement('w:r')
  if run.find(qn('w:rPr')) is not None:tabrun.append(deepcopy(run.find(qn('w:rPr'))))
  for tab in tabs:run.remove(tab);tabrun.append(tab)
  p._p.insert(pos,tabrun);pos+=1
 field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGEREF scope_section_'+str(n)+' \\h')
 result=deepcopy(run);field.append(result);p._p.remove(run);p._p.insert(pos,field)
for section in d.sections:
 for p in section.footer.paragraphs:
  if p.text=='Halaman 2':
   for node in p._p.xpath('./w:r'):p._p.remove(node)
   p.add_run('Halaman ');field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE')
   run=OxmlElement('w:r');text=OxmlElement('w:t');text.text='1';run.append(text);field.append(run);p._p.append(field)

# Main content must retain every original word, run and paragraph property.
assert len(d.paragraphs)==len(original.paragraphs)==325
for i,(a,b) in enumerate(zip(original.paragraphs,d.paragraphs)):
 if i in range(31,45):
  assert ''.join(a._p.xpath('.//w:t/text()'))==''.join(b._p.xpath('.//w:t/text()'))
 elif a.text.strip():
  assert b.text.startswith(a.text),(i,a.text,b.text)
 else:
  assert i in fill or b.text==a.text
 assert a.style.style_id==b.style.style_id
def canonical(e):
 from lxml import etree
 return etree.tostring(e,method='c14n') if e is not None else None
for a,b in zip(original.paragraphs,d.paragraphs):assert canonical(a._p.pPr)==canonical(b._p.pPr)
assert canonical(original.styles.element)==canonical(d.styles.element)
assert canonical(original.sections[0]._sectPr)==canonical(d.sections[0]._sectPr)
for at,bt in zip(original.tables,d.tables):
 for ar,br in zip(at.rows,bt.rows):
  for ac,bc in zip(ar.cells,br.cells):
   if ac.text:assert bc.text==ac.text
assert len(original.tables)==len(d.tables)==2
d.save(out)
assert hashlib.sha256(src.read_bytes()).hexdigest()==source_hash
report={'source':str(src),'source_sha256':source_hash,'output':str(out),'original_paragraphs_preserved':325,'filled_paragraphs':len(fill),'completed_paragraphs':len(append),'styles_and_paragraph_format_preserved':True,'original_nonempty_table_cells_unchanged':True,'blank_table_rows_filled':2,'navigation':'TOC page references and footer page field updated; original heading wording retained.'}
(work/'verifikasi_template_dilengkapi.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
