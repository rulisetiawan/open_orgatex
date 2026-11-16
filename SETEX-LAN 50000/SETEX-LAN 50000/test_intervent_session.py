import struct
import threading
import unittest
from unittest.mock import patch
from setex_intervent import FunctionSnapshot, change_temperature_once


class SessionTests(unittest.TestCase):
    before = FunctionSnapshot(0, 141, (45., 1., 2., 0., 0., 0.), (3, 4, 5, 0, 0, 0))
    after = FunctionSnapshot(0, 141, (44., 1., 2., 0., 0., 0.), (3, 4, 5, 0, 0, 0))

    def run_session(self, failure=None, cancel=False):
        requests = []
        stop = threading.Event()
        def exchange(host, port, request, token):
            requests.append(request)
            if request[15] == failure:
                raise TimeoutError('test timeout')
            if token.is_set():
                raise InterruptedError('Stop')
            if cancel and request[15] == 109:
                stop.set()
            response = bytearray(request)
            response[14] = 2
            struct.pack_into('<H', response, 2, 16)
            struct.pack_into('<H', response, 18, 0)
            return bytes(response)
        with patch('setex_intervent.read_temperature', side_effect=[self.before, self.before, self.after]), patch('setex_intervent._exchange', side_effect=exchange):
            result = change_temperature_once('test', 50000, self.before, 'P1 - Suhu (°C)', 44., stop, slot=1)
        return requests, result

    def test_order_preserves_parameters_and_readback(self):
        requests, result = self.run_session()
        self.assertEqual([(r[15], struct.unpack_from('<H', r, 16)[0]) for r in requests], [(109, 3), (106, 6), (110, 3)])
        self.assertEqual(requests[1][20], 1)
        self.assertEqual(tuple(struct.unpack_from('<f', requests[1], 25+8*i)[0] for i in range(6)), self.after.values)
        self.assertTrue(result['acknowledged'])
        self.assertTrue(result['manual_exited'])
        self.assertEqual(result['readback'], self.after)

    def test_unknown_entry_does_not_write_or_reset(self):
        requests, result = self.run_session(109)
        self.assertEqual([r[15] for r in requests], [109])
        self.assertTrue(result['manual_uncertain'])
        self.assertFalse(result['acknowledged'])

    def test_change_timeout_still_finishes_owned_session_without_retry(self):
        requests, result = self.run_session(106)
        self.assertEqual([r[15] for r in requests], [109, 106, 110])
        self.assertFalse(result['acknowledged'])
        self.assertTrue(result['manual_exited'])

    def test_reset_failure_reports_uncertain_state(self):
        requests, result = self.run_session(110)
        self.assertEqual(len(requests), 3)
        self.assertTrue(result['manual_uncertain'])
        self.assertFalse(result['manual_exited'])

    def test_stop_does_not_prevent_cleanup_of_acknowledged_session(self):
        requests, result = self.run_session(cancel=True)
        self.assertEqual([r[15] for r in requests], [109, 106, 110])
        self.assertFalse(result['acknowledged'])
        self.assertTrue(result['manual_exited'])

    def test_slot_is_required_before_network(self):
        for slot in (None, 0, 14, True):
            with patch('setex_intervent.read_temperature') as read, self.assertRaises(ValueError):
                change_temperature_once('test', 50000, self.before, 'P1 - Suhu (°C)', 44., threading.Event(), slot=slot)
            read.assert_not_called()

    def test_changed_values_after_entry_cancel_write_but_exit(self):
        with patch('setex_intervent.read_temperature', side_effect=[self.before, self.after, self.after]), patch('setex_intervent._exchange') as exchange:
            def ack(host, port, request, token):
                response = bytearray(request)
                response[14] = 2
                return bytes(response)
            exchange.side_effect = ack
            result = change_temperature_once('test', 50000, self.before, 'P1 - Suhu (°C)', 44., threading.Event(), slot=1)
            self.assertEqual([c.args[2][15] for c in exchange.call_args_list], [109, 110])
            self.assertFalse(result['acknowledged'])

