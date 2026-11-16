from pathlib import Path
from copy import deepcopy
from shutil import copy2
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
import json

work=Path(r'D:\File HMI\Analisis\Dokumen_Project')
target=Path(r'C:\Users\Lenovo Yoga 7i\Documents\PT.SMM\DIGITAL AUTOMATION DEPARTEMENT\DOKUMENTASI DAN NOTE\Dokumentasi\Internal Dokumen\Pengajuan_Project_Digitalisasi_Dan_Otomatisasi_PT_SMM_Dilengkapi.docx')
backup=work/'sebelum_detail_ROI_teknis.docx'
if not backup.exists(): copy2(target,backup)
target=target.with_name('Pengajuan_Project_Digitalisasi_Dan_Otomatisasi_PT_SMM_Detail_ROI_Teknis.docx')
d=Document(backup)
old=list(d.paragraphs)
base_xml=[deepcopy(p._p) for p in old]
cursor=None

def para(text,heading=False):
    global cursor
    el=OxmlElement('w:p');cursor.addnext(el);cursor=el
    p=Paragraph(el,d._body)
    p.style=d.styles['Normal']
    f=p.paragraph_format
    f.space_before=Pt(12 if heading else 0);f.space_after=Pt(6)
    f.first_line_indent=Inches(0);f.line_spacing=1.08
    f.keep_with_next=heading;f.widow_control=True
    r=p.add_run(text);r.font.name='Arial';r.font.size=Pt(11)
    r.font.color.rgb=RGBColor(0,0,0);r.bold=heading
    return p

def table(headers,rows,widths):
    global cursor
    t=d.add_table(rows=1,cols=len(headers));t.autofit=False
    t.alignment=WD_TABLE_ALIGNMENT.CENTER
    pr=t._tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for side in ['top','left','bottom','right','insideH','insideV']:
        e=OxmlElement('w:'+side);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
    pr.append(borders)
    for col,w in zip(t.columns,widths):col.width=Inches(w)
    for j,h in enumerate(headers):t.rows[0].cells[j].text=h
    for row in rows:
        cells=t.add_row().cells
        for c,txt in zip(cells,row):c.text=str(txt)
    for i,row in enumerate(t.rows):
        rp=row._tr.get_or_add_trPr();rp.append(OxmlElement('w:cantSplit'))
        if i==0:rp.append(OxmlElement('w:tblHeader'))
        for j,c in enumerate(row.cells):
            c.width=Inches(widths[j]);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cp=c._tc.get_or_add_tcPr();m=OxmlElement('w:tcMar')
            for side in ['top','left','bottom','right']:
                e=OxmlElement('w:'+side);e.set(qn('w:w'),'90');e.set(qn('w:type'),'dxa');m.append(e)
            cp.append(m)
            if i==0:
                sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E7E6E6');cp.append(sh)
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0);p.paragraph_format.line_spacing=1.0
                for r in p.runs:r.font.name='Arial';r.font.size=Pt(10);r.bold=i==0
    cursor.addnext(t._tbl);cursor=t._tbl
    return t

