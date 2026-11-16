import unittest
import threading
import struct
from unittest.mock import patch
from setex_controller import read_live, build_read
from setex_reader import parse_addresses


class Block240Tests(unittest.TestCase):
    def test_ui_allows_240_and_rejects_241(self):
        self.assertEqual(parse_addresses('1', 'Lebih dari 1', '240'), list(range(1, 241)))
        with self.assertRaises(ValueError):
            parse_addresses('1', 'Lebih dari 1', '241')

    def test_240_words_in_single_frame(self):
        request = build_read(11, 1009, 1, 240)
        self.assertEqual(struct.unpack_from('<HH', request, 20), (1, 240))
        with patch('setex_controller.transact', return_value=list(range(240))) as tx:
            self.assertEqual(len(read_live('test', 50000, 11, 1009, 1, 240, threading.Event())), 240)
            tx.assert_called_once()

    def test_240_dwords_are_split_and_ordered(self):
        def tx(host, port, service, obj, address, count, stop):
            return list(range(address, address + count))
        with patch('setex_controller.transact', side_effect=tx) as exchange:
            values = read_live('test', 50000, 11, 1035, 10, 240, threading.Event())
            self.assertEqual(values, list(range(10, 250)))
            self.assertEqual([(c.args[4], c.args[5]) for c in exchange.call_args_list], [(10, 121), (131, 119)])

    def test_out_of_range_rejected_before_request(self):
        with patch('setex_controller.transact') as tx:
            with self.assertRaises(ValueError):
                read_live('test', 50000, 11, 1035, 65500, 240, threading.Event())
            tx.assert_not_called()
