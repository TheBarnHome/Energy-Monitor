"""Data coordinator for Energy Monitor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_RESERVE_PERCENT,
    CONF_BATTERY_SOC_ENTITY,
    CONF_ENABLE_GRID_EXPORT,
    CONF_HISTORY_DAYS,
    CONF_HOME_CONSUMPTION_ENTITY,
    CONF_LOADS,
    CONF_RESOLUTION_MINUTES,
    CONF_ROUNDTRIP_EFFICIENCY,
    CONF_SOLAR_FORECAST_ENTITY,
    DEFAULT_BATTERY_RESERVE_PERCENT,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_RESOLUTION_MINUTES,
    DEFAULT_ROUNDTRIP_EFFICIENCY,
    DOMAIN,
)
from .forecast import (
    EnergySample,
    ForecastConfig,
    ForecastResult,
    LoadProfile,
    build_baseload_profile,
    simulate_forecast,
)
from .loads import (
    load_profiles_from_json,
    load_profiles_from_subentries,
    merge_load_profiles,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnergyMonitorData:
    """Coordinator data exposed to platforms."""

    result: ForecastResult | None
    generated_at: datetime
    actual_soc_entity: str
    resolution_minutes: int
    error: str | None = None


class EnergyMonitorCoordinator(DataUpdateCoordinator[EnergyMonitorData]):
    """Fetch source entities and run the forecast."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> EnergyMonitorData:
        data = self.entry.data
        options = self.entry.options
        now = dt_util.now()
        resolution = int(data.get(CONF_RESOLUTION_MINUTES, DEFAULT_RESOLUTION_MINUTES))
        actual_soc_entity = data[CONF_BATTERY_SOC_ENTITY]

        try:
            current_soc = _state_float(self.hass, actual_soc_entity)
            if current_soc is None:
                raise ValueError(f"Missing numeric state for {actual_soc_entity}")

            solar_forecast = _solar_forecast_samples(
                self.hass,
                data[CONF_SOLAR_FORECAST_ENTITY],
                resolution,
            )
            history = await _async_consumption_history(
                self.hass,
                data[CONF_HOME_CONSUMPTION_ENTITY],
                int(data.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS)),
                resolution,
            )
            baseload = build_baseload_profile(history, resolution)
            config = ForecastConfig(
                resolution_minutes=resolution,
                battery_capacity_kwh=float(data[CONF_BATTERY_CAPACITY_KWH]),
                battery_reserve_percent=float(
                    data.get(
                        CONF_BATTERY_RESERVE_PERCENT,
                        DEFAULT_BATTERY_RESERVE_PERCENT,
                    )
                ),
                roundtrip_efficiency=float(
                    data.get(
                        CONF_ROUNDTRIP_EFFICIENCY,
                        DEFAULT_ROUNDTRIP_EFFICIENCY,
                    )
                ),
                export_enabled=bool(data.get(CONF_ENABLE_GRID_EXPORT, False)),
            )
            loads = merge_load_profiles(
                load_profiles_from_subentries(self.entry),
                load_profiles_from_json(options.get(CONF_LOADS, "[]")),
            )
            result = simulate_forecast(
                now=now,
                current_soc_percent=current_soc,
                solar_forecast=solar_forecast,
                baseload_profile=baseload,
                config=config,
                loads=loads,
            )
            return EnergyMonitorData(result, now, actual_soc_entity, resolution)
        except Exception as err:  # pragma: no cover - logged for HA diagnostics
            _LOGGER.exception("Unable to update Energy Monitor forecast")
            return EnergyMonitorData(None, now, actual_soc_entity, resolution, str(err))


def _state_float(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _solar_forecast_samples(
    hass: HomeAssistant,
    entity_id: str,
    resolution_minutes: int,
) -> list[EnergySample]:
    state = hass.states.get(entity_id)
    if state is None:
        return []

    raw = (
        state.attributes.get("forecast")
        or state.attributes.get("forecasts")
        or state.attributes.get("data")
        or []
    )
    samples: list[EnergySample] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        when_raw = item.get("datetime") or item.get("start") or item.get("period_start")
        value = (
            item.get("solar_forecast_kwh")
            or item.get("energy_kwh")
            or item.get("pv_estimate")
            or item.get("estimate")
            or item.get("value")
        )
        when = _parse_datetime(when_raw)
        energy = _coerce_float(value)
        if when is None or energy is None:
            continue
        samples.append(EnergySample(when, _normalise_energy(energy, resolution_minutes)))
    return samples


async def _async_consumption_history(
    hass: HomeAssistant,
    entity_id: str,
    history_days: int,
    resolution_minutes: int,
) -> list[EnergySample]:
    """Fetch historical states and convert them to rough slot energy samples."""
    start = dt_util.now() - timedelta(days=history_days)
    end = dt_util.now()

    def _fetch() -> list[EnergySample]:
        from homeassistant.components.recorder.history import state_changes_during_period

        states_by_entity = state_changes_during_period(
            hass,
            start,
            end,
            entity_id,
            include_start_time_state=True,
        )
        states = states_by_entity.get(entity_id, [])
        samples: list[EnergySample] = []
        for state in states:
            value = _coerce_float(state.state)
            if value is None:
                continue
            samples.append(
                EnergySample(
                    state.last_updated,
                    _normalise_energy(value, resolution_minutes),
                )
            )
        return samples

    return await hass.async_add_executor_job(_fetch)


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else dt_util.as_local(parsed)


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_energy(value: float, resolution_minutes: int) -> float:
    """Accept kWh-like values and convert large W-like values to slot kWh."""
    if abs(value) > 100:
        return value / 1000 * resolution_minutes / 60
    return value