cursor=old[156]._p
para('2.5.1  Dasar perhitungan dan data yang diperlukan',True)
para('Perhitungan berikut menggunakan investasi Rp2.000.000.000 sesuai estimasi awal. Pembagian terhadap 160 unit menghasilkan rata rata Rp12.500.000 per unit, hanya untuk melihat skala investasi. Nilai penghematan setiap mesin tetap dihitung sesuai proses, jam kerja dan kondisi actual; mesin produksi dan utilitas tidak disamakan manfaatnya.')
para('Data awal diambil dari record produksi, QC, engineering, utilitas dan administrasi, disarankan mencakup 3 sampai 6 bulan agar variasi order terlihat. Data sebelum dan sesudah dibandingkan pada jenis kain, berat batch, resep dan kondisi produksi yang sebanding. Jumlah asset dalam RAB juga perlu dicocokkan dengan inventaris final.')
table(['Data yang dikumpulkan','Sumber dan kegunaan'],[
('Durasi setup, menunggu dan downtime','Record mesin dan engineering; menentukan waktu mesin yang benar benar bisa dipakai kembali.'),
('Batch, kg hasil baik dan kapasitas per jam','Produksi dan ERP; menentukan output tambahan yang dapat diproduksi dan dijual.'),
('Rework, reject dan downgrade','QC dan produksi; menentukan frekuensi serta biaya kerugian masing masing kategori.'),
('Chemical, steam, air, listrik dan lembur','Meter, pemakaian bahan dan biaya actual; menghitung pengeluaran yang dapat dikurangi.'),
('Margin kontribusi dan biaya system','Keuangan dan Digital Automation; menghitung manfaat setelah biaya variabel dan biaya operasi tambahan.')],[2.35,4.35])
para('2.5.2  Efisiensi waktu proses dan pekerjaan manual',True)
para('Waktu yang berkurang dapat berasal dari input resep, setup, menunggu instruksi atau troubleshooting. Pengurangan waktu mesin dihitung terpisah dari waktu administrasi. Pencatatan operator yang lebih cepat belum tentu menambah jam produksi bila mesin sebelumnya tetap running.')
para('Jam tersedia per bulan = menit mesin yang dihemat per hari ÷ 60 × hari operasi. Manfaat produksi = jam tersedia × kapasitas hasil baik per jam × faktor pemanfaatan × margin kontribusi per kg. Margin kontribusi adalah nilai penjualan setelah biaya variabel untuk menghasilkan dan menjual tambahan produksi tersebut.')
para('Contoh simulasi per mesin: waktu berkurang 20 menit per hari, 26 hari operasi, kapasitas 50 kg per jam, faktor pemanfaatan 60% dan margin kontribusi Rp1.500 per kg. Jam tersedia = 20 ÷ 60 × 26 = 8,67 jam per bulan. Tambahan hasil baik = 8,67 × 50 × 60% = sekitar 260 kg. Manfaat = 260 × Rp1.500 = Rp390.000 per mesin per bulan.')
para('Faktor pemanfaatan 60% pada contoh harus dibuktikan dari ketersediaan order, bahan dan kapasitas proses berikutnya. Jika tambahan kapasitas belum bisa dimanfaatkan, manfaat produksi tambahan dicatat nol. Untuk pekerjaan manual, jam kerja yang berkurang dicatat sebagai peningkatan produktivitas; nilai rupiahnya masuk ROI hanya jika ada pengurangan biaya yang nyata, misalnya lembur yang tidak lagi diperlukan.')
para('2.5.3  Pengurangan pengulangan proses dan kegagalan hasil',True)
para('Penghematan rework per bulan = jumlah batch pembanding × penurunan tingkat rework × biaya tambahan rata rata setiap rework. Gunakan volume batch yang sama agar penurunan jumlah kejadian akibat produksi yang lebih sedikit tidak dianggap sebagai perbaikan proses.')
para('Contoh simulasi: 52 batch per mesin per bulan, tingkat rework turun dari 5% menjadi 3%, sehingga rework yang dapat dicegah = 52 × (5% − 3%) = 1,04 batch per bulan. Jika biaya tambahan per rework Rp450.000, penghematannya = 1,04 × Rp450.000 = Rp468.000 per mesin per bulan.')
table(['Komponen biaya rework','Asumsi per kejadian'],[
('Chemical tambahan','Rp200.000'),('Steam, air dan listrik tambahan','Rp150.000'),('Lembur tambahan','Rp75.000'),('Pengujian ulang','Rp25.000'),('Total biaya tambahan','Rp450.000')],[4.35,2.35])
para('Rincian tersebut merupakan contoh biaya yang harus diganti dengan pemakaian actual. Reject dihitung dari biaya produk yang benar benar hilang setelah dikurangi nilai pemulihan. Downgrade dihitung dari penurunan nilai jual bersih yang dapat dibuktikan. Satu batch tidak dimasukkan sebagai kerugian penuh pada lebih dari satu kategori.')
para('2.5.4  Penghematan utilitas dan engineering',True)
para('Penghematan utilitas = penurunan konsumsi per kg hasil baik × volume pembanding × biaya per satuan utilitas. Perhitungan dilakukan terpisah untuk listrik, air, steam dan udara bertekanan. Pemakaian sebelum dan sesudah perlu dibandingkan pada beban yang sebanding; penurunan konsumsi karena produksi turun tidak langsung dianggap efisiensi.')
para('Manfaat engineering berasal dari biaya kerusakan, spare part darurat, lembur dan downtime yang berkurang. Tambahan jam mesin akibat downtime yang berkurang dimasukkan ke perhitungan waktu pada 2.5.2. Biaya rework yang sudah mencakup chemical dan utilitas tidak dihitung lagi sebagai penghematan utilitas terpisah.')
para('2.5.5  Simulasi manfaat bersih ROI dan balik modal',True)
para('Gabungan contoh waktu dan rework menghasilkan manfaat kotor Rp390.000 + Rp468.000 = Rp858.000 per mesin per bulan. Keduanya boleh dijumlahkan jika penghematan 20 menit per hari tidak mencakup waktu rework yang sudah diperhitungkan. Penghematan utilitas umum, administrasi dan engineering di luar dua contoh tersebut belum ditambahkan.')
para('Simulasi berikut memakai 40, 80 dan 120 mesin yang diasumsikan memenuhi kondisi contoh yang sama. Jumlah ini adalah variasi cakupan manfaat, bukan hasil survei atau target yang sudah disetujui. Manfaat mesin lain dan utilitas dihitung terpisah sesuai datanya. Investasi tetap Rp2 miliar dan biaya operasi tambahan system diasumsikan Rp8 juta per bulan pada ketiga skenario.')
table(['Komponen','40 mesin','80 mesin','120 mesin'],[
('Manfaat kotor per bulan','Rp34,32 juta','Rp68,64 juta','Rp102,96 juta'),
('Biaya operasi per bulan','Rp8 juta','Rp8 juta','Rp8 juta'),
('Manfaat bersih per bulan','Rp26,32 juta','Rp60,64 juta','Rp94,96 juta'),
('Manfaat bersih per tahun','Rp315,84 juta','Rp727,68 juta','Rp1.139,52 juta'),
('ROI tahunan sederhana','15,79%','36,38%','56,98%'),
('Balik modal sederhana','76,0 bulan','33,0 bulan','21,1 bulan')],[2.2,1.5,1.5,1.5])
para('Biaya operasi Rp8 juta per bulan merupakan asumsi, terdiri dari pemeliharaan aplikasi dan perangkat Rp4 juta, server dan penyimpanan Rp2 juta, jaringan dan backup Rp1 juta, serta pengecekan atau kalibrasi Rp1 juta. Hanya biaya tambahan akibat project yang dibebankan, kemudian disesuaikan dengan RAB operasi actual.')
para('Manfaat bersih bulanan = total manfaat kotor − biaya operasi tambahan. ROI tahunan sederhana = manfaat bersih bulanan × 12 ÷ investasi × 100%. Balik modal sederhana = investasi ÷ manfaat bersih bulanan. Contoh 80 mesin: Rp60,64 juta × 12 ÷ Rp2.000 juta × 100% = 36,38%; balik modal = Rp2.000 juta ÷ Rp60,64 juta = sekitar 33 bulan.')
para('Perhitungan tersebut menggambarkan kondisi setelah cakupan contoh sudah aktif penuh. Waktu implementasi dan kenaikan manfaat secara bertahap akan memperpanjang balik modal sejak pengeluaran pertama. Untuk evaluasi actual, catat arus kas bulanan sejak awal project sampai akumulasi manfaat bersih menutup seluruh investasi. Perhitungan sederhana ini belum memasukkan pajak dan nilai waktu uang.')
para('Angka 20, 50 dan 80 pada tabel awal tetap dipertahankan sebagai bagian format awal, tetapi belum dipakai sebagai persentase atau nominal karena satuan serta dasar perhitungannya belum ditetapkan. Simulasi rinci di atas menggunakan asumsi yang disebutkan secara terpisah.')
para('2.5.6  Pembuktian manfaat setelah implementasi',True)
para('Pada mesin uji, catat nilai awal, perubahan yang diterapkan dan hasil sesudah penerapan. Produksi memverifikasi waktu serta output, QC memverifikasi rework dan hasil kain, engineering memverifikasi downtime, utilitas memverifikasi konsumsi, dan keuangan memverifikasi nilai biaya serta margin. Hanya manfaat yang terukur dan tidak tumpang tindih yang masuk perhitungan ROI actual.')
para('Evaluasi dilakukan per bulan untuk membandingkan estimasi dengan realisasi. Jika manfaat lebih rendah, periksa penyebabnya seperti pemakaian system yang belum penuh, order yang tidak tersedia, data sensor yang belum sesuai atau cakupan otomatisasi yang belum selesai. Keputusan perluasan mengikuti hasil uji teknis dan manfaat yang sudah dapat dibuktikan.')

