import struct
import threading
import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import queue
from setex_alarms import request_frame, decode_status, decode_alarms, read_status_alarms, read_alarm_detail
from setex_controller import ProtocolError


def response(service, obj, length):
    frame = bytearray(request_frame(service, obj))
    frame[14] = 2
    struct.pack_into('<H', frame, 2, length + 16)
    struct.pack_into('<H', frame, 18, length)
    return frame


def status_response(count):
    frame = response(112, 0, 471)
    struct.pack_into('<HHBBB', frame, 399, 9 if count else 0, count, 1, 32, 64)
    return bytes(frame)


class AlarmTests(unittest.TestCase):
    def test_ui_once_and_cyclic_use_same_reader_without_gui(self):
        from setex_reader import App
        for cyclic, expected_calls in [(False, 1), (True, 2)]:
            with self.subTest(cyclic=cyclic):
                app = App.__new__(App)
                app.busy = False
                app.target = lambda: ('test', 50000)
                for name, value in [('mode', 'LIVE Controller (eksperimental)'),
                                    ('schedule', 'Cyclic' if cyclic else 'Sekali'),
                                    ('interval', '2'), ('alarm_detail', '65 - Bitmask')]:
                    setattr(app, name, SimpleNamespace(get=lambda v=value: v))
                app.stop_event = MagicMock()
                app.stop_event.is_set.return_value = False
                app.stop_event.wait.side_effect = [False, True]
                app.alarm_detail_button = MagicMock()
                app.detail_requested = threading.Event()
                if cyclic:
                    app.stop_event.is_set.side_effect = [False, False, False, False, True]
                app.rows = []
                app.table = MagicMock()
                app.status = MagicMock()
                app.set_busy = MagicMock()
                app.events = queue.Queue()
                def thread(target, **kwargs):
                    return SimpleNamespace(start=target)
                with patch('setex_reader.time.monotonic', side_effect=[0, 3, 3, 6]), patch('setex_reader.threading.Thread', side_effect=thread), patch('setex_reader.read_status_alarms', return_value={}) as read:
                    app.run_alarms()
                    self.assertEqual(read.call_count, expected_calls)
                events = []
                while not app.events.empty():
                    events.append(app.events.get()[0])
                self.assertEqual(events, ['alarms'] * expected_calls + ['done'])

    def test_empty_payload_requests(self):
        for service, obj in [(112, 0), (1, 65), (1, 67)]:
            frame = request_frame(service, obj)
            self.assertEqual(len(frame), 516)
            self.assertEqual(struct.unpack_from('<HH', frame), (2, 16))
            self.assertEqual(frame[15], service)
            self.assertEqual(struct.unpack_from('<HH', frame, 16), (obj, 0))
            self.assertEqual(frame[20:], bytes(496))

    def test_status_offsets(self):
        self.assertEqual(decode_status(status_response(2)),
                         dict(priority=9, count=2, communication=1, stop=32, halt=64))

    def test_bitmask_boundaries_and_id_521(self):
        frame = response(1, 65, 286)
        ids = [1, 8, 9, 521, 2000]
        struct.pack_into('<H', frame, 54, len(ids))
        for n in ids:
            frame[56+(n-1)//8] |= 1 << ((n-1) % 8)
        result = decode_alarms(bytes(frame))
        self.assertEqual(result['ids'], ids)
        self.assertTrue(result['count_matches'])

    def test_list_capacity_not_confused_with_id_range(self):
        frame = response(1, 67, 476)
        struct.pack_into('<H', frame, 54, 101)
        struct.pack_into('<100H', frame, 56, *range(1, 101))
        result = decode_alarms(bytes(frame), 67)
        self.assertTrue(result['truncated'])
        self.assertFalse(result['count_matches'])

    def test_count_mismatch_is_reported(self):
        frame = response(1, 65, 286)
        struct.pack_into('<H', frame, 54, 2)
        frame[56] = 1
        self.assertFalse(decode_alarms(bytes(frame))['count_matches'])

    def test_zero_alarms_skips_detail(self):
        with patch('setex_alarms._exchange', return_value=status_response(0)) as exchange:
            result = read_status_alarms('test', 50000, threading.Event())
            exchange.assert_called_once()
            self.assertIsNone(result['detail'])
            self.assertIsNone(result['detail_error'])

    def test_summary_with_active_alarms_never_requests_detail(self):
        with patch('setex_alarms._exchange', return_value=status_response(2)) as exchange:
            result = read_status_alarms('test', 50000, threading.Event())
            exchange.assert_called_once()
            self.assertEqual(exchange.call_args.args[2][15], 112)
            self.assertEqual(result['status']['count'], 2)
            self.assertIsNone(result['detail'])

    def test_explicit_detail_sends_only_detail_not_summary(self):
        frame = response(1, 65, 286)
        struct.pack_into('<H', frame, 54, 1)
        frame[57] = 1
        with patch('setex_alarms._exchange', return_value=bytes(frame)) as exchange:
            result = read_alarm_detail('test', 50000, threading.Event())
            exchange.assert_called_once()
            self.assertEqual(exchange.call_args.args[2][15], 1)
            self.assertEqual(struct.unpack_from('<H', exchange.call_args.args[2], 16)[0], 65)
            self.assertEqual(result['ids'], [9])

    def test_malformed_frames_are_not_shown_as_no_alarm(self):
        for frame in [bytes(516), status_response(2)[:-1], bytes(response(112, 0, 470))]:
            with self.subTest(length=len(frame)), self.assertRaises(ProtocolError):
                decode_status(frame)
        frame = response(1, 67, 476)
        struct.pack_into('<H', frame, 56, 2001)
        with self.assertRaises(ProtocolError):
            decode_alarms(bytes(frame), 67)

