from __future__ import annotations

from dataclasses import dataclass
import unittest

from custom_components.energy_monitor.loads import (
    load_profiles_from_json,
    load_profiles_from_subentries,
    merge_load_profiles,
)


@dataclass
class FakeSubentry:
    subentry_type: str
    data: dict


@dataclass
class FakeEntry:
    subentries: dict[str, FakeSubentry]


class LoadConfigTest(unittest.TestCase):
    def test_load_profiles_from_json(self) -> None:
        loads = load_profiles_from_json(
            """
            [
              {
                "id": "ev",
                "name": "EV",
                "priority": 1,
                "duration_minutes": 120,
                "energy_kwh": 7.5,
                "earliest_start": "22:00",
                "latest_end": "08:00"
              }
            ]
            """
        )

        self.assertEqual(len(loads), 1)
        self.assertEqual(loads[0].load_id, "ev")
        self.assertEqual(loads[0].required_energy_kwh, 7.5)
        self.assertEqual(loads[0].earliest_start.hour, 22)

    def test_load_profiles_from_subentries(self) -> None:
        entry = FakeEntry(
            {
                "abc": FakeSubentry(
                    "load",
                    {
                        "id": "spa",
                        "name": "Spa",
                        "priority": 2,
                        "duration_minutes": 90,
                        "power_kw": 2,
                    },
                )
            }
        )

        loads = load_profiles_from_subentries(entry)

        self.assertEqual(len(loads), 1)
        self.assertEqual(loads[0].load_id, "spa")
        self.assertEqual(loads[0].required_energy_kwh, 3.0)

    def test_subentries_override_legacy_duplicates(self) -> None:
        subentry_loads = load_profiles_from_json(
            '[{"id": "ev", "name": "EV UI", "duration_minutes": 60, "energy_kwh": 1}]'
        )
        legacy_loads = load_profiles_from_json(
            '[{"id": "ev", "name": "EV JSON", "duration_minutes": 60, "energy_kwh": 2}]'
        )

        merged = merge_load_profiles(subentry_loads, legacy_loads)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].name, "EV UI")


if __name__ == "__main__":
    unittest.main()