cursor=old[202]._p
para('Rincian aliran data mesin',True)
para('Alur monitoring direncanakan dari sensor atau meter ke PLC/controller, kemudian melalui driver atau gateway ke layanan pengumpulan data, database dan dashboard. HMI lokal tetap menjadi titik pembanding saat validasi. Aplikasi pengumpulan data memisahkan pembacaan controller dari tampilan agar gangguan pada satu dashboard tidak menghentikan penyimpanan data.')
para('Setiap tag memiliki kode mesin, nama parameter, alamat atau object sumber, tipe data, satuan, faktor scaling, waktu pembacaan dan status kualitas. Daftar tag juga membedakan nilai yang hanya dibaca dan parameter yang boleh ditulis. Contoh nama parameter adalah suhu actual, setpoint suhu, level, tekanan, kecepatan, status running, step proses dan alarm.')
para('Target awal tampilan nilai proses adalah pembaruan setiap 1 detik bila controller dan jaringan mendukung. Interval pembacaan per kelompok tag ditetapkan setelah uji beban komunikasi; alarm dan perubahan status dicatat sesuai kemampuan sumbernya. Waktu data terakhir harus terlihat. Saat komunikasi terputus, nilai terakhir ditandai tidak terbaru agar tidak terbaca sebagai kondisi actual.')
para('Database menyimpan kode mesin, nomor batch, waktu sumber atau waktu penerimaan, nilai, satuan dan kualitas pembacaan. Data per detik dapat disimpan untuk kebutuhan analisa proses, lalu diringkas untuk laporan jangka panjang. Kapasitas penyimpanan dihitung dari jumlah tag × frekuensi pencatatan × masa simpan, termasuk index dan backup, sebelum server ditentukan.')

