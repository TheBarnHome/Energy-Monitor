from __future__ import annotations

import unittest

from custom_components.energy_monitor.parsing import coerce_float


class ParsingTest(unittest.TestCase):
    def test_coerce_float_accepts_plain_numbers(self) -> None:
        self.assertEqual(coerce_float("53.2"), 53.2)
        self.assertEqual(coerce_float(53), 53.0)

    def test_coerce_float_accepts_percent_and_comma(self) -> None:
        self.assertEqual(coerce_float("53,2 %"), 53.2)

    def test_coerce_float_rejects_unavailable_states(self) -> None:
        self.assertIsNone(coerce_float("unavailable"))
        self.assertIsNone(coerce_float("unknown"))


if __name__ == "__main__":
    unittest.main()
