import struct
import threading
import unittest
from unittest.mock import patch
from setex_controller import build_read, build_write, parse_response, read_live, ProtocolError
from setex_reader import OBJECTS, parse_addresses, read_values


class ConsumptionTests(unittest.TestCase):
    def response(self, service, values):
        frame = bytearray(516)
        struct.pack_into('<HH', frame, 0, 2, 16+len(values)*4)
        frame[14:16] = bytes((2, service))
        struct.pack_into('<HH', frame, 16, 1035, len(values)*4)
        struct.pack_into('<'+'I'*len(values), frame, 20, *values)
        return bytes(frame)

    def test_unsigned_dword_endian_boundaries(self):
        values = [0, 65536, 0x12345678, 0x80000000, 0xFFFFFFFF]
        frame = self.response(11, values)
        self.assertEqual(frame[28:32], bytes.fromhex('78 56 34 12'))
        self.assertEqual(parse_response(frame, 11, 1035, 5), values)

    def test_read_payload_uses_counter_index_and_count_not_byte_length(self):
        one = build_read(1, 1035, 10)
        block = build_read(11, 1035, 10, 80)
        self.assertEqual(struct.unpack_from('<HHH', one, 16), (1035, 2, 10))
        self.assertEqual(struct.unpack_from('<HHHH', block, 16), (1035, 4, 10, 80))
        with self.assertRaises(ValueError):
            build_read(11, 1035, 10, 122)

    def test_word_sized_response_rejected(self):
        frame = bytearray(self.response(1, [65536]))
        struct.pack_into('<H', frame, 2, 18)
        struct.pack_into('<H', frame, 18, 2)
        with self.assertRaises(ProtocolError):
            parse_response(bytes(frame), 1, 1035, 1)

    def test_block_80_counters_decoded_in_one_transaction(self):
        values = [100000+n for n in range(80)]
        with patch('setex_controller._exchange', return_value=self.response(11, values)) as exchange:
            self.assertEqual(read_live('test', 50000, 11, 1035, 1, 80, threading.Event()), values)
            exchange.assert_called_once()

    def test_single_dword(self):
        with patch('setex_controller._exchange', return_value=self.response(1, [4294967295])):
            self.assertEqual(read_live('test', 50000, 1, 1035, 1, 1, threading.Event()), [4294967295])

    def test_counters_are_read_only(self):
        with self.assertRaisesRegex(ValueError, 'hanya baca'):
            build_write(1035, 1, 0)

    def test_ui_choice_address_list_and_simulation_support_dword(self):
        self.assertEqual(OBJECTS['Konsumsi batch - DWORD (1035)'], 1035)
        self.assertEqual(parse_addresses('1,3,5', 'Satuan', '1'), [1, 3, 5])
        self.assertEqual(read_values('SIMULASI', 1, 1035, 4000, 1, 0), [68000])