cursor=old[204]._p
para('Pendataan dan penentuan koneksi controller',True)
para('Survei mencatat merk dan tipe controller/HMI/inverter, versi program, port yang tersedia, diagram listrik, sensor terpasang dan dokumentasi komunikasi. Backup program serta konfigurasi dilakukan sebelum perubahan. Mesin dikelompokkan berdasarkan controller dan kebutuhan data sehingga satu hasil uji dapat digunakan sebagai dasar pada mesin yang benar benar sejenis.')
para('Untuk perangkat dengan protokol yang terdokumentasi, pilih koneksi sesuai dukungannya, misalnya Modbus RTU/TCP, OPC UA atau driver resmi. Nama protokol tersebut merupakan pilihan teknis, bukan asumsi bahwa seluruh mesin sudah mendukungnya. Untuk koneksi serial, periksa alamat perangkat, baud rate, parity, terminasi dan isolasi; untuk Ethernet periksa alamat IP, port dan batas koneksi.')
para('Pada mesin SETEX/Orgatex, jalur komunikasi server ke HMI dan HMI ke PLC harus dipetakan terpisah. File program PRG digunakan untuk urutan proses dan parameter; file tersebut belum membuktikan alamat nilai actual atau cara pengiriman perintah. Mapping ditetapkan dari konfigurasi, dokumentasi dan pengujian baca/tulis pada controller yang sesuai.')
para('Jika data belum tersedia dari controller, tentukan sensor atau meter tambahan berdasarkan rentang ukur, satuan, ketelitian, kondisi pemasangan dan kebutuhan kalibrasi. Sinyal dihubungkan ke input controller atau modul akuisisi yang sesuai. Rangkaian safety dan proteksi mesin diperiksa bersama engineering sebelum penambahan atau perubahan kontrol.')

cursor=old[206]._p
para('Rancangan jaringan dan keandalan data',True)
para('Jaringan mesin dikelompokkan per area dan dipisahkan dari jaringan pengguna kantor. Akses dari aplikasi ke controller dibatasi pada alamat dan layanan yang diperlukan. Daftar IP, port, jalur kabel, switch dan titik gateway menjadi bagian dokumentasi agar koneksi dapat ditelusuri ketika terjadi gangguan.')
para('Layanan pengumpulan data perlu menyimpan antrian sementara saat server tidak dapat diakses, kemudian mengirim ulang setelah koneksi pulih. Identitas record digunakan agar pengiriman ulang tidak menggandakan data. Waktu server, gateway dan controller diselaraskan sesuai kemampuan perangkat; selisih waktu dicatat jika controller tidak mendukung sinkronisasi.')
para('Server aplikasi, database, penyimpanan backup dan kebutuhan UPS dihitung dari beban actual serta lama gangguan yang harus ditangani. Backup database dan konfigurasi dibuat terjadwal dengan salinan terpisah, kemudian diuji pemulihannya. Target lama pemulihan dan batas kehilangan data ditetapkan bersama produksi sebelum sistem dipakai penuh.')

