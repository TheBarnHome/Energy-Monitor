from __future__ import annotations

import unittest

from custom_components.energy_monitor.solar import (
    solar_forecast_raw,
    solar_forecast_values,
)


class SolarForecastParsingTest(unittest.TestCase):
    def test_wh_period_mapping_is_used_before_watts(self) -> None:
        raw, unit = solar_forecast_raw(
            {
                "unit_of_measurement": "kWh",
                "watts": {"2026-05-29T08:00:00+02:00": 500},
                "wh_period": {"2026-05-29T08:00:00+02:00": 125},
            }
        )

        self.assertEqual(unit, "Wh")
        self.assertEqual(raw, {"2026-05-29T08:00:00+02:00": 125})

    def test_mapping_values_are_converted_to_tuples(self) -> None:
        values = solar_forecast_values(
            {"2026-05-29T08:00:00+02:00": 125},
            "Wh",
        )

        self.assertEqual(values, [("2026-05-29T08:00:00+02:00", 125, "Wh")])

    def test_list_values_keep_existing_shape(self) -> None:
        values = solar_forecast_values(
            [{"datetime": "2026-05-29T08:00:00+02:00", "energy_kwh": 0.125}],
            "kWh",
        )

        self.assertEqual(values, [("2026-05-29T08:00:00+02:00", 0.125, "kWh")])


if __name__ == "__main__":
    unittest.main()
