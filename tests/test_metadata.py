import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from metadata import parse_filename, apply_overrides_and_validate

class MetadataTests(unittest.TestCase):
    def test_hex_socket_screw(self):
        data = parse_filename(Path("DIN_912_M5_P0.8_HEX4_L20.step"))
        self.assertEqual(data["screw_type"], "Socket_Head_Cap_Screw")
        self.assertEqual(data["tool_size"], "HEX4")
        self.assertEqual(data["thread_size"], "M5")
        self.assertEqual(data["thread_pitch"], "P0.8")
        self.assertEqual(data["screw_length"], "L20")

    def test_hex_nut_no_length(self):
        data = parse_filename(Path("DIN_934_M8_P1.25_SW13_LNA.step"))
        self.assertEqual(data["screw_type"], "Hex_Nut")
        self.assertEqual(data["screw_length"], "NA")

    def test_underscored_tool_size(self):
        data = parse_filename(Path("DIN_961_M6_P0.75_SW_10_L30.step"))
        self.assertEqual(data["tool_size"], "SW10")

    def test_csv_override(self):
        p = Path("/tmp/input/DIN_912_M5_P0.8_HEX4_L20.step")
        parsed = parse_filename(p)
        result = apply_overrides_and_validate(
            p, Path("/tmp/input"), parsed,
            {"DIN_912_M5_P0.8_HEX4_L20.step": {"screw_type": "Special_Button_Torx"}}
        )
        self.assertEqual(result["screw_type"], "Special_Button_Torx")

if __name__ == "__main__":
    unittest.main()