cursor=old[211]._p
para('Alur planning batch dan pengiriman program',True)
para('1. ERP atau planning membuat order dengan nomor batch, jenis kain, berat, resep dan mesin tujuan. Aplikasi memeriksa kelengkapan data, kapasitas mesin dan versi resep. Perubahan order yang sudah dikirim harus memiliki versi agar HMI tidak menjalankan data lama.')
para('2. Batch yang disetujui masuk antrian mesin. Aplikasi menyiapkan urutan fungsi dan parameter sesuai jenis controller. Untuk mesin berbasis PRG, validasi meliputi ID fungsi, urutan step, jumlah parameter, batas nilai, satuan dan kecocokan konfigurasi mesin. File hasil export diuji baca ulang sebelum digunakan pada HMI.')
para('3. HMI menerima batch dan program melalui mekanisme komunikasi yang telah diuji. Status transfer dibedakan menjadi dikirim, diterima, tervalidasi dan siap digunakan. Operator memeriksa identitas batch serta mesin sebelum menjalankan proses. Status running diambil dari controller, sehingga transfer yang berhasil tidak langsung dianggap sebagai proses yang sudah berjalan.')
para('4. Selama proses, suhu, waktu, level, alarm dan step actual dikaitkan ke nomor batch yang aktif. Saat proses selesai, aplikasi mengirim status akhir, durasi, konsumsi dan hasil produksi ke ERP melalui interface yang disepakati. Koreksi data harus menyimpan riwayat perubahan.')
para('Integrasi dosing LAWER',True)
para('Resep obat memuat kode chemical, target jumlah, satuan dan dasar perhitungan seperti berat kain atau volume larutan. Nilai persen terhadap berat kain perlu dibedakan dari konsentrasi gram per liter. Perhitungan target dosing menggunakan berat atau volume batch yang sudah disahkan, lalu dikonversi ke satuan yang diterima sistem dosing.')
para('Permintaan dosing membawa identitas batch, mesin, step, tangki tujuan dan rincian chemical. Status diterima, sedang disiapkan, siap dikirim, selesai atau gagal harus memiliki konfirmasi dari sistem terkait. Jumlah actual dan waktu dosing dikembalikan ke record batch. Aplikasi tidak menandai obat sudah masuk hanya karena permintaan berhasil dikirim.')
para('Antarmuka LAWER yang tersedia di lapangan perlu diperiksa bersama dokumentasinya; implementasi dapat memakai interface yang didukung vendor. Setiap permintaan diberi identitas unik dan pemeriksaan status sebelum dicoba ulang agar tidak terjadi dosing ganda saat koneksi terputus. Pembatalan, kekurangan stok, salah tangki dan kegagalan pengiriman diuji sebelum dihubungkan ke produksi.')
para('Pengiriman parameter dan otomatisasi utilitas',True)
para('Perintah tulis memeriksa hak pengguna, mesin tujuan, batch aktif, rentang nilai dan kondisi mesin. Aplikasi mencatat nilai lama, nilai baru, pengirim dan hasil konfirmasi, lalu membaca balik nilai yang diterima controller. Perintah start/stop dan perubahan resep mengikuti mode operasi serta interlock lokal yang telah disepakati.')
para('Pengaturan boiler, pompa dan supply air dilakukan dari gabungan kebutuhan mesin, tekanan atau level actual serta kapasitas peralatan. Parameter batas, prioritas beban dan perilaku saat komunikasi hilang ditetapkan di controller lokal. Aplikasi memberikan permintaan atau setpoint yang sudah dibatasi, sementara proteksi dan respon cepat tetap dijalankan controller.')

