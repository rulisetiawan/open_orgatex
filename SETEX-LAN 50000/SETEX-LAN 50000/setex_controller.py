"""Experimental SC737 TCP reader reconstructed from 6A x86 DLLs.

No remote screen/keyboard services. Hardware compatibility remains unverified.
"""
import json
import math
import socket
import struct
import threading
import time
from datetime import datetime
from pathlib import Path

FRAME_SIZE = 516
LOG_PATH = Path(__file__).resolve().parent / 'controller_packets.jsonl'
LOG_LOCK = threading.Lock()
ALLOWED_OBJECTS = {1001, 1002, 1009, 1010, 1025, 1026, 1035, 1057, 1058}


class ProtocolError(RuntimeError):
    pass


def build_read(service, obj, address, count=1):
    if service not in (1, 11) or obj not in ALLOWED_OBJECTS:
        raise ValueError('LIVE hanya mendukung SV_READ dan SV_READ_BLOCK pada objek PLC terpilih.')
    if obj in (1002, 1026, 1057):
        raise ValueError('Decoder bit LIVE belum terverifikasi. Pilih objek word dahulu.')
    if not 0 <= address <= 65535 or not 1 <= count <= 240 or address + count > 65536:
        raise ValueError('Rentang alamat tidak valid.')
    if service == 11 and count * (4 if obj == 1035 else 2) > 486:
        raise ValueError('Block melebihi kapasitas frame; gunakan read_live untuk pemecahan otomatis.')
    if service == 1 and count != 1:
        raise ValueError('SV_READ mengirim satu alamat per transaksi.')
    payload = struct.pack('<H', address) if service == 1 else struct.pack('<HH', address, count)
    frame = bytearray(FRAME_SIZE)
    struct.pack_into('<HH', frame, 0, 2, 16 + len(payload))
    # Server rewrites routing bytes 4,5 and socket ticket at 7.
    # Api_* sets word +9 to 1, message type +14 to 1, service +15,
    # object +16, data length +18, data +20.
    frame[4:7] = bytes((10, 12, 0))
    struct.pack_into('<H', frame, 9, 1)
    frame[14] = 1
    frame[15] = service
    struct.pack_into('<HH', frame, 16, obj, len(payload))
    frame[20:20 + len(payload)] = payload
    return bytes(frame)


def parse_response(frame, service, obj, count):
    size = validate_response(frame, service, obj)
    width, code = (4, 'I') if obj == 1035 else (2, 'H')
    if size != count * width:
        raise ProtocolError(f'Payload {size} byte, diharapkan {count * width}. '
                            'Nilai tidak ditampilkan karena layout balasan belum cocok.')
    return list(struct.unpack_from('<' + code * count, frame, 20))


def validate_response(frame, service, obj):
    if len(frame) != FRAME_SIZE:
        raise ProtocolError(f'Frame harus {FRAME_SIZE} byte; diterima {len(frame)}.')
    magic, declared = struct.unpack_from('<HH', frame)
    reply_obj, size = struct.unpack_from('<HH', frame, 16)
    if magic != 2 or size > 486 or declared != size + 16:
        raise ProtocolError('Magic/panjang balasan tidak cocok dengan format hasil penelusuran DLL.')
    if frame[15] != service or reply_obj != obj:
        raise ProtocolError(f'Balasan bukan perintah/objek yang diminta: service={frame[15]}, object={reply_obj}.')
    if frame[14] != 2:
        if frame[14] == 3 and size >= 4:
            api_code, error_code = struct.unpack_from('<HH', frame, 20)
            api_name = {19: 'API_PRA_ERROR (pengolahan program)'}.get(api_code, 'API error')
            error_name = {62: 'Invalid status', 66: 'Invalid service', 81: 'Invalid line no (slot fungsi)', 84: 'Function ID mismatch', 93: 'Step change active', 94: 'Function not active',
                          95: 'Function active', 115: 'Parameter transfer error',
                          116: 'Invalid parameter number', 117: 'Invalid parameter count',
                          124: 'Parameter too small', 125: 'Parameter too big'}.get(error_code, 'Controller error')
            raise ProtocolError(f'Controller menolak service {service}, object {obj}: '
                                f'API {api_code} — {api_name}; error {error_code} — {error_name}. '
                                'Periksa status proses dan konteks target; kode ini tidak membuktikan masalah PIN.')
        raise ProtocolError(f'Controller tidak mengirim respons data (jenis={frame[14]}, '
                            f'payload={frame[20:20+size].hex(" ")}). Lihat log paket.')
    return size


