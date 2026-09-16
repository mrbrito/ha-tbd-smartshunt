import math
import struct
import unittest
from loader import load

parse = load('parser').parse_state_of_charge

class ParserTests(unittest.TestCase):
    def test_three_captured_packets(self):
        captures = [
            ('64000000c8755141552bba40cf1d964200000000ffffffff9f2a0000ab40a43c000000000000000000000000',13.091255,5.817790,75.058220),
            ('6400000006ea3041ec2c674037c21f4200000000ffffffff70b50200731f593b000048c20000000000000000',11.057135,3.612117,39.939663),
            ('6400000035173041ab8f6740c3471f4200000000ffffffff15b5020073d66e3b000048c20000000000000000',11.005666,3.618144,39.820080),
        ]
        for hex_data,v,a,w in captures:
            raw = bytes.fromhex(hex_data)
            data = parse(raw)
            self.assertEqual(data.soc,100)
            for actual,expected in [(data.voltage,v),(data.current,a),(data.power,w)]:
                self.assertAlmostEqual(actual,expected,places=5)
            self.assertEqual(data.raw_tail,raw[16:])

    def test_unsupported_lengths(self):
        for length in (0,16,31,32,43,45,88):
            self.assertIsNone(parse(bytes(length)))

    def test_nonfinite_values(self):
        for index in (1,2,3):
            for value in (math.nan,math.inf,-math.inf):
                fields=[100,12.0,3.0,36.0];fields[index]=value
                self.assertIsNone(parse(struct.pack('<Ifff',*fields)+bytes(28)))

    def test_invalid_soc_voltage(self):
        self.assertIsNone(parse(struct.pack('<Ifff',101,12,1,12)+bytes(28)))
        self.assertIsNone(parse(struct.pack('<Ifff',50,-1,1,1)+bytes(28)))

    def test_signed_values_preserved_without_claiming_discharge_mapping(self):
        data=parse(struct.pack('<Ifff',50,12,-1,-12)+bytes(28))
        self.assertEqual(data.current,-1)
        self.assertEqual(data.power,-12)
