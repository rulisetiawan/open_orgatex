"""Read-only Controller status/alarm layouts from the supplied 13E analysis.

Runtime compatibility must be checked against captured Controller responses.
"""
import struct
from setex_controller import build_read, validate_response, ProtocolError, _exchange


def request_frame(service, obj):
    if (service, obj) not in ((112, 0), (1, 65), (1, 67)):
        raise ValueError('Permintaan status/alarm tidak didukung.')
    frame = bytearray(build_read(1, 1025, 1))
    frame[20:] = bytes(len(frame) - 20)
    frame[15] = service
    struct.pack_into('<HHH', frame, 16, obj, 0, 0)
    struct.pack_into('<H', frame, 2, 16)
    return bytes(frame)


def decode_status(frame):
    if validate_response(frame, 112, 0) != 471:
        raise ProtocolError('Layout status bukan payload 471 byte; lihat log paket.')
    priority, count = struct.unpack_from('<HH', frame, 399)
    if priority > 2000 or count > 2000:
        raise ProtocolError('Jumlah/ID alarm di luar layout 13E yang dipetakan.')
    return dict(priority=priority, count=count, communication=frame[403],
                stop=frame[404], halt=frame[405])


def decode_alarms(frame, obj=65):
    expected = {65: 286, 67: 476}
    if obj not in expected:
        raise ValueError('Objek detail alarm tidak didukung.')
    if validate_response(frame, 1, obj) != expected[obj]:
        raise ProtocolError('Layout detail alarm tidak cocok; lihat log paket.')
    count = struct.unpack_from('<H', frame, 54)[0]
    if count > 2000:
        raise ProtocolError('Jumlah alarm tidak valid.')
    if obj == 65:
        ids = [n+1 for n in range(2000) if frame[56+n//8] & (1 << (n % 8))]
    else:
        ids = [n for n in struct.unpack_from('<100H', frame, 56) if n]
        if any(n > 2000 for n in ids) or len(set(ids)) != len(ids):
            raise ProtocolError('Daftar ID alarm tidak valid.')
    return dict(ids=ids, count=count, truncated=(obj == 67 and count > 100),
                count_matches=(len(ids) == count))


def read_status_alarms(host, port, stop, detail_object=65):
    """Read summary only. Never request alarm detail automatically."""
    status = decode_status(_exchange(host, port, request_frame(112, 0), stop))
    return dict(status=status, detail=None, detail_error=None)


def read_alarm_detail(host, port, stop, detail_object=65):
    """One explicit detail request, independent of summary count."""
    return decode_alarms(_exchange(host, port, request_frame(1, detail_object), stop), detail_object)