def build_write(obj, address, value):
    if obj == 1035:
        raise ValueError('Counter konsumsi 1035 hanya baca; write/reset tidak tersedia.')
    # Api_WritePLCWord: service 2, length 4, uint16 address + uint16 value.
    if type(value) is not int or not 0 <= value <= 65535:
        raise ValueError('Nilai write harus bilangan bulat mentah 0..65535.')
    frame = bytearray(build_read(1, obj, address))
    struct.pack_into('<H', frame, 2, 20)
    frame[15] = 2
    struct.pack_into('<HHH', frame, 18, 4, address, value)
    return bytes(frame)


def build_change_parameter_extended(entries, flag=1, target_extra=0, service=137):
    """Builds SV_CHANGE_EXTENDED (137) or SV_CHANGE (106) on OBJID_PARAMETER (41).

    Reconstructed from SecomCE_D_BackGround_2d.dll Api_ChangeParameterExtended (RVA 0x295B2).
    Wire layout (516-byte fixed frame):
      Offset 0..1:   Magic 2 (uint16 LE)
      Offset 2..3:   Declared length 140 (16 + 124)
      Offset 4..6:   Routing bytes (10, 12, 0)
      Offset 9..10:  1 (uint16 LE)
      Offset 14:     Message type 1 (Request)
      Offset 15:     Service code (137 = SV_CHANGE_EXTENDED, 106 = SV_CHANGE)
      Offset 16..17: Object ID 41 (OBJID_PARAMETER, uint16 LE)
      Offset 18..19: Payload length 124 (uint16 LE)
      Offset 20:     Flag (uint8: 1 = trigger PLC intervention bit, 0 = no trigger)
      Offset 21:     Count of entries (uint8: 1..20)
      Offset 22 + 6*i: Param ID (uint16 LE)
      Offset 24 + 6*i: Value (float32 LE)
      Offset 142..143: Target extra (uint16 LE: 0 = active step + batch recipe)
    """
    if service not in (106, 137):
        raise ValueError('Service perubahan parameter harus 137 (SV_CHANGE_EXTENDED) atau 106 (SV_CHANGE).')
    if isinstance(entries, tuple) and len(entries) == 2 and isinstance(entries[0], int):
        entries = [entries]
    elif not isinstance(entries, (list, tuple)) or not entries:
        raise ValueError('Perubahan parameter membutuhkan setidaknya satu entri (param_id, value).')
    if len(entries) > 20:
        raise ValueError('Maksimal 20 parameter per frame perubahan.')
    if type(flag) is not int or not 0 <= flag <= 255:
        raise ValueError('Flag harus bilangan bulat uint8 (0..255).')
    if type(target_extra) is not int or not 0 <= target_extra <= 65535:
        raise ValueError('Target extra harus bilangan bulat uint16 (0..65535).')

    frame = bytearray(FRAME_SIZE)
    struct.pack_into('<HH', frame, 0, 2, 16 + 124)
    frame[4:7] = bytes((10, 12, 0))
    struct.pack_into('<H', frame, 9, 1)
    frame[14] = 1
    frame[15] = service
    struct.pack_into('<HH', frame, 16, 41, 124)
    frame[20] = flag
    frame[21] = len(entries)

    for i, item in enumerate(entries):
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError('Setiap entri harus berupa pasangan (param_id, value).')
        pid, val = item
        if type(pid) is not int or not 1 <= pid <= 1000:
            raise ValueError(f'ID parameter {pid} di luar rentang valid (1..1000).')
        if not math.isfinite(val):
            raise ValueError(f'Nilai parameter {pid} harus finite float.')
        off = 22 + 6 * i
        struct.pack_into('<Hf', frame, off, pid, float(val))

    struct.pack_into('<H', frame, 142, target_extra)
    return bytes(frame)


