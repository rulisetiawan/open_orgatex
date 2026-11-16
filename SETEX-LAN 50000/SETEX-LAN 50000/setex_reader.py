"""SETEX Controller v0.5: read and explicitly confirmed single-word write."""
import csv
import ipaddress
import math
from pathlib import Path
import queue
import socket
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
from setex_alarms import read_status_alarms, read_alarm_detail
from setex_controller import read_live, build_read, build_write, write_once_verified
from setex_intervent import (PARAMETERS, FUNCTIONS, PROFILE_PARAMETERS, PROFILE_IDS,
                            read_temperature, changed_values, change_temperature_once, parameter_rows, INTERVENT_SERVICE)

BASE = Path(__file__).resolve().parent
OBJECTS = {"IW - Info Words": 1025, "Info Bits": 1026,
           "LW - Link Words": 1001, "L - Link Bits": 1002,
           "ACT - Aktual (IST)": 1010, "SET - Target (SOLL)": 1009,
           "Konsumsi batch - DWORD (1035)": 1035, "MW - Memory Words": 1058, "M - Memory Bits": 1057}
SERVICES = {"SV_READ (1)": 1, "SV_READ_BLOCK (11)": 11,
            "SV_READ_LIST (128)": 128}
WORD_OBJECTS = {name: code for name, code in OBJECTS.items()
                if code not in (1002, 1026, 1057)}
OBJECT_HELP = {
    1025: "IW: Info Words. Nomor alamat mengikuti tabel IW mesin.",
    1010: "ACT / IST: nilai aktual. Alamat ACT terpisah dari alamat IW.",
    1009: "SET / SOLL: nilai target/setpoint. Mulai baca hanya membaca; write memakai tombol terpisah.",
    1001: "LW: Link Words. Alamat LW terpisah dari IW, ACT, dan SET.",
    1035: "Counter konsumsi batch: DWORD uint32 Little-Endian, hanya baca. Alamat adalah indeks counter, bukan byte. Mapping air/energi, satuan dan rentang valid perlu validasi mesin. Baca sebelum reset batch; tidak otomatis dipicu Program End.",
    1058: "MW: Memory Words. Nilai mentah 16 bit; arti alamat mengikuti PLC mesin.",
}


def parse_addresses(text, quantity, count_text):
    parts = text.split(',')
    if any(not part.strip() for part in parts):
        raise ValueError('Daftar alamat tidak boleh kosong. Contoh: 10,20,30,40')
    if len(parts) > 1:
        addresses = [int(part.strip()) for part in parts]
    else:
        start = int(text.strip())
        count = 1 if quantity == 'Satuan' else int(count_text)
        if not 1 <= count <= 240:
            raise ValueError('Jumlah alamat harus 1..240.')
        addresses = list(range(start, start + count))
    if not 1 <= len(addresses) <= 240 or any(not 0 <= a <= 65535 for a in addresses):
        raise ValueError('Maksimal 240 alamat, masing-masing 0..65535.')
    if len(set(addresses)) != len(addresses):
        raise ValueError('Alamat duplikat dalam daftar. Tulis setiap alamat satu kali.')
    return addresses


def validate_request(service, obj, start, count):
    if service not in (1, 11, 128) or obj not in OBJECTS.values():
        raise ValueError("Perintah/objek tidak diizinkan.")
    if not 0 <= start <= 65535 or not 1 <= count <= 240 or start + count > 65536:
        raise ValueError("Alamat 0..65535, jumlah 1..240, rentang tidak boleh melampaui 65535.")
    if service == 128 and obj not in (1001, 1002):
        raise ValueError("Commands.csv tidak mencantumkan SV_READ_LIST untuk objek ini.\n"
                         "Untuk IW pilih SV_READ atau SV_READ_BLOCK.")


