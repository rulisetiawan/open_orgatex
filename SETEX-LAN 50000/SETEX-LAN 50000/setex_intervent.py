"""Experimental function-level intervention, reconstructed from 13E HMI APIs.

Profiles Temperature Control 141 and Drain Percent 71; no parameter-41 guesses.
"""
import math
import struct
from dataclasses import dataclass
from setex_controller import (build_read, validate_response, _exchange,
                              ProtocolError, build_change_parameter_extended)

FUNCTION_ID = 141
INTERVENT_SERVICE = 106
PARAMETERS = {
    'P1 - Suhu (°C)': (0, 0.0, 150.0),
    'P2 - Gradien (°C/min)': (1, 0.0, 9.9),
    'P3 - Waktu (min)': (2, 0.0, 180.0),
}
FUNCTIONS = {'713 - Fill Level (liter)': 713,
             '141 - Temperature Control': 141, '71 - Drain Percent': 71}
PROFILE_PARAMETERS = {
    141: PARAMETERS,
    71: {'P1 - Level akhir (%)': (0, 0.0, 100.0),
         'P3 - Waktu (min)': (2, 0.0, 180.0)},
    # Machine bounds supplied explicitly per operation; infinity is NOT a
    # permitted write bound (see parameter_spec).
    713: {'P2 - Volume isi (L)': (1, 0.0, math.inf)},
}
PROFILE_IDS = {141: (3, 4, 5), 71: (6, 16, 18), 713: (7, 9)}
PARAMETER_LABELS = {3: ('Suhu target', '°C'), 4: ('Gradien suhu', '°C/min'),
                    5: ('Waktu', 'min'), 6: ('Level akhir', '%'),
                    16: ('Pilihan drain', 'kode'), 18: ('Waktu drain', 'min'),
                    7: ('Jenis air', 'kode'), 9: ('Volume isi', 'L')}


@dataclass(frozen=True)
class FunctionSnapshot:
    line: int
    function_id: int
    values: tuple
    parameter_ids: tuple = ()


def parameter_rows(snapshot):
    rows = []
    expected = PROFILE_IDS[snapshot.function_id]
    for index, value in enumerate(snapshot.values):
        pid = snapshot.parameter_ids[index] if snapshot.parameter_ids else 0
        name, unit = PARAMETER_LABELS.get(pid, ('ID belum dipetakan', ''))
        editable = next((label for label, spec in PROFILE_PARAMETERS[snapshot.function_id].items()
                         if spec[0] == index and index < len(expected) and pid == expected[index]), None)
        if not pid:
            name, unit = 'Tidak dipakai / tidak dilaporkan', ''
        rows.append((f'P{index+1}', pid, name, value, unit, editable))
    return rows


def function_frame(service, line=0, values=None, function_id=FUNCTION_ID):
    if function_id not in PROFILE_PARAMETERS:
        raise ValueError('Fungsi belum didukung profil 13E.')
    if service not in (1, 106) or type(line) is not int or not 0 <= line <= 13:
        raise ValueError('Service fungsi atau baris fungsi tidak valid.')
    if service == 106 and (values is None or len(values) != 6 or
                           any(not math.isfinite(v) for v in values)):
        raise ValueError('Perubahan fungsi membutuhkan enam nilai finite dari pembacaan sebelumnya.')
    frame = bytearray(build_read(1, 1025, 1))
    frame[20:] = bytes(len(frame) - 20)
    frame[15] = service
    struct.pack_into('<HH', frame, 16, 6, 64)
    struct.pack_into('<H', frame, 2, 80)
    frame[20] = line
    struct.pack_into('<H', frame, 21, function_id)
    if service == 106:
        for i, value in enumerate(values):
            struct.pack_into('<f', frame, 25 + 8 * i, value)
    # Matches Api_Rem_ReadFunction / Api_ChangeFunction builder; fields not
    # provided by those HMI calls remain zero (not copied from opaque response).
    return bytes(frame)


def decode_function(frame, function_id=FUNCTION_ID):
    size = validate_response(frame, 1, 6)
    if size != 64:
        raise ProtocolError(f'Layout fungsi tidak cocok: payload {size}, diharapkan 64. Lihat log.')
    line = frame[20]
    fid = struct.unpack_from('<H', frame, 21)[0]
    values = tuple(struct.unpack_from('<f', frame, 25 + 8*i)[0] for i in range(6))
    parameter_ids = tuple(struct.unpack_from('<H', frame, 29 + 8*i)[0] for i in range(6))
    if fid != function_id or fid not in PROFILE_PARAMETERS or not 0 <= line <= 13 or any(not math.isfinite(v) for v in values):
        raise ProtocolError('Respons bukan fungsi yang diminta / konteks atau nilai tidak valid.')
    for index, minimum, maximum in PROFILE_PARAMETERS[fid].values():
        if not minimum <= values[index] <= maximum + 0.00001:
            raise ProtocolError('Nilai fungsi di luar batas konfigurasi 13E; perubahan diblokir.')
    return FunctionSnapshot(line, fid, values, parameter_ids)


def read_temperature(host, port, stop, function_id=FUNCTION_ID):
    return decode_function(_exchange(host, port, function_frame(1, function_id=function_id), stop), function_id)