cursor=old[213]._p
para('Tahapan pengembangan analisa',True)
para('Tahap pertama menampilkan trend, durasi step, penyimpangan terhadap resep dan perbandingan konsumsi per kg. Tahap berikutnya menghubungkan data tersebut dengan hasil QC seperti krismark, bowing atau TM sesuai pencatatan produksi. Setiap analisa harus dapat ditelusuri kembali ke batch, mesin dan versi resep.')
para('Model AI dikembangkan setelah data tervalidasi dan label hasil produksi cukup. Hasil diuji pada batch yang berbeda dari data pelatihan serta diperiksa oleh produksi dan engineering. Rekomendasi parameter diterapkan melalui review dan uji terkontrol sebelum menjadi aturan otomatis. Ketepatan peringatan dan jumlah alarm yang tidak relevan ikut dievaluasi.')

cursor=old[217]._p
para('Penerapan akses dan pencatatan perubahan',True)
para('Hak pengguna dibagi menjadi monitoring, operator, engineering dan administrator. Hak mengubah resep, mengirim parameter, mengelola akun dan memulihkan backup diatur terpisah. Perubahan dicatat dengan identitas pengguna, waktu, alasan dan hasil tindakan. Akses jarak jauh menggunakan jalur yang disetujui perusahaan dengan pencatatan sesi.')
para('Akun layanan dibuat khusus untuk integrasi dan dibatasi sesuai kebutuhan. Kredensial disimpan di konfigurasi yang terlindungi. Uji gangguan mencakup koneksi terputus, server mati, data terlambat dan pengiriman ulang; setiap kondisi harus memiliki status yang terlihat serta langkah pemulihan yang dapat dijalankan petugas.')

cursor=old[222]._p
para('Tahapan implementasi teknis dan hasil yang harus tersedia',True)
table(['Tahap','Pekerjaan utama','Hasil sebelum dilanjutkan'],[
('1  Survei dan mapping','Pendataan mesin, backup, daftar tag dan kebutuhan sensor.','Daftar asset, jalur komunikasi dan parameter prioritas disepakati.'),
('2  Uji baca pada mesin perwakilan','Pembacaan nilai, scaling, alarm dan status pada setiap jenis koneksi utama.','Nilai sesuai HMI atau alat ukur dalam toleransi yang ditetapkan; beban komunikasi dapat diterima.'),
('3  Dashboard dan historical','Penyimpanan data, trend, kualitas pembacaan dan pencatatan batch.','Data dapat ditelusuri; gangguan koneksi ditandai; antrian dan pemulihan teruji.'),
('4  Integrasi batch dan dosing','Planning ERP, transfer program, konfirmasi HMI dan alur LAWER.','Identitas batch sesuai; status transfer jelas; pengulangan pesan tidak menggandakan transaksi.'),
('5  Kontrol dan otomatisasi','Uji parameter, mode operasi, interlock dan pengaturan utilitas.','Baca balik sesuai; batas nilai bekerja; kondisi gangguan dan pemulihan lulus uji.'),
('6  Perluasan dan evaluasi','Penerapan per kelompok mesin, pelatihan, dokumentasi dan pengukuran ROI.','Berita acara hasil uji, backup, SOP dan data manfaat tersedia sebelum serah terima.')],[1.35,2.55,2.8])
para('Mesin perwakilan dipilih berdasarkan jenis controller, kebutuhan proses dan tingkat kesulitan koneksi. Keberhasilan pada satu jenis mesin tidak langsung dianggap berlaku untuk seluruh mesin. Jumlah dan urutan perluasan ditentukan dari hasil uji, kesiapan perangkat serta jadwal produksi.')

# Existing content and its formatting remain intact; only insertions are allowed.
def signature(el):
    return (el.tag,dict(el.attrib),el.text,tuple(signature(c) for c in el))
for p,xml in zip(old,base_xml):
    assert signature(p._p)==signature(xml), 'Existing paragraph changed'
d.save(target)
check=Document(target)
before=[p.text for p in Document(backup).paragraphs if p.text]
after=[p.text for p in check.paragraphs if p.text]
pos=0
for txt in before:
    pos=after.index(txt,pos)+1
assert len(check.tables)==len(Document(backup).tables)+4
for n in (40,80,120):
    net=n*858000-8000000
    print(n,net,net*12/2000000000*100,2000000000/net)
print(json.dumps({'file':str(target),'paragraphs':len(check.paragraphs),'tables':len(check.tables),'preserved_original_paragraphs':len(before)},ensure_ascii=False))
