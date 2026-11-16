import math
import struct
import threading
import unittest
from unittest.mock import patch
from setex_controller import ProtocolError, build_change_parameter_extended, validate_response
from setex_intervent import (FunctionSnapshot, function_frame, decode_function,
                             changed_values, change_temperature_once, change_function_legacy_once,
                             PARAMETERS, parameter_rows)


class InterventTests(unittest.TestCase):


    def fill_snapshot(self, volume=3000.):
        return FunctionSnapshot(0, 713, (1., volume, 0., 0., 0., 0.), (7, 9, 0, 0, 0, 0))

    def test_fill_requires_explicit_valid_limits(self):
        for bounds in [None, (0., math.inf), (0., math.nan), (-1., 8000.), (8000., 0.), (0., 0.)]:
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                changed_values(self.fill_snapshot(), 'P2 - Volume isi (L)', 4000., bounds)
        self.assertEqual(changed_values(self.fill_snapshot(), 'P2 - Volume isi (L)', 4000., (100., 8000.)),
                         (1., 4000., 0., 0., 0., 0.))

    def test_fill_limit_rejection_opens_no_connection(self):
        with patch('setex_intervent.read_temperature') as read, patch('setex_intervent._exchange') as exchange:
            with self.assertRaises(ValueError):
                change_temperature_once('127.0.0.1', 50000, self.fill_snapshot(),
                                        'P2 - Volume isi (L)', 9000., threading.Event(), fill_limits=(100., 8000.), slot=1)
            read.assert_not_called()
            exchange.assert_not_called()


    def snapshot(self):
        return FunctionSnapshot(0, 141, (45., 1., 2., 0., 0., 0.), (3, 4, 5, 0, 0, 0))

    def reply(self, service=1, values=None):
        values = values or self.snapshot().values
        frame = bytearray(function_frame(106, 0, values))
        frame[14] = 2
        frame[15] = service
        for i, pid in enumerate((3, 4, 5, 0, 0, 0)):
            struct.pack_into('<H', frame, 29 + 8*i, pid)
        return bytes(frame)

    def test_api_read_function_layout(self):
        frame = function_frame(1)
        self.assertEqual(len(frame), 516)
        self.assertEqual(struct.unpack_from('<HH', frame), (2, 80))
        self.assertEqual(frame[14:23], bytes.fromhex('01 01 06 00 40 00 00 8d 00'))
        self.assertEqual(frame[23:], bytes(493))

    def test_function_roundtrip_and_preserved_other_values(self):
        snapshot = decode_function(self.reply())
        self.assertEqual(snapshot, self.snapshot())
        values = changed_values(snapshot, next(iter(PARAMETERS)), 50.)
        self.assertEqual(values, (50., 1., 2., 0., 0., 0.))
        frame = function_frame(106, 0, values)
        self.assertEqual(frame[15], 106)
        self.assertEqual(struct.unpack_from('<f', frame, 25)[0], 50.)
        self.assertEqual(struct.unpack_from('<f', frame, 33)[0], 1.)
        self.assertEqual(struct.unpack_from('<f', frame, 41)[0], 2.)

    def test_reject_wrong_function_size_and_nonfinite(self):
        for offset, value in [(16, 41), (18, 0), (21, 142), (20, 14)]:
            bad = bytearray(self.reply())
            bad[offset] = value
            with self.subTest(offset=offset), self.assertRaises(ProtocolError):
                decode_function(bytes(bad))
        bad = bytearray(self.reply())
        struct.pack_into('<f', bad, 25, math.nan)
        with self.assertRaises(ProtocolError):
            decode_function(bytes(bad))

    def test_config_bounds(self):
        for name, value in [('P1 - Suhu (°C)', 151), ('P2 - Gradien (°C/min)', -1),
                            ('P3 - Waktu (min)', 181), ('P1 - Suhu (°C)', math.nan)]:
            with self.assertRaises(ValueError):
                changed_values(self.snapshot(), name, value)

    def test_changed_snapshot_never_sends_change(self):
        other = FunctionSnapshot(0, 141, (46., 1., 2., 0., 0., 0.))
        with patch('setex_intervent.read_temperature', return_value=other), patch('setex_intervent._exchange') as exchange:
            with self.assertRaises(ProtocolError):
                change_temperature_once('127.0.0.1', 50000, self.snapshot(), next(iter(PARAMETERS)), 50., threading.Event(), slot=1)
            exchange.assert_not_called()

    def reply_param_ack(self, service=137):
        frame = bytearray(516)
        struct.pack_into('<HH', frame, 0, 2, 16)
        frame[14] = 2
        frame[15] = service
        struct.pack_into('<HH', frame, 16, 41, 0)
        return bytes(frame)

    def test_change_parameter_extended_wire_layout(self):
        # Matches SecomCE_D_BackGround_2d.dll Api_ChangeParameterExtended (RVA 0x295B2)
        frame = build_change_parameter_extended([(3, 45.5)], flag=1, target_extra=0, service=137)
        self.assertEqual(len(frame), 516)
        magic, declared = struct.unpack_from('<HH', frame, 0)
        self.assertEqual((magic, declared), (2, 140))  # 16 + 124
        self.assertEqual(frame[4:7], bytes((10, 12, 0)))
        self.assertEqual(struct.unpack_from('<H', frame, 9)[0], 1)
        self.assertEqual(frame[14], 1)     # Request
        self.assertEqual(frame[15], 137)   # SV_CHANGE_EXTENDED
        obj, plen = struct.unpack_from('<HH', frame, 16)
        self.assertEqual((obj, plen), (41, 124))
        self.assertEqual(frame[20], 1)     # flag = 1
        self.assertEqual(frame[21], 1)     # count = 1
        pid, val = struct.unpack_from('<Hf', frame, 22)
        self.assertEqual(pid, 3)
        self.assertAlmostEqual(val, 45.5, places=5)
        self.assertEqual(frame[28:142], bytes(114))
        self.assertEqual(struct.unpack_from('<H', frame, 142)[0], 0)
        self.assertEqual(frame[144:], bytes(516 - 144))

        # Test multiple parameters & service 106
        frame_multi = build_change_parameter_extended([(3, 41.0), (4, 1.5), (5, 2.0)], flag=0, target_extra=1, service=106)
        self.assertEqual(frame_multi[15], 106)
        self.assertEqual(frame_multi[20], 0)
        self.assertEqual(frame_multi[21], 3)
        self.assertEqual(struct.unpack_from('<Hf', frame_multi, 22), (3, 41.0))
        self.assertEqual(struct.unpack_from('<Hf', frame_multi, 28), (4, 1.5))
        self.assertEqual(struct.unpack_from('<Hf', frame_multi, 34), (5, 2.0))
        self.assertEqual(struct.unpack_from('<H', frame_multi, 142)[0], 1)

    def test_change_parameter_extended_validation(self):
        with self.assertRaises(ValueError):
            build_change_parameter_extended([(0, 10.0)])  # pid <= 0
        with self.assertRaises(ValueError):
            build_change_parameter_extended([(1001, 10.0)])  # pid > 1000
        with self.assertRaises(ValueError):
            build_change_parameter_extended([(i, float(i)) for i in range(1, 22)])  # > 20 entries
        with self.assertRaises(ValueError):
            build_change_parameter_extended([(3, math.nan)])
        with self.assertRaises(ValueError):
            build_change_parameter_extended([(3, 40.0)], service=1)


    def test_legacy_function_change_still_available(self):
        after = FunctionSnapshot(0, 141, (50., 1., 2., 0., 0., 0.), (3, 4, 5, 0, 0, 0))
        with patch('setex_intervent.read_temperature', side_effect=[self.snapshot(), after]), patch('setex_intervent._exchange', return_value=self.reply(106)) as exchange:
            result = change_function_legacy_once('127.0.0.1', 50000, self.snapshot(), next(iter(PARAMETERS)), 50., threading.Event())
            exchange.assert_called_once()
            self.assertEqual(exchange.call_args.args[2][15], 106)
            self.assertEqual(struct.unpack_from('<H', exchange.call_args.args[2], 16)[0], 6)
            self.assertTrue(result['acknowledged'])


    def test_drain_profile_and_preserve_drain_code(self):
        frame = bytearray(function_frame(106, 0, (0., 1., 2., 0., 0., 0.), 71))
        frame[14:16] = bytes((2, 1))
        for i, pid in enumerate((6, 16, 18)):
            struct.pack_into('<H', frame, 29 + 8*i, pid)
        snapshot = decode_function(bytes(frame), 71)
        self.assertEqual(snapshot.function_id, 71)
        values = changed_values(snapshot, 'P1 - Level akhir (%)', 5.)
        self.assertEqual(values, (5., 1., 2., 0., 0., 0.))
        with self.assertRaises(ValueError):
            changed_values(snapshot, 'P2 - Kode drain', 2.)
        with self.assertRaises(ProtocolError):
            decode_function(bytes(frame), 141)

    def test_error_62_is_decoded(self):
        frame = bytearray(function_frame(106, 0, self.snapshot().values))
        frame[14] = 3
        struct.pack_into('<H', frame, 2, 20)
        struct.pack_into('<HH', frame, 16, 6, 4)
        struct.pack_into('<HH', frame, 20, 19, 62)
        from setex_controller import validate_response
        with self.assertRaisesRegex(ProtocolError, 'error 62 — Invalid status'):
            validate_response(bytes(frame), 106, 6)

    def test_fill_liter_profile_reads_but_no_changes_without_limits(self):
        frame = bytearray(function_frame(1, function_id=713))
        frame[14] = 2
        struct.pack_into('<f', frame, 25, 1.)
        struct.pack_into('<f', frame, 33, 8000.)
        snapshot = decode_function(bytes(frame), 713)
        self.assertEqual(snapshot.values[:2], (1., 8000.))
        with self.assertRaises(ValueError):
            changed_values(snapshot, 'P2 - Volume (L)', 9000.)

    def test_six_rows_and_unused_slots(self):
        rows = parameter_rows(self.snapshot())
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0][:3], ('P1', 3, 'Suhu target'))
        self.assertEqual(rows[2][1], 5)
        self.assertIsNone(rows[3][-1])

    def test_changed_parameter_id_cannot_be_written(self):
        snapshot = FunctionSnapshot(0, 141, (45., 1., 2., 0., 0., 0.), (9, 4, 5, 0, 0, 0))
        self.assertEqual(parameter_rows(snapshot)[0][2], 'Volume isi')
        self.assertIsNone(parameter_rows(snapshot)[0][-1])
        with self.assertRaises(ValueError):
            changed_values(snapshot, 'P1 - Suhu (°C)', 50.)
        with self.assertRaises(ValueError):
            change_temperature_once('127.0.0.1', 50000, snapshot, 'P1 - Suhu (°C)', 50., threading.Event())

    def test_error_decoding_for_parameter_extended(self):
        for err_code, expected_text in [(116, 'Invalid parameter number'), (117, 'Invalid parameter count'), (125, 'Parameter too big')]:
            frame = bytearray(516)
            struct.pack_into('<HH', frame, 0, 2, 20)
            frame[14] = 3
            frame[15] = 137
            struct.pack_into('<HH', frame, 16, 41, 4)
            struct.pack_into('<HH', frame, 20, 19, err_code)
            with self.subTest(err_code=err_code), self.assertRaisesRegex(ProtocolError, expected_text):
                validate_response(bytes(frame), 137, 41)


if __name__ == '__main__':
    unittest.main()
