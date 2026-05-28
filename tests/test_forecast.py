from __future__ import annotations

from datetime import datetime, timedelta
import unittest
from zoneinfo import ZoneInfo

from custom_components.energy_monitor.forecast import (
    EnergySample,
    ForecastConfig,
    LoadProfile,
    build_baseload_profile,
    simulate_forecast,
)


TZ = ZoneInfo("Europe/Paris")


class ForecastTest(unittest.TestCase):
    def test_forecast_points_are_complete_and_bounded(self) -> None:
        now = datetime(2026, 5, 28, 22, 17, tzinfo=TZ)
        baseload = {slot: 0.2 for slot in range(48)}
        solar = [
            EnergySample(datetime(2026, 5, 29, 8, 0, tzinfo=TZ), 0.5),
            EnergySample(datetime(2026, 5, 29, 8, 30, tzinfo=TZ), 0.5),
        ]

        result = simulate_forecast(
            now=now,
            current_soc_percent=60,
            solar_forecast=solar,
            baseload_profile=baseload,
            config=ForecastConfig(battery_capacity_kwh=10),
        )

        self.assertTrue(result.points)
        self.assertEqual(
            result.points[0].datetime, datetime(2026, 5, 28, 22, 0, tzinfo=TZ)
        )
        self.assertTrue(all(0 <= point.soc_percent <= 100 for point in result.points))
        self.assertTrue(
            all(
                later.datetime - earlier.datetime == timedelta(minutes=30)
                for earlier, later in zip(result.points, result.points[1:])
            )
        )

    def test_solar_takeover_requires_consecutive_covering_slots(self) -> None:
        now = datetime(2026, 5, 28, 23, 0, tzinfo=TZ)
        baseload = {slot: 0.3 for slot in range(48)}
        solar = [
            EnergySample(datetime(2026, 5, 29, 7, 30, tzinfo=TZ), 0.4),
            EnergySample(datetime(2026, 5, 29, 8, 0, tzinfo=TZ), 0.1),
            EnergySample(datetime(2026, 5, 29, 8, 30, tzinfo=TZ), 0.4),
            EnergySample(datetime(2026, 5, 29, 9, 0, tzinfo=TZ), 0.4),
        ]

        result = simulate_forecast(
            now=now,
            current_soc_percent=90,
            solar_forecast=solar,
            baseload_profile=baseload,
            config=ForecastConfig(battery_capacity_kwh=10),
        )

        self.assertEqual(
            result.solar_takeover_time, datetime(2026, 5, 29, 8, 30, tzinfo=TZ)
        )

    def test_baseload_profile_filters_spikes(self) -> None:
        samples = []
        base = datetime(2026, 5, 1, 22, 0, tzinfo=TZ)
        for day in range(7):
            samples.append(EnergySample(base + timedelta(days=day), 0.2))
        samples.append(EnergySample(base + timedelta(days=8), 5.0))

        profile = build_baseload_profile(samples, 30)

        slot = int((22 * 60) / 30)
        self.assertEqual(profile[slot], 0.2)

    def test_load_is_avoided_when_it_breaks_reserve(self) -> None:
        now = datetime(2026, 5, 28, 22, 0, tzinfo=TZ)
        baseload = {slot: 0.4 for slot in range(48)}
        solar = [
            EnergySample(datetime(2026, 5, 29, 8, 0, tzinfo=TZ), 0.5),
            EnergySample(datetime(2026, 5, 29, 8, 30, tzinfo=TZ), 0.5),
        ]

        result = simulate_forecast(
            now=now,
            current_soc_percent=45,
            solar_forecast=solar,
            baseload_profile=baseload,
            config=ForecastConfig(
                battery_capacity_kwh=10,
                battery_reserve_percent=10,
            ),
            loads=[
                LoadProfile(
                    name="EV",
                    load_id="ev",
                    priority=1,
                    duration_minutes=120,
                    energy_kwh=5,
                )
            ],
        )

        self.assertEqual(result.recommendations[0].state, "avoid")

    def test_load_is_recommended_when_reserve_holds(self) -> None:
        now = datetime(2026, 5, 28, 22, 0, tzinfo=TZ)
        baseload = {slot: 0.1 for slot in range(48)}
        solar = [
            EnergySample(datetime(2026, 5, 29, 8, 0, tzinfo=TZ), 0.5),
            EnergySample(datetime(2026, 5, 29, 8, 30, tzinfo=TZ), 0.5),
        ]

        result = simulate_forecast(
            now=now,
            current_soc_percent=80,
            solar_forecast=solar,
            baseload_profile=baseload,
            config=ForecastConfig(
                battery_capacity_kwh=10,
                battery_reserve_percent=10,
            ),
            loads=[
                LoadProfile(
                    name="Spa",
                    load_id="spa",
                    priority=1,
                    duration_minutes=60,
                    power_kw=1.0,
                )
            ],
        )

        self.assertEqual(result.recommendations[0].state, "recommended")
        self.assertEqual(result.recommendations[0].start, now)


if __name__ == "__main__":
    unittest.main()