def trace(direction, host, port, data):
    row = dict(time=datetime.now().astimezone().isoformat(), direction=direction,
               host=host, port=port, bytes=len(data), hex=data.hex(' '))
    with LOG_LOCK, LOG_PATH.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row) + '\n')


def transact(host, port, service, obj, address, count, stop, timeout=3):
    request = build_read(service, obj, address, count)
    response = _exchange(host, port, request, stop, timeout)
    return parse_response(response, service, obj, count)


def _exchange(host, port, request, stop, timeout=3):
    if stop.is_set():
        raise InterruptedError('Dihentikan.')
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(0.2)
        trace('TX', host, port, request)
        sock.sendall(request)
        received = bytearray()
        deadline = time.monotonic() + timeout
        try:
            while len(received) < FRAME_SIZE:
                if stop.is_set():
                    raise InterruptedError('Dihentikan.')
                if time.monotonic() >= deadline:
                    raise TimeoutError(f'Timeout balasan: {len(received)}/{FRAME_SIZE} byte. Lihat log paket.')
                try:
                    chunk = sock.recv(FRAME_SIZE - len(received))
                except socket.timeout:
                    continue
                if not chunk:
                    raise ProtocolError(f'Controller menutup koneksi setelah {len(received)} byte.')
                received.extend(chunk)
        finally:
            trace('RX', host, port, bytes(received))
    return bytes(received)


def write_once_verified(host, port, obj, address, value, expected_old, stop):
    """One explicit write only. No retry, rollback, or repeated/cyclic write."""
    request = build_write(obj, address, value)
    current = transact(host, port, 1, obj, address, 1, stop)[0]
    if current != expected_old:
        raise ProtocolError(f'Write dibatalkan: nilai berubah dari {expected_old} menjadi {current}. '
                            'Baca dan konfirmasi ulang.')
    if stop.is_set():
        raise InterruptedError('Write dibatalkan sebelum pengiriman.')
    result = dict(old=current, requested=value, readback=None, acknowledged=False,
                  ack_error=None, readback_error=None)
    try:
        response = _exchange(host, port, request, stop)
        validate_response(response, 2, obj)
        result['acknowledged'] = True
    except (OSError, RuntimeError) as exc:
        # A timeout/error does not establish whether the controller applied it.
        result['ack_error'] = str(exc)
    if stop.is_set():
        result['readback_error'] = 'Dihentikan setelah upaya write; hasil belum terkonfirmasi.'
        return result
    try:
        result['readback'] = transact(host, port, 1, obj, address, 1, stop)[0]
    except (OSError, RuntimeError) as exc:
        result['readback_error'] = str(exc)
    return result


def read_live(host, port, service, obj, address, count, stop):
    if not 0 <= address <= 65535 or not 1 <= count <= 240 or address + count > 65536:
        raise ValueError('Rentang alamat tidak valid; jumlah 1..240.')
    # Single reads are paced; no automatic retries or protocol fallback.
    if service == 1:
        values = []
        for offset in range(count):
            if offset and stop.wait(1):
                raise InterruptedError('Dihentikan.')
            values.extend(transact(host, port, 1, obj, address + offset, 1, stop))
        return values
    if service == 11:
        limit = min(240, 486 // (4 if obj == 1035 else 2))
        values = []
        for offset in range(0, count, limit):
            values.extend(transact(host, port, service, obj, address + offset,
                                   min(limit, count - offset), stop))
        return values
    return transact(host, port, service, obj, address, count, stop)
