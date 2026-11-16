import struct
import threading
import unittest
from unittest.mock import patch
from setex_controller import build_read, parse_response, transact, ProtocolError


class ControllerTests(unittest.TestCase):
    def response(self):
        data = bytearray(516)
        struct.pack_into('<HH', data, 0, 2, 18)
        data[14:16] = bytes((2, 1))
        struct.pack_into('<HHH', data, 16, 1025, 2, 2299)
        return bytes(data)

    def test_read_layout_from_dll(self):
        data = build_read(1, 1025, 1)
        self.assertEqual(len(data), 516)
        self.assertEqual(data[:4], bytes.fromhex('02 00 12 00'))
        self.assertEqual(data[14:22], bytes.fromhex('01 01 01 04 02 00 01 00'))

    def test_block_payload(self):
        self.assertEqual(build_read(11, 1025, 71, 5)[18:24], bytes.fromhex('04 00 47 00 05 00'))

    def test_decode_and_reject_mismatches(self):
        self.assertEqual(parse_response(self.response(), 1, 1025, 1), [2299])
        for offset, value in [(0, 0), (2, 0), (14, 3), (15, 2), (16, 0), (18, 4)]:
            bad = bytearray(self.response())
            bad[offset] = value
            with self.subTest(offset=offset), self.assertRaises(ProtocolError):
                parse_response(bytes(bad), 1, 1025, 1)

    def test_fragmented_response(self):
        class Socket:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def settimeout(self, value): pass
            def sendall(self, data): self.sent = data
            def recv(self, count): return self.parts.pop(0)
        sock = Socket()
        packet = self.response()
        sock.parts = [packet[:3], packet[3:20], packet[20:]]
        with patch('setex_controller.socket.create_connection', return_value=sock), patch('setex_controller.trace'):
            self.assertEqual(transact('127.0.0.1', 50000, 1, 1025, 1, 1, threading.Event()), [2299])

    def test_write_and_bits_rejected(self):
        for service, obj in [(2, 1025), (128, 1056), (1, 1026)]:
            with self.assertRaises(ValueError):
                build_read(service, obj, 1)

    def test_each_word_object_has_own_request_and_response(self):
        # Literal IDs from 6A Commands.csv; same address must use different IDs.
        for obj, wire in [(1009, b'\xf1\x03'), (1010, b'\xf2\x03'),
                          (1001, b'\xe9\x03'), (1058, b'\x22\x04'),
                          (1025, b'\x01\x04')]:
            for service, count in [(1, 1), (11, 3)]:
                with self.subTest(obj=obj, service=service):
                    request = build_read(service, obj, 1, count)
                    self.assertEqual(request[16:18], wire)
                    reply = bytearray(516)
                    struct.pack_into('<HH', reply, 0, 2, 16 + 2 * count)
                    reply[14:16] = bytes((2, service))
                    struct.pack_into('<HH', reply, 16, obj, 2 * count)
                    values = list(range(100, 100 + count))
                    struct.pack_into('<' + 'H' * count, reply, 20, *values)
                    self.assertEqual(parse_response(bytes(reply), service, obj, count), values)
                    with self.assertRaises(ProtocolError):
                        parse_response(bytes(reply), service, 1010 if obj != 1010 else 1009, count)


if __name__ == '__main__':
    unittest.main()