def parameter_spec(snapshot, parameter, fill_limits=None):
    if snapshot.function_id not in PROFILE_PARAMETERS or len(snapshot.values) != 6:
        raise ValueError('Snapshot fungsi tidak valid.')
    parameters = PROFILE_PARAMETERS[snapshot.function_id]
    if parameter not in parameters:
        raise ValueError('Parameter tidak dikenali.')
    index, minimum, maximum = parameters[parameter]
    if snapshot.function_id == 713:
        if fill_limits is None or len(fill_limits) != 2:
            raise ValueError('Isi batas minimum dan maksimum Fill sesuai HMI terlebih dahulu.')
        minimum, maximum = fill_limits
        if not all(math.isfinite(v) for v in fill_limits) or not 0 <= minimum < maximum:
            raise ValueError('Batas Fill harus finite dan memenuhi 0 ≤ minimum < maksimum.')
    if snapshot.parameter_ids and snapshot.parameter_ids[index] != PROFILE_IDS[snapshot.function_id][index]:
        raise ValueError('ID parameter balasan berbeda dari profil 13E pada slot ini. Perubahan diblokir.')
    return index, minimum, maximum


def changed_values(snapshot, parameter, new_value, fill_limits=None):
    index, minimum, maximum = parameter_spec(snapshot, parameter, fill_limits)
    if not math.isfinite(new_value) or not minimum <= new_value <= maximum:
        raise ValueError(f'Nilai harus {minimum:g}..{maximum:g} dalam satuan tampilan.')
    values = list(snapshot.values)
    values[index] = new_value
    return tuple(values)


def manual_frame(service):
    """Api_SetManual / Api_ResetManual: empty payload, program object 3."""
    if service not in (109, 110):
        raise ValueError('Perintah Manual tidak valid.')
    frame = bytearray(build_read(1, 1025, 1))
    frame[20:] = bytes(len(frame) - 20)
    frame[15] = service
    struct.pack_into('<HH', frame, 16, 3, 0)
    struct.pack_into('<H', frame, 2, 16)
    return bytes(frame)


def change_temperature_once(host, port, snapshot, parameter, value, stop,
                            fill_limits=None, slot=None, progress=None):
    """Single confirmed transaction: enter Manual, change function, exit Manual.

    Slot must be supplied explicitly: read query line 0 does not identify it.
    No retry/fallback; cleanup is attempted only after acknowledged entry.
    """
    if type(slot) is not int or not 1 <= slot <= 13:
        raise ValueError('Isi slot fungsi aktif 1..13 (bukan nomor step). Jangan gunakan baris query 0.')
    values = changed_values(snapshot, parameter, value, fill_limits)
    index = parameter_spec(snapshot, parameter, fill_limits)[0]
    if not snapshot.parameter_ids or snapshot.parameter_ids[index] != PROFILE_IDS[snapshot.function_id][index]:
        raise ValueError('ID parameter belum terverifikasi dari balasan Controller.')
    current = read_temperature(host, port, stop, snapshot.function_id)
    if current != snapshot:
        raise ProtocolError('Parameter/konteks berubah sejak konfirmasi. Baca dan konfirmasi ulang.')
    result = dict(acknowledged=False, ack_error=None, readback=None,
                  readback_error=None, manual_entered=False, manual_exited=False,
                  manual_uncertain=False, stages=[], service=106, object=6, slot=slot)
    def send(service, obj, request, label, token):
        if progress:
            progress(label)
        stage = dict(stage=label, service=service, object=obj, ok=False)
        result['stages'].append(stage)
        try:
            validate_response(_exchange(host, port, request, token), service, obj)
            stage['ok'] = True
        except (OSError, RuntimeError) as exc:
            stage['error'] = str(exc)
            raise
    try:
        # Unknown outcome on timeout: never continue with the change.
        result['manual_uncertain'] = True
        send(109, 3, manual_frame(109), 'Masuk Intervent 109/3', stop)
        result['manual_entered'] = True
        current = read_temperature(host, port, stop, snapshot.function_id)
        if current != snapshot:
            raise ProtocolError('Parameter berubah saat masuk Intervent; perubahan dibatalkan.')
        send(106, 6, function_frame(106, slot, values, snapshot.function_id),
             'Simpan fungsi 106/6', stop)
        result['acknowledged'] = True
    except (OSError, RuntimeError) as exc:
        result['ack_error'] = str(exc)
    finally:
        if result['manual_entered']:
            # Finish our acknowledged Manual session even if Stop was pressed.
            import threading
            try:
                send(110, 3, manual_frame(110), 'Selesai Intervent 110/3', threading.Event())
                result['manual_exited'] = True
                result['manual_uncertain'] = False
            except (OSError, RuntimeError) as exc:
                result['ack_error'] = (result['ack_error'] or '') + ' Keluar Manual: ' + str(exc)
    try:
        result['readback'] = read_temperature(host, port, stop, snapshot.function_id)
    except (OSError, RuntimeError) as exc:
        result['readback_error'] = str(exc)
    return result


def change_function_legacy_once(host, port, snapshot, parameter, value, stop):
    """Legacy SV_CHANGE 106 / obj 6 path (rejected by controller during RUN with Error 62)."""
    values = changed_values(snapshot, parameter, value)
    request = function_frame(106, snapshot.line, values, snapshot.function_id)
    current = read_temperature(host, port, stop, snapshot.function_id)
    if current != snapshot:
        raise ProtocolError('Parameter/konteks fungsi berubah sejak konfirmasi. Baca dan konfirmasi ulang.')
    if stop.is_set():
        raise InterruptedError('Perubahan dibatalkan sebelum pengiriman.')
    result = dict(acknowledged=False, ack_error=None, readback=None, readback_error=None)
    try:
        response = _exchange(host, port, request, stop)
        validate_response(response, 106, 6)
        result['acknowledged'] = True
    except (OSError, RuntimeError) as exc:
        result['ack_error'] = str(exc)
    if stop.is_set():
        result['readback_error'] = 'Dihentikan; perintah yang sudah dikirim tidak dapat ditarik kembali.'
        return result
    try:
        result['readback'] = read_temperature(host, port, stop, snapshot.function_id)
    except (OSError, RuntimeError) as exc:
        result['readback_error'] = str(exc)
    return result
