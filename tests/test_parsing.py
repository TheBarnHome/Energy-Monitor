from __future__ import annotations

import unittest

from custom_components.energy_monitor.parsing import (
    coerce_float,
    is_energy_unit,
    normalise_slot_energy,
)


class ParsingTest(unittest.TestCase):
    def test_coerce_float_accepts_plain_numbers(self) -> None:
        self.assertEqual(coerce_float("53.2"), 53.2)
        self.assertEqual(coerce_float(53), 53.0)

    def test_coerce_float_accepts_percent_and_comma(self) -> None:
        self.assertEqual(coerce_float("53,2 %"), 53.2)

    def test_coerce_float_rejects_unavailable_states(self) -> None:
        self.assertIsNone(coerce_float("unavailable"))
        self.assertIsNone(coerce_float("unknown"))

    def test_normalise_slot_energy_converts_power_units(self) -> None:
        self.assertEqual(normalise_slot_energy(60, 30, "W"), 0.03)
        self.assertEqual(normalise_slot_energy(0.5, 30, "kW"), 0.25)

    def test_normalise_slot_energy_preserves_energy_units(self) -> None:
        self.assertEqual(normalise_slot_energy(250, 30, "Wh"), 0.25)
        self.assertEqual(normalise_slot_energy(0.25, 30, "kWh"), 0.25)

    def test_normalise_slot_energy_uses_safer_unknown_unit_heuristic(self) -> None:
        self.assertEqual(normalise_slot_energy(60, 30), 0.03)
        self.assertEqual(normalise_slot_energy(0.25, 30), 0.25)

    def test_is_energy_unit(self) -> None:
        self.assertTrue(is_energy_unit("kWh"))
        self.assertFalse(is_energy_unit("W"))


if __name__ == "__main__":
    unittest.main()