def read_values(mode, service, obj, start, count, tick):
    validate_request(service, obj, start, count)
    if mode != "SIMULASI":
        raise RuntimeError("Pembacaan LIVE belum tersedia: header sesi, serialisasi request, "
                           "dan decoder respons TCP belum terverifikasi.\n"
                           "Gunakan Tes TCP untuk memeriksa koneksi saja.")
    # Angka buatan yang sengaja tidak diberi label sensor/satuan fisik.
    return [((start + i) * 17 + tick) % (2 if obj in (1002, 1026, 1057) else (4294967296 if obj == 1035 else 65536))
            for i in range(count)]


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("SETEX Controller v0.9.9 - Status / Alarm / Intervent")
        self.root.geometry("960x780")
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.busy = False
        self.alarm_polling = False
        self.detail_requested = threading.Event()
        self.rows = []
        self.ip = tk.StringVar(value="172.16.120.113")
        self.port = tk.StringVar(value="50000")
        self.mode = tk.StringVar(value="LIVE Controller (eksperimental)")
        self.service = tk.StringVar(value="SV_READ (1)")
        self.obj = tk.StringVar(value="IW - Info Words")
        self.quantity = tk.StringVar(value="Satuan")
        self.start = tk.StringVar(value="1")
        self.count = tk.StringVar(value="5")
        self.schedule = tk.StringVar(value="Sekali")
        self.interval = tk.StringVar(value="2")
        self.write_value = tk.StringVar()
        self.temp_parameter = tk.StringVar(value=next(iter(PARAMETERS)))
        self.function_name = tk.StringVar(value='141 - Temperature Control')
        self.temp_new = tk.StringVar()
        self.fill_min = tk.StringVar()
        self.fill_max = tk.StringVar()
        self.temp_info = tk.StringVar(value='Belum dibaca. Pilih fungsi sesuai proses pada HMI. Pembacaan tidak membuktikan fungsi aktif.')
        self.temp_snapshot = None
        self.temp_target = None
        self.status = tk.StringVar(value="LIVE eksperimental: mulai dengan SV_READ / IW / alamat 1 / Sekali. Belum diuji pada PLC fisik.")
        box = ttk.Frame(root, padding=16)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="SETEX • Controller Read / Write", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(box, text=f"v0.9.9 • Status / Alarm • Fill / Temperature / Drain • Intervent 109/3 → 106/6 → 110/3").pack(anchor="w", pady=(3, 12))
        form = ttk.Frame(box)
        form.pack(fill="x")
        self.controls = []
        fields = [("IP mesin", self.ip, None), ("Port TCP", self.port, None),
                  ("Sumber data", self.mode, ["LIVE Controller (eksperimental)", "SIMULASI"]),
                  ("Perintah", self.service, list(SERVICES)),
                  ("Objek", self.obj, list(OBJECTS)),
                  ("Jumlah data", self.quantity, ["Satuan", "Lebih dari 1"]),
                  ("Alamat awal / daftar", self.start, None), ("Jumlah (untuk rentang)", self.count, None),
                  ("Pembacaan", self.schedule, ["Sekali", "Cyclic"]),
                  ("Interval (detik, minimal 1)", self.interval, None)]
        for i, (label, var, choices) in enumerate(fields):
            col, row = (i % 2) * 2, i // 2
            ttk.Label(form, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=5)
            widget = (ttk.Combobox(form, textvariable=var, values=choices, state="readonly", width=23)
                      if choices else ttk.Entry(form, textvariable=var, width=26))
            widget.grid(row=row, column=col + 1, sticky="ew", padx=(0, 20), pady=5)
            self.controls.append((widget, "readonly" if choices else "normal"))
            if var is self.obj:
                self.object_combo = widget
            if var is self.service:
                self.service_combo = widget
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        self.object_hint = tk.StringVar()
        ttk.Label(box, textvariable=self.object_hint, wraplength=840).pack(anchor="w", pady=(8, 0))
        buttons = ttk.Frame(box)
        buttons.pack(fill="x", pady=12)
        self.run_button = ttk.Button(buttons, text="Mulai baca", command=self.run)
        self.run_button.pack(side="left")
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        self.probe_button = ttk.Button(buttons, text="Tes TCP saja", command=self.probe)
        self.probe_button.pack(side="left")
        ttk.Button(buttons, text="Ekspor CSV", command=self.export).pack(side="right")
        alarm_controls = ttk.Frame(box)
        alarm_controls.pack(fill='x', pady=(0, 5))
        self.alarm_button = ttk.Button(alarm_controls, text='Baca status 112/0', command=self.run_alarms)
        self.alarm_button.pack(side='left')
        self.alarm_detail_button = ttk.Button(alarm_controls, text='Baca detail alarm', command=self.request_alarm_detail)
        self.alarm_detail_button.pack(side='left', padx=4)
        ttk.Label(alarm_controls, text='Detail:').pack(side='left', padx=6)
        self.alarm_detail = tk.StringVar(value='65 - Bitmask 1–2000')
        alarm_combo = ttk.Combobox(alarm_controls, textvariable=self.alarm_detail,
                                  values=['65 - Bitmask 1–2000', '67 - Daftar maksimal 100 ID'], state='readonly', width=28)
        alarm_combo.pack(side='left')
        self.controls.append((alarm_combo, 'readonly'))
        ttk.Label(alarm_controls, text='Status: Sekali/Cyclic. Detail: klik manual.').pack(side='left', padx=6)
        write_box = ttk.LabelFrame(box, text="SV_WRITE (2) — satu alamat, satu kali", padding=8)
        write_box.pack(fill="x", pady=(0, 6))
        ttk.Label(write_box, text="Nilai mentah baru (0..65535)").pack(side="left")
        write_entry = ttk.Entry(write_box, textvariable=self.write_value, width=12)
        write_entry.pack(side="left", padx=8)
        self.controls.append((write_entry, 'normal'))
        self.write_button = ttk.Button(write_box, text="Baca nilai lama → Konfirmasi write", command=self.prepare_write)
        self.write_button.pack(side="left")
        temp_box = ttk.LabelFrame(box, text='Nilai fungsi Controller — bukan pembacaan Program List / PRG', padding=6)
        temp_box.pack(fill='x', pady=(0, 6))
        function_combo = ttk.Combobox(temp_box, textvariable=self.function_name, values=list(FUNCTIONS), width=34, state='readonly')
        function_combo.pack(anchor='w', pady=(0, 4))
        self.controls.append((function_combo, 'readonly'))
        ttk.Label(temp_box, textvariable=self.temp_info, wraplength=870).pack(anchor='w')
        fill_controls = ttk.Frame(temp_box)
        fill_controls.pack(fill='x', pady=(3, 0))
        ttk.Label(fill_controls, text='Batas Fill dari HMI (L): min').pack(side='left')
        self.fill_min_entry = ttk.Entry(fill_controls, textvariable=self.fill_min, width=9)
        self.fill_min_entry.pack(side='left', padx=5)
        ttk.Label(fill_controls, text='maks').pack(side='left')
        self.fill_max_entry = ttk.Entry(fill_controls, textvariable=self.fill_max, width=9)
        self.fill_max_entry.pack(side='left', padx=5)
        self.controls.extend([(self.fill_min_entry, 'normal'), (self.fill_max_entry, 'normal')])
        ttk.Label(fill_controls, text='Wajib untuk ubah Fill; bukan batas otomatis dari mesin.').pack(side='left')
        parameter_frame = ttk.Frame(temp_box)
        parameter_frame.pack(fill='x', pady=(4, 0))
        self.parameter_table = ttk.Treeview(parameter_frame, columns=('slot', 'id', 'name', 'current', 'unit', 'access'),
                                            show='headings', height=3)
        for key, title, width in [('slot', 'Slot', 45), ('id', 'ID parameter', 85),
                                  ('name', 'Nama dari ID balasan', 240), ('current', 'Nilai terbaca', 110),
                                  ('unit', 'Satuan', 85), ('access', 'Status', 175)]:
            self.parameter_table.heading(key, text=title)
            self.parameter_table.column(key, width=width)
        parameter_scroll = ttk.Scrollbar(parameter_frame, orient='vertical', command=self.parameter_table.yview)
        self.parameter_table.configure(yscrollcommand=parameter_scroll.set)
        self.parameter_table.pack(side='left', fill='x', expand=True)
        parameter_scroll.pack(side='right', fill='y')
        self.parameter_table.bind('<<TreeviewSelect>>', self.select_parameter_row)
        temp_controls = ttk.Frame(temp_box)
        temp_controls.pack(fill='x', pady=(5, 0))
        self.intervent_slot = tk.StringVar(value='')
        ttk.Label(temp_controls, text='Slot aktif (1–13):').pack(side='left')
        slot_entry = ttk.Entry(temp_controls, textvariable=self.intervent_slot, width=3)
        slot_entry.pack(side='left', padx=4)
        self.controls.append((slot_entry, 'normal'))
        self.temp_read_button = ttk.Button(temp_controls, text='1. Baca fungsi', command=self.read_temp_function)
        self.temp_read_button.pack(side='left')
        temp_combo = ttk.Combobox(temp_controls, textvariable=self.temp_parameter, values=list(PARAMETERS), width=24, state='readonly')
        self.temp_combo = temp_combo
        temp_combo.bind('<<ComboboxSelected>>', self.fill_current_parameter)
        temp_combo.pack(side='left', padx=6)
        temp_entry = ttk.Entry(temp_controls, textvariable=self.temp_new, width=10)
        self.temp_entry = temp_entry
        temp_entry.pack(side='left')
        self.controls.extend([(temp_combo, 'readonly'), (temp_entry, 'normal')])
        self.temp_change_button = ttk.Button(temp_controls, text='2. Konfirmasi ubah', command=self.change_temp_function)
        self.temp_change_button.pack(side='left', padx=6)
        ttk.Label(box, textvariable=self.status, wraplength=840, foreground="#9b4500").pack(anchor="w", pady=6)
        frame = ttk.Frame(box)
        frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(frame, columns=("time", "mode", "obj", "address", "raw", "hex"), show="headings")
        for name, label, width in [("time", "Waktu", 155), ("mode", "Sumber", 90),
                                  ("obj", "Objek", 160), ("address", "Alamat", 80),
                                  ("raw", "Nilai mentah", 100), ("hex", "Hex", 80)]:
            self.table.heading(name, text=label)
            self.table.column(name, width=width)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Label(box, text="Nilai tampil mentah. Mapping sensor, skala, dan satuan perlu validasi per mesin.").pack(anchor="w", pady=(8, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.mode.trace_add("write", self.update_choices)
        self.obj.trace_add("write", self.update_object_hint)
        self.function_name.trace_add('write', self.update_function_choice)
        self.fill_min.trace_add('write', self.sync_intervent_controls)
        self.fill_max.trace_add('write', self.sync_intervent_controls)
        self.update_choices()
        self.sync_intervent_controls()
        root.after(100, self.drain)

    def update_choices(self, *_):
        live = self.mode.get() != "SIMULASI"
        choices = WORD_OBJECTS if live else OBJECTS
        services = list(SERVICES)[:2] if live else list(SERVICES)
        self.object_combo.configure(values=list(choices))
        self.service_combo.configure(values=services)
        if self.obj.get() not in choices:
            self.obj.set("IW - Info Words")
        if self.service.get() not in services:
            self.service.set("SV_READ (1)")
        self.update_object_hint()

    def update_object_hint(self, *_):
        obj = OBJECTS[self.obj.get()]
        self.object_hint.set(f"Object ID {obj} / 0x{obj:04X} • " +
                             OBJECT_HELP.get(obj, "Objek bit: simulasi saja."))
        if not self.busy:
            self.rows.clear()
            self.table.delete(*self.table.get_children())

    def target(self):
        host = str(ipaddress.ip_address(self.ip.get().strip()))
        port = int(self.port.get())
        if not 1 <= port <= 65535:
            raise ValueError("Port harus 1..65535.")
        return host, port

    def set_busy(self, value):
        self.busy = value
        if not value:
            self.alarm_polling = False
            self.detail_requested.clear()
        for widget, state in self.controls:
            widget.configure(state="disabled" if value else state)
        self.run_button.configure(state="disabled" if value else "normal")
        self.probe_button.configure(state="disabled" if value else "normal")
        self.alarm_button.configure(state="disabled" if value else "normal")
        self.alarm_detail_button.configure(state="normal" if not value or self.alarm_polling else "disabled")
        self.write_button.configure(state="disabled" if value else "normal")
        self.temp_read_button.configure(state="disabled" if value else "normal")
        self.sync_intervent_controls()
        self.stop_button.configure(state="normal" if value else "disabled")

    def show_temp(self, snapshot):
        self.parameter_table.delete(*self.parameter_table.get_children())
        editable = []
        self.parameter_row_labels = {}
        for slot, pid, name, value, unit, label in parameter_rows(snapshot):
            row_id = self.parameter_table.insert('', 'end', values=(slot, pid or '—', name,
                f'{value:g}' if pid else '—', unit, 'Eksperimental' if label else 'Baca saja'))
            if label:
                editable.append(label)
                self.parameter_row_labels[row_id] = label
        self.temp_combo.configure(values=editable)
        self.temp_parameter.set(editable[0] if editable else 'Baca saja — ID/batas belum cocok')
        if snapshot.function_id == 713:
            self.temp_info.set(f'Fungsi 713, baris {snapshot.line} • P1={snapshot.values[0]:g} (kode jenis air) • '
                               f'P2={snapshot.values[1]:g} L • Isi batas min/maks sesuai HMI untuk mengubah P2.')
        else:
            units = ('°C', '°C/min', 'min') if snapshot.function_id == 141 else ('%', 'kode drain', 'min')
            self.temp_info.set(f'Fungsi {snapshot.function_id}, baris {snapshot.line} • '
                               f'P1={snapshot.values[0]:g} {units[0]} • P2={snapshot.values[1]:g} {units[1]} • P3={snapshot.values[2]:g} {units[2]}')
        self.sync_intervent_controls()

    def get_fill_limits(self):
        minimum = float(self.fill_min.get().strip().replace(',', '.'))
        maximum = float(self.fill_max.get().strip().replace(',', '.'))
        if not math.isfinite(minimum) or not math.isfinite(maximum) or not 0 <= minimum < maximum:
            raise ValueError('Isi batas Fill sesuai HMI: 0 ≤ minimum < maksimum, dalam liter.')
        return minimum, maximum

    def sync_intervent_controls(self, *_):
        snapshot = self.temp_snapshot
        fill_selected = FUNCTIONS[self.function_name.get()] == 713
        for entry in (self.fill_min_entry, self.fill_max_entry):
            entry.configure(state='normal' if fill_selected and not self.busy else 'disabled')
        can_edit = (not self.busy and snapshot is not None and
                    any(row[-1] for row in parameter_rows(snapshot)))
        if can_edit and snapshot.function_id == 713:
            try:
                self.get_fill_limits()
            except ValueError:
                can_edit = False
        self.temp_change_button.configure(state='normal' if can_edit else 'disabled')
        self.temp_entry.configure(state='normal' if can_edit else 'disabled')

    def fill_current_parameter(self, *_):
        if self.temp_snapshot is not None:
            spec = PROFILE_PARAMETERS[self.temp_snapshot.function_id].get(self.temp_parameter.get())
            if spec:
                self.temp_new.set(f'{self.temp_snapshot.values[spec[0]]:g}')

    def select_parameter_row(self, *_):
        if self.busy:
            return
        selected = self.parameter_table.selection()
        label = getattr(self, 'parameter_row_labels', {}).get(selected[0]) if selected else None
        if label:
            self.temp_parameter.set(label)
            self.fill_current_parameter()

    def update_function_choice(self, *_):
        self.parameter_table.delete(*self.parameter_table.get_children())
        choices = PROFILE_PARAMETERS[FUNCTIONS[self.function_name.get()]]
        self.temp_combo.configure(values=list(choices))
        self.temp_parameter.set(next(iter(choices), 'Baca saja — batas belum dipetakan'))
        self.temp_snapshot = None
        self.temp_target = None
        self.temp_new.set('')
        self.sync_intervent_controls()
        self.temp_info.set('Pilihan fungsi berubah. Klik Baca fungsi dahulu; data fungsi sebelumnya tidak dipakai.')

    def read_temp_function(self):
        if self.busy:
            return
        try:
            if self.mode.get() == 'SIMULASI':
                raise ValueError('Intervent membutuhkan LIVE Controller; tidak memakai data simulasi.')
            target = self.target()
            function_id = FUNCTIONS[self.function_name.get()]
        except ValueError as exc:
            messagebox.showerror('Intervent', str(exc))
            return
        self.temp_snapshot = None
        self.temp_target = None
        self.stop_event.clear()
        self.set_busy(True)
        self.temp_info.set(f'Membaca fungsi {function_id} ...')
        self.status.set('SV_READ / object 6: hanya membaca fungsi; belum mengirim SV_CHANGE.')

        def worker():
            try:
                snapshot = read_temperature(*target, self.stop_event, function_id)
                self.events.put(('temp_read', (target, snapshot)))
            except Exception as exc:
                self.events.put(('temp_error', f'Baca fungsi gagal; SV_CHANGE tidak dikirim: {exc}'))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def change_temp_function(self):
        if self.busy:
            return
        try:
            target = self.target()
            snapshot = self.temp_snapshot
            if (self.mode.get() == 'SIMULASI' or snapshot is None or target != self.temp_target
                    or snapshot.function_id != FUNCTIONS[self.function_name.get()]):
                raise ValueError('Klik Baca fungsi pada IP/port yang sama terlebih dahulu.')
            parameter = self.temp_parameter.get()
            value = float(self.temp_new.get().strip().replace(',', '.'))
            fill_limits = self.get_fill_limits() if snapshot.function_id == 713 else None
            values = changed_values(snapshot, parameter, value, fill_limits)
            slot = int(self.intervent_slot.get().strip())
            if not 1 <= slot <= 13:
                raise ValueError('Slot fungsi aktif harus 1..13; ini bukan nomor step program.')
        except ValueError as exc:
            messagebox.showerror('Intervent', str(exc))
            return
        host, port = target
        index = PROFILE_PARAMETERS[snapshot.function_id][parameter][0]
        expected_ids = PROFILE_IDS[snapshot.function_id]
        pid = snapshot.parameter_ids[index] if snapshot.parameter_ids else expected_ids[index]
        old_val = snapshot.values[index]
        if not messagebox.askyesno('Konfirmasi Intervent Parameter (ProcessInfo)',
            f'Tujuan: {host}:{port}\n'
            f'Jalur: Masuk Manual 109/3 → Simpan 106/6 → Keluar Manual 110/3\n'
            f'Fungsi: {self.function_name.get()}, SLOT AKTIF {slot} (bukan step)\n'
            f'Parameter: {parameter} (ID definisi {pid})\n'
            f'Nilai lama: {old_val:g} -> Nilai baru: {value:g}\n'
            + (f'Batas Fill yang Anda isi: {fill_limits[0]:g}..{fill_limits[1]:g} L\n' if fill_limits else '') +
            f'Seluruh enam nilai fungsi dikirim; hanya parameter pilihan diubah.\n\n'
            'Pastikan fungsi proses yang dimaksud sedang aktif pada mesin ini.\n'
            'Kirim satu perubahan parameter? Ini tidak mengubah resep permanen.', default='no'):
            return
        self.temp_snapshot = None  # Every intervention requires a fresh explicit read.
        self.stop_event.clear()
        self.set_busy(True)
        self.status.set('Memeriksa fungsi → Masuk Intervent → Simpan → Selesai → Baca ulang ...')

        def worker():
            try:
                result = change_temperature_once(host, port, snapshot, parameter, value, self.stop_event,
                                                 fill_limits=fill_limits, slot=slot,
                                                 progress=lambda text: self.events.put(('intervent_progress', text)))
                self.events.put(('temp_result', (snapshot.line, values, result)))
            except Exception as exc:
                self.events.put(('temp_error', f'Intervent gagal: {exc}'))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def prepare_write(self):
        if self.busy:
            return
        try:
            if self.mode.get() == 'SIMULASI':
                raise ValueError('Write hanya tersedia dalam mode LIVE Controller.')
            if self.schedule.get() != 'Sekali':
                raise ValueError('Pilih Sekali untuk write. Cyclic hanya untuk baca.')
            host, port = self.target()
            addresses = parse_addresses(self.start.get(), self.quantity.get(), self.count.get())
            if len(addresses) != 1:
                raise ValueError('Write versi ini hanya satu alamat. Hapus daftar/rentang dan pilih Satuan.')
            value = int(self.write_value.get().strip(), 10)
            obj_name = self.obj.get()
            obj, address = OBJECTS[obj_name], addresses[0]
            build_write(obj, address, value)
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror('Write belum dapat diproses', str(exc))
            return
        self.stop_event.clear()
        self.set_busy(True)
        self.status.set(f'Membaca nilai lama {obj_name} alamat {address}; belum mengirim write ...')
        # Snapshot target retained through confirmation, unaffected by later edits.
        target = (host, port, obj_name, obj, address, value)

        def worker():
            try:
                old = read_live(host, port, 1, obj, address, 1, self.stop_event)[0]
                self.events.put(('confirm_write', (target, old)))
            except Exception as exc:
                self.events.put(('status', f'Persiapan gagal; write belum dikirim: {exc}'))
                self.events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def confirm_write(self, target, old):
        if self.stop_event.is_set():
            self.status.set('Write dibatalkan sebelum pengiriman.')
            self.set_busy(False)
            return
        host, port, obj_name, obj, address, value = target
        confirmed = messagebox.askyesno('Konfirmasi SV_WRITE — PLC asli',
            f'Tujuan: {host}:{port}\nObjek: {obj_name} (ID {obj})\nAlamat: {address}\n\n'
            f'Nilai lama: {old} (0x{old:04X})\nNilai baru: {value} (0x{value:04X})\n\n'
            'Kirim satu perintah write ke alamat ini?\nNilai adalah uint16 mentah, tanpa konversi satuan.',
            default='no')
        if not confirmed:
            self.status.set('Write dibatalkan; tidak ada perintah write dikirim.')
            self.set_busy(False)
            return
        self.status.set('Memeriksa ulang nilai lama, mengirim write sekali, lalu membaca kembali ...')

        def worker():
            try:
                result = write_once_verified(host, port, obj, address, value, old, self.stop_event)
                self.events.put(('write_result', (target, result)))
            except Exception as exc:
                self.events.put(('status', f'Write dibatalkan sebelum pengiriman: {exc}'))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def run_alarms(self):
        if self.busy:
            return
        try:
            host, port = self.target()
            if self.mode.get() == 'SIMULASI':
                raise ValueError('Status/alarm memerlukan LIVE Controller; tidak menampilkan alarm buatan.')
            cyclic = self.schedule.get() == 'Cyclic'
            interval = float(self.interval.get().replace(',', '.')) if cyclic else 1.
            if not math.isfinite(interval) or interval < 1:
                raise ValueError('Interval minimal 1 detik.')
            detail_object = int(self.alarm_detail.get().split(' ')[0])
        except ValueError as exc:
            messagebox.showerror('Status / Alarm', str(exc))
            return
        self.rows.clear()
        self.table.delete(*self.table.get_children())
        self.stop_event.clear()
        self.set_busy(True)
        self.alarm_polling = True
        self.alarm_detail_button.configure(state='normal')
        self.status.set('Membaca 112/0 saja. Detail hanya diminta saat tombol diklik.')
        def worker():
            try:
                while not self.stop_event.is_set():
                    result = read_status_alarms(host, port, self.stop_event, detail_object)
                    self.events.put(('alarms', (datetime.now().astimezone().isoformat(timespec='seconds'), result)))
                    if not cyclic:
                        break
                    deadline = time.monotonic() + interval
                    while not self.stop_event.is_set():
                        if self.detail_requested.is_set():
                            self.detail_requested.clear()
                            self.fetch_alarm_detail(host, port, detail_object)
                        remaining = deadline - time.monotonic()
                        if remaining <= 0 or self.stop_event.wait(min(0.1, remaining)):
                            break
            except Exception as exc:
                self.events.put(('status', f'Status/alarm berhenti: {exc}. Hasil sebelumnya bukan status terkini.'))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def request_alarm_detail(self):
        if self.busy:
            if self.alarm_polling:
                self.detail_requested.set()
                self.alarm_detail_button.configure(state='disabled')
            return
        try:
            host, port = self.target()
            if self.mode.get() == 'SIMULASI':
                raise ValueError('Detail alarm memerlukan LIVE Controller.')
            obj = int(self.alarm_detail.get().split(' ')[0])
        except ValueError as exc:
            messagebox.showerror('Detail alarm', str(exc))
            return
        self.stop_event.clear()
        self.set_busy(True)
        def worker():
            try:
                self.fetch_alarm_detail(host, port, obj)
            finally:
                self.events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def fetch_alarm_detail(self, host, port, obj):
        try:
            result = read_alarm_detail(host, port, self.stop_event, obj)
            self.events.put(('alarm_detail', (host, port, obj, datetime.now().astimezone().isoformat(timespec='seconds'), result)))
        except Exception as exc:
            self.events.put(('detail_error', str(exc)))

    def show_alarm_detail(self, host, port, obj, stamp, result):
        # Separate window keeps explicitly requested details visible during status polling.
        window = tk.Toplevel(self.root)
        window.title(f'Detail alarm {host}:{port} — 1/{obj}')
        text = tk.Text(window, width=65, height=20, wrap='word')
        text.pack(fill='both', expand=True)
        body = f"{stamp}\nJumlah dilaporkan: {result['count']}\nID terbaca: {len(result['ids'])}\n\n"
        body += '\n'.join(f'#{n:03d}' for n in result['ids']) or 'Tidak ada ID alarm aktif.'
        if result['truncated']:
            body += '\nDaftar terpotong; gunakan objek 65.'
        if not result['count_matches']:
            body += '\nJumlah dan detail berbeda; perlu verifikasi.'
        text.insert('1.0', body + '\n\nSnapshot saat diminta; tidak diperbarui otomatis. Nama alarm belum dipetakan.')
        text.configure(state='disabled')

    def show_alarms(self, stamp, result):
        status, detail = result['status'], result['detail']
        entries = [('Jumlah alarm aktif', 'NumberOfAlarms', status['count']),
                   ('Alarm utama (ID)', 'StatusLineAlarm', status['priority']),
                   ('Komunikasi (raw)', 'ComAlarm', status['communication']),
                   ('Stop (raw)', 'StopAlarm', status['stop']),
                   ('Halt (raw)', 'HaltAlarm', status['halt'])]
        if detail is not None:
            entries.extend(('Alarm aktif (ID)', f'#{alarm_id:03d}', alarm_id) for alarm_id in detail['ids'])
        # Latest snapshot only: no obsolete alarm rows remain on screen.
        self.rows.clear()
        self.table.delete(*self.table.get_children())
        for label, field, value in entries:
            row = (stamp, 'LIVE Status/Alarm', label, field, value, f'0x{value:04X}')
            self.rows.append(row)
            self.table.insert('', 'end', values=row)
        text = f"{stamp} • {status['count']} alarm aktif • alarm utama #{status['priority']:03d}."
        if result['detail_error']:
            text += ' Detail belum terbaca: ' + result['detail_error']
        elif detail is not None:
            text += f" Detail: {len(detail['ids'])} ID, jumlah dilaporkan {detail['count']}."
            if detail['truncated']:
                text += ' Daftar terpotong; gunakan objek 65.'
            if not detail['count_matches'] or detail['count'] != status['count']:
                text += ' Jumlah berbeda; status mungkin berubah antar pembacaan atau layout belum cocok.'
        text += ' Klik Baca detail alarm untuk meminta daftar ID; tidak otomatis.'
        self.status.set(text)

    def run(self):
        if self.busy:
            return
        try:
            host, port = self.target()
            mode, service, obj = self.mode.get(), SERVICES[self.service.get()], OBJECTS[self.obj.get()]
            addresses = parse_addresses(self.start.get(), self.quantity.get(), self.count.get())
            start, count = addresses[0], len(addresses)
            contiguous = addresses == list(range(start, start + count))
            if service != 1 and not contiguous:
                raise ValueError('Daftar alamat terpisah memakai SV_READ (1). Pilih perintah tersebut.')
            cyclic = self.schedule.get() == "Cyclic"
            interval = float(self.interval.get()) if cyclic else 1.0
            if not math.isfinite(interval) or interval < 1:
                raise ValueError("Interval harus angka minimal 1 detik.")
            for address in addresses:
                validate_request(service, obj, address, 1)
            if mode != "SIMULASI":
                build_read(service, obj, start, 1 if service == 1 else min(count, 121 if obj == 1035 else 240))
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("Belum dapat membaca", str(exc))
            return
        self.rows.clear()
        self.table.delete(*self.table.get_children())
        self.stop_event.clear()
        self.set_busy(True)
        self.status.set("SIMULASI: angka buatan." if mode == "SIMULASI" else f"LIVE: membaca {host}:{port} ...")

        def worker():
            tick = 0
            try:
                while not self.stop_event.is_set():
                    if service == 1:
                        values = []
                        for index, address in enumerate(addresses):
                            if self.stop_event.is_set() or (index and self.stop_event.wait(1)):
                                raise InterruptedError('Dihentikan.')
                            values.extend(read_values(mode, service, obj, address, 1, tick)
                                          if mode == 'SIMULASI' else
                                          read_live(host, port, service, obj, address, 1, self.stop_event))
                    else:
                        values = (read_values(mode, service, obj, start, count, tick)
                                  if mode == "SIMULASI" else read_live(host, port, service, obj, start, count, self.stop_event))
                    self.events.put(("values", (datetime.now().astimezone().isoformat(timespec="seconds"),
                                               self_name, addresses, values, mode)))
                    tick += 1
                    if not cyclic or self.stop_event.wait(interval):
                        break
            except Exception as exc:
                self.events.put(("status", f"Baca berhenti: {exc}"))
            finally:
                self.events.put(("done", None))

        self_name = self.obj.get()
        threading.Thread(target=worker, daemon=True).start()

    def probe(self):
        if self.busy:
            return
        try:
            target = self.target()
        except ValueError as exc:
            messagebox.showerror("IP/port tidak valid", str(exc))
            return
        self.stop_event.clear()
        self.set_busy(True)
        self.status.set("Mencoba koneksi TCP (timeout 3 detik)...")

        def worker():
            try:
                with socket.create_connection(target, timeout=3):
                    result = "TCP tersambung. Ini belum membuktikan protokol SETEX atau izin baca PLC."
            except OSError as exc:
                result = f"TCP gagal: {exc}"
            self.events.put(("status", result))
            self.events.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

    def stop(self):
        self.stop_event.set()
        self.status.set("Menghentikan proses; tes TCP menunggu timeout maksimal 3 detik.")

    def drain(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "values":
                    stamp, obj, addresses, values, mode = data
                    for i, value in enumerate(values):
                        width = 8 if OBJECTS.get(obj) == 1035 else 4
                        row = (stamp, mode, obj, addresses[i], value, f"0x{value:0{width}X}")
                        self.rows.append(row)
                        self.table.insert("", "end", values=row)
                    # Batas memori untuk sesi cyclic panjang; ekspor hanya 5000 baris terakhir.
                    self.rows[:] = self.rows[-5000:]
                    children = self.table.get_children()
                    if len(children) > 5000:
                        self.table.delete(*children[:-5000])
                    self.table.yview_moveto(1)
                    self.status.set(f"{mode} • {stamp} • {len(values)} nilai mentah • maksimal 5000 baris.")
                elif kind == 'alarm_detail':
                    self.show_alarm_detail(*data)
                    self.alarm_detail_button.configure(state='normal' if not self.busy or self.alarm_polling else 'disabled')
                elif kind == 'detail_error':
                    messagebox.showerror('Detail alarm gagal', data)
                    self.alarm_detail_button.configure(state='normal' if not self.busy or self.alarm_polling else 'disabled')
                elif kind == "alarms":
                    self.show_alarms(*data)
                elif kind == "status":
                    self.status.set(data)
                elif kind == 'confirm_write':
                    self.confirm_write(*data)
                elif kind == 'temp_read':
                    self.temp_target, self.temp_snapshot = data
                    self.show_temp(self.temp_snapshot)
                    self.fill_current_parameter()
                    editable = any(row[-1] for row in parameter_rows(self.temp_snapshot))
                    self.status.set('Nilai fungsi Controller terbaca; tidak mengambil nilai resep dari Program List. ' +
                                    ('Pilih baris parameter untuk perubahan eksperimental.' if editable else
                                     'Baca saja: tidak ada slot yang batas/ID-nya terverifikasi untuk diubah.'))
                elif kind == 'temp_error':
                    self.temp_info.set(data)
                    self.status.set(data)
                elif kind == 'intervent_progress':
                    self.status.set(data)
                elif kind == 'temp_result':
                    expected_line, expected, result = data
                    actual = result['readback']
                    if actual is not None:
                        self.show_temp(actual)
                    matches = actual is not None and actual.line == expected_line and all(math.isclose(a, b, rel_tol=0, abs_tol=0.0001)
                                                         for a, b in zip(actual.values, expected))
                    text = ('ACK diterima dan parameter fungsi hasil baca ulang cocok.'
                            if matches and result['acknowledged'] and result.get('manual_exited') else
                            'Hasil SV_CHANGE belum terkonfirmasi cocok. Periksa HMI dan log; tidak ada retry otomatis.')
                    text += ' Tahap: ' + ' → '.join(stage['stage'] + (' OK' if stage['ok'] else ' GAGAL') for stage in result.get('stages', []))
                    if result.get('manual_uncertain'):
                        text += ' STATUS MANUAL BELUM PASTI: periksa dan selesaikan Intervent melalui HMI.'
                    if result['ack_error']:
                        text += ' ACK: ' + result['ack_error']
                    if result['readback_error']:
                        text += ' Baca ulang: ' + result['readback_error']
                    self.status.set(text)
                elif kind == 'write_result':
                    target, result = data
                    host, port, name, obj, address, value = target
                    actual = result['readback']
                    if actual is not None:
                        row = (datetime.now().astimezone().isoformat(timespec='seconds'),
                               'LIVE baca ulang write', name, address, actual, f'0x{actual:04X}')
                        self.rows.append(row)
                        self.table.insert('', 'end', values=row)
                        self.rows[:] = self.rows[-5000:]
                        children = self.table.get_children()
                        if len(children) > 5000:
                            self.table.delete(*children[:-5000])
                        self.table.yview_moveto(1)
                    if actual == value and result['acknowledged']:
                        text = f'ACK diterima; baca ulang {name}[{address}] = {actual}, sesuai nilai yang diminta.'
                    elif actual is not None:
                        text = (f'Baca ulang {name}[{address}] = {actual}; diminta {value}. '
                                + ('ACK tidak terkonfirmasi. ' if not result['acknowledged'] else 'Nilai tidak cocok. '))
                    else:
                        text = 'Hasil write belum terkonfirmasi; baca ulang gagal/dihentikan. Jangan anggap write gagal diterapkan.'
                    if result['ack_error']:
                        text += f" Detail ACK: {result['ack_error']}"
                    if result['readback_error']:
                        text += f" Detail baca ulang: {result['readback_error']}"
                    self.status.set(text)
                elif kind == "done":
                    self.set_busy(False)
        except queue.Empty:
            pass
        self.root.after(100, self.drain)

    def export(self):
        if not self.rows:
            messagebox.showinfo("CSV", "Belum ada data.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="SETEX_DATA.csv",
                                          filetypes=[("CSV", "*.csv")])
        if path:
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(["waktu", "sumber", "objek", "alamat", "raw", "hex"])
                    writer.writerows(self.rows)
                self.status.set(f"CSV disimpan: {path}")
            except OSError as exc:
                messagebox.showerror("Gagal menyimpan", str(exc))

    def close(self):
        self.stop_event.set()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
