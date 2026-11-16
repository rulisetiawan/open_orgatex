import struct
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from setex_controller import build_write, write_once_verified, ProtocolError
from setex_reader import App


class WriteTests(unittest.TestCase):
    def ack(self, obj=1009, kind=2):
        frame = bytearray(516)
        struct.pack_into('<HH', frame, 0, 2, 16)
        frame[14:16] = bytes((kind, 2))
        struct.pack_into('<HH', frame, 16, obj, 0)
        return bytes(frame)

    def test_wire_matches_write_word_builder_in_dll(self):
        for obj in [1009, 1010, 1025, 1001, 1058]:
            packet = build_write(obj, 10, 1234)
            self.assertEqual(len(packet), 516)
            self.assertEqual(packet[:4], bytes.fromhex('02 00 14 00'))
            self.assertEqual(packet[14:16], b'\x01\x02')
            self.assertEqual(struct.unpack_from('<HHHH', packet, 16), (obj, 4, 10, 1234))

    def test_rejects_invalid_values_and_objects(self):
        for value in [-1, 65536, 1.5, True]:
            with self.assertRaises(ValueError):
                build_write(1009, 10, value)
        for obj in [1026, 1056, 0]:
            with self.assertRaises(ValueError):
                build_write(obj, 10, 1)

    def run_write(self, stop=None):
        return write_once_verified('127.0.0.1', 50000, 1009, 10, 1234, 100, stop or threading.Event())

    def test_checks_old_writes_once_and_reads_back(self):
        calls = []
        def read(*args):
            calls.append('read')
            return [100] if len(calls) == 1 else [1234]
        def send(*args):
            calls.append('write')
            return self.ack()
        with patch('setex_controller.transact', side_effect=read), patch('setex_controller._exchange', side_effect=send) as exchange:
            result = self.run_write()
            self.assertEqual(calls, ['read', 'write', 'read'])
            self.assertTrue(result['acknowledged'])
            self.assertEqual(result['readback'], 1234)
            exchange.assert_called_once()

    def test_changed_old_value_prevents_write(self):
        with patch('setex_controller.transact', return_value=[101]), patch('setex_controller._exchange') as send:
            with self.assertRaises(ProtocolError):
                self.run_write()
            send.assert_not_called()

    def test_stop_before_send_prevents_write(self):
        stop = threading.Event()
        def read(*args):
            stop.set()
            return [100]
        with patch('setex_controller.transact', side_effect=read), patch('setex_controller._exchange') as send:
            with self.assertRaises(InterruptedError):
                self.run_write(stop)
            send.assert_not_called()

    def test_timeout_does_not_retry_and_still_reads_back(self):
        with patch('setex_controller.transact', side_effect=[[100], [1234]]), patch('setex_controller._exchange', side_effect=TimeoutError('timeout')) as send:
            result = self.run_write()
            send.assert_called_once()
            self.assertFalse(result['acknowledged'])
            self.assertEqual(result['readback'], 1234)
            self.assertEqual(result['ack_error'], 'timeout')

    def test_rejected_ack_is_not_success(self):
        with patch('setex_controller.transact', side_effect=[[100], [100]]), patch('setex_controller._exchange', return_value=self.ack(kind=3)):
            result = self.run_write()
            self.assertFalse(result['acknowledged'])
            self.assertEqual(result['readback'], 100)

    def test_readback_failure_is_reported(self):
        with patch('setex_controller.transact', side_effect=[[100], TimeoutError('readback timeout')]), patch('setex_controller._exchange', return_value=self.ack()):
            result = self.run_write()
            self.assertTrue(result['acknowledged'])
            self.assertIsNone(result['readback'])
            self.assertEqual(result['readback_error'], 'readback timeout')

    def test_cancel_confirmation_starts_no_writer(self):
        app = SimpleNamespace(stop_event=threading.Event(), status=Mock(), set_busy=Mock())
        with patch('setex_reader.messagebox.askyesno', return_value=False), patch('setex_reader.threading.Thread') as worker:
            App.confirm_write(app, ('127.0.0.1', 50000, 'SET', 1009, 10, 1234), 100)
            worker.assert_not_called()
            app.set_busy.assert_called_once_with(False)


if __name__ == '__main__':
    unittest.main()
