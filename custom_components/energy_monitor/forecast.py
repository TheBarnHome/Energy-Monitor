"""Forecast engine for Energy Monitor.

This module intentionally has no Home Assistant imports so the core behavior can
be tested with plain Python.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from statistics import median
from typing import Iterable, Literal


RecommendationState = Literal["recommended", "delay", "avoid", "insufficient_data"]


@dataclass(frozen=True)
class EnergySample:
    """Energy sample for one time slot."""

    start: datetime
    energy_kwh: float


@dataclass(frozen=True)
class LoadProfile:
    """Programmable load definition."""

    name: str
    load_id: str
    priority: int
    duration_minutes: int
    power_kw: float | None = None
    energy_kwh: float | None = None
    earliest_start: time | None = None
    latest_end: time | None = None

    @property
    def required_energy_kwh(self) -> float:
        """Return configured energy, deriving it from power and duration if needed."""
        if self.energy_kwh is not None:
            return max(0.0, self.energy_kwh)
        if self.power_kw is None:
            return 0.0
        return max(0.0, self.power_kw * self.duration_minutes / 60)


@dataclass(frozen=True)
class ForecastConfig:
    """Inputs controlling forecast behavior."""

    resolution_minutes: int = 30
    battery_capacity_kwh: float = 10.0
    battery_reserve_percent: float = 5.0
    roundtrip_efficiency: float = 0.92
    solar_takeover_slots: int = 2
    export_enabled: bool = False


@dataclass(frozen=True)
class ForecastPoint:
    """One forecast point."""

    datetime: datetime
    soc_percent: float
    battery_energy_kwh: float
    solar_forecast_kwh: float
    baseload_kwh: float

    def as_dict(self) -> dict[str, str | float]:
        """Return a Home Assistant attribute friendly representation."""
        return {
            "datetime": self.datetime.isoformat(),
            "soc_percent": round(self.soc_percent, 2),
            "battery_energy_kwh": round(self.battery_energy_kwh, 3),
            "solar_forecast_kwh": round(self.solar_forecast_kwh, 3),
            "baseload_kwh": round(self.baseload_kwh, 3),
        }


@dataclass(frozen=True)
class LoadRecommendation:
    """Recommendation for a programmable load."""

    load_id: str
    name: str
    state: RecommendationState
    reason: str
    start: datetime | None = None
    end: datetime | None = None
    min_soc_percent: float | None = None

    def as_dict(self) -> dict[str, str | float | None]:
        """Return an attribute friendly representation."""
        return {
            "load_id": self.load_id,
            "name": self.name,
            "state": self.state,
            "reason": self.reason,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "min_soc_percent": (
                round(self.min_soc_percent, 2)
                if self.min_soc_percent is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ForecastResult:
    """Complete forecast output."""

    points: list[ForecastPoint]
    solar_takeover_time: datetime | None
    min_soc_percent: float | None
    holds_until_solar: bool
    recommendations: list[LoadRecommendation] = field(default_factory=list)


def align_datetime(value: datetime, resolution_minutes: int) -> datetime:
    """Round a datetime down to the configured slot boundary."""
    minute = value.minute - (value.minute % resolution_minutes)
    return value.replace(minute=minute, second=0, microsecond=0)


def build_baseload_profile(
    history: Iterable[EnergySample],
    resolution_minutes: int,
    fallback_kwh: float = 0.25,
    spike_factor: float = 2.5,
) -> dict[int, float]:
    """Build a median slot profile with simple spike filtering."""
    by_slot: dict[int, list[float]] = defaultdict(list)
    slots_per_day = int(24 * 60 / resolution_minutes)

    for sample in history:
        slot = _slot_index(sample.start, resolution_minutes)
        by_slot[slot].append(max(0.0, sample.energy_kwh))

    profile: dict[int, float] = {}
    all_values = [value for values in by_slot.values() for value in values]
    global_fallback = median(all_values) if all_values else fallback_kwh

    for slot in range(slots_per_day):
        values = by_slot.get(slot, [])
        if not values:
            profile[slot] = global_fallback
            continue

        first_pass = median(values)
        threshold = max(first_pass * spike_factor, first_pass + fallback_kwh)
        filtered = [value for value in values if value <= threshold]
        profile[slot] = median(filtered or values)

    return profile


def simulate_forecast(
    *,
    now: datetime,
    current_soc_percent: float,
    solar_forecast: Iterable[EnergySample],
    baseload_profile: dict[int, float],
    config: ForecastConfig,
    loads: Iterable[LoadProfile] = (),
) -> ForecastResult:
    """Simulate battery SoC and produce load recommendations."""
    resolution = config.resolution_minutes
    start = align_datetime(now, resolution)
    solar_by_time = {
        align_datetime(sample.start, resolution): max(0.0, sample.energy_kwh)
        for sample in solar_forecast
    }
    horizon_end = _default_horizon_end(start, resolution)
    times = list(_time_slots(start, horizon_end, resolution))

    if not times:
        return ForecastResult([], None, None, False, [])

    points = _simulate_points(
        times=times,
        current_soc_percent=current_soc_percent,
        solar_by_time=solar_by_time,
        baseload_profile=baseload_profile,
        config=config,
        extra_load_by_time={},
    )
    takeover_time = find_solar_takeover(points, config.solar_takeover_slots)
    clipped_points = [point for point in points if not takeover_time or point.datetime <= takeover_time]
    min_soc = min((point.soc_percent for point in clipped_points), default=None)
    holds = bool(min_soc is not None and min_soc >= config.battery_reserve_percent)
    recommendations = recommend_loads(
        loads=loads,
        times=times,
        solar_by_time=solar_by_time,
        baseload_profile=baseload_profile,
        current_soc_percent=current_soc_percent,
        config=config,
        cutoff=takeover_time or horizon_end,
    )
    return ForecastResult(points, takeover_time, min_soc, holds, recommendations)


def find_solar_takeover(
    points: list[ForecastPoint],
    required_slots: int,
) -> datetime | None:
    """Find the first slot where solar covers baseload for enough consecutive slots."""
    streak = 0
    candidate: datetime | None = None
    for point in points:
        if point.solar_forecast_kwh >= point.baseload_kwh and point.baseload_kwh > 0:
            if streak == 0:
                candidate = point.datetime
            streak += 1
            if streak >= required_slots:
                return candidate
        else:
            streak = 0
            candidate = None
    return None


def recommend_loads(
    *,
    loads: Iterable[LoadProfile],
    times: list[datetime],
    solar_by_time: dict[datetime, float],
    baseload_profile: dict[int, float],
    current_soc_percent: float,
    config: ForecastConfig,
    cutoff: datetime,
) -> list[LoadRecommendation]:
    """Recommend the earliest viable slot for each load, ordered by priority."""
    recommendations: list[LoadRecommendation] = []
    scheduled_load: dict[datetime, float] = {}

    for load in sorted(loads, key=lambda item: item.priority):
        if load.required_energy_kwh <= 0 or load.duration_minutes <= 0:
            recommendations.append(
                LoadRecommendation(
                    load.load_id,
                    load.name,
                    "insufficient_data",
                    "Missing load energy or duration.",
                )
            )
            continue

        best: tuple[datetime, datetime, float] | None = None
        for start in times:
            end = start + timedelta(minutes=load.duration_minutes)
            if end > cutoff or not _within_window(start, end, load):
                continue

            extra = dict(scheduled_load)
            for slot in _time_slots(start, end, config.resolution_minutes):
                extra[slot] = extra.get(slot, 0.0) + _load_energy_for_slot(
                    load, config.resolution_minutes
                )

            simulated = _simulate_points(
                times=times,
                current_soc_percent=current_soc_percent,
                solar_by_time=solar_by_time,
                baseload_profile=baseload_profile,
                config=config,
                extra_load_by_time=extra,
            )
            until_cutoff = [point for point in simulated if point.datetime <= cutoff]
            candidate_min = min(point.soc_percent for point in until_cutoff)
            if candidate_min >= config.battery_reserve_percent:
                best = (start, end, candidate_min)
                scheduled_load = extra
                break

        if best:
            start, end, min_soc = best
            recommendations.append(
                LoadRecommendation(
                    load.load_id,
                    load.name,
                    "recommended",
                    "Battery forecast remains viable until solar takeover.",
                    start,
                    end,
                    min_soc,
                )
            )
        else:
            recommendations.append(
                LoadRecommendation(
                    load.load_id,
                    load.name,
                    "avoid",
                    "No viable slot before solar takeover without crossing reserve.",
                )
            )

    return recommendations


def _simulate_points(
    *,
    times: list[datetime],
    current_soc_percent: float,
    solar_by_time: dict[datetime, float],
    baseload_profile: dict[int, float],
    config: ForecastConfig,
    extra_load_by_time: dict[datetime, float],
) -> list[ForecastPoint]:
    capacity = max(config.battery_capacity_kwh, 0.001)
    energy = capacity * min(100.0, max(0.0, current_soc_percent)) / 100
    points: list[ForecastPoint] = []

    for when in times:
        solar = solar_by_time.get(when, 0.0)
        baseload = baseload_profile.get(_slot_index(when, config.resolution_minutes), 0.0)
        load = extra_load_by_time.get(when, 0.0)
        demand = baseload + load
        delta = solar * config.roundtrip_efficiency - demand
        energy = min(capacity, max(0.0, energy + delta))
        points.append(
            ForecastPoint(
                datetime=when,
                soc_percent=energy / capacity * 100,
                battery_energy_kwh=energy,
                solar_forecast_kwh=solar,
                baseload_kwh=baseload,
            )
        )

    return points


def _slot_index(value: datetime, resolution_minutes: int) -> int:
    return int((value.hour * 60 + value.minute) / resolution_minutes)


def _default_horizon_end(start: datetime, resolution_minutes: int) -> datetime:
    tomorrow = start.date() + timedelta(days=1)
    end = datetime.combine(tomorrow, time(hour=18), tzinfo=start.tzinfo)
    if end <= start:
        end += timedelta(days=1)
    return align_datetime(end, resolution_minutes)


def _time_slots(start: datetime, end: datetime, resolution_minutes: int) -> Iterable[datetime]:
    current = start
    step = timedelta(minutes=resolution_minutes)
    while current < end:
        yield current
        current += step


def _within_window(start: datetime, end: datetime, load: LoadProfile) -> bool:
    if load.earliest_start and start.time() < load.earliest_start:
        return False
    if load.latest_end and end.time() > load.latest_end:
        return False
    return True


def _load_energy_for_slot(load: LoadProfile, resolution_minutes: int) -> float:
    if load.power_kw is not None:
        return load.power_kw * resolution_minutes / 60
    slots = max(1, load.duration_minutes / resolution_minutes)
    return load.required_energy_kwh / slots
