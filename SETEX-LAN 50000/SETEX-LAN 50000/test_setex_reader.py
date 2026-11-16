import unittest
from unittest.mock import patch
from setex_reader import read_values, validate_request, parse_addresses


class ReaderTests(unittest.TestCase):
    def test_address_list(self):
        self.assertEqual(parse_addresses('10, 20,30,40', 'Lebih dari 1', '5'), [10, 20, 30, 40])
        self.assertEqual(parse_addresses('40,10', 'Satuan', '5'), [40, 10])
        self.assertEqual(parse_addresses('10', 'Lebih dari 1', '4'), [10, 11, 12, 13])
        self.assertEqual(parse_addresses('10', 'Satuan', '5'), [10])
        for text in ['10,', '1,1', '-1,20', '65536', ',']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_addresses(text, 'Satuan', '5')

    def test_iw_rejects_unsupported_list(self):
        with self.assertRaises(ValueError):
            validate_request(128, 1025, 1, 5)

    def test_write_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_request(2, 1025, 1, 1)

    def test_address_bounds(self):
        for start, count in [(-1, 1), (0, 0), (0, 241), (65535, 2)]:
            with self.subTest(start=start, count=count), self.assertRaises(ValueError):
                validate_request(1, 1025, start, count)

    def test_simulation_single_and_multiple(self):
        self.assertEqual(len(read_values('SIMULASI', 1, 1025, 71, 1, 0)), 1)
        self.assertEqual(len(read_values('SIMULASI', 11, 1025, 71, 5, 0)), 5)
        self.assertTrue(all(x in (0, 1) for x in read_values('SIMULASI', 1, 1026, 0, 10, 0)))

    def test_live_cannot_send_guessed_packets(self):
        with patch('socket.create_connection') as connect:
            with self.assertRaises(RuntimeError):
                read_values('LIVE (belum tersedia)', 1, 1025, 71, 1, 0)
            connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
