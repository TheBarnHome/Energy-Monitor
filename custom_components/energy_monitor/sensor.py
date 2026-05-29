"""Sensor platform for Energy Monitor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnergyMonitorCoordinator
from .loads import (
    load_profiles_from_json,
    load_profiles_from_subentries,
    merge_load_profiles,
)


@dataclass(frozen=True, kw_only=True)
class EnergyMonitorSensorDescription(SensorEntityDescription):
    """Energy Monitor sensor description."""

    value_fn: Any
    attrs_fn: Any | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energy Monitor sensors."""
    coordinator: EnergyMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]
    descriptions = [
        EnergyMonitorSensorDescription(
            key="battery_forecast",
            translation_key="battery_forecast",
            name="Battery forecast",
            native_unit_of_measurement=PERCENTAGE,
            value_fn=_battery_forecast_state,
            attrs_fn=_battery_forecast_attrs,
        ),
        EnergyMonitorSensorDescription(
            key="min_soc_before_solar",
            translation_key="min_soc_before_solar",
            name="Min SoC before solar",
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda data: _result_value(data, "min_soc_percent"),
        ),
        EnergyMonitorSensorDescription(
            key="solar_takeover_time",
            translation_key="solar_takeover_time",
            name="Solar takeover time",
            value_fn=lambda data: (
                data.result.solar_takeover_time.isoformat()
                if data.result and data.result.solar_takeover_time
                else None
            ),
        ),
        EnergyMonitorSensorDescription(
            key="recommendation_summary",
            translation_key="recommendation_summary",
            name="Recommendation summary",
            value_fn=_recommendation_summary_state,
            attrs_fn=_recommendation_summary_attrs,
        ),
    ]
    async_add_entities(
        EnergyMonitorSensor(coordinator, entry.entry_id, description)
        for description in descriptions
    )
    loads = merge_load_profiles(
        load_profiles_from_subentries(entry),
        load_profiles_from_json(entry.options.get("loads", "[]")),
    )
    async_add_entities(
        EnergyMonitorLoadSensor(coordinator, entry.entry_id, load.load_id, load.name)
        for load in loads
    )


class EnergyMonitorSensor(CoordinatorEntity[EnergyMonitorCoordinator], SensorEntity):
    """Energy Monitor sensor."""

    entity_description: EnergyMonitorSensorDescription

    def __init__(
        self,
        coordinator: EnergyMonitorCoordinator,
        entry_id: str,
        description: EnergyMonitorSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        attrs: dict[str, Any] = {}
        if data is None:
            return attrs
        if data.error:
            attrs["error"] = data.error
        if self.entity_description.attrs_fn:
            attrs.update(self.entity_description.attrs_fn(data))
        return attrs


class EnergyMonitorLoadSensor(CoordinatorEntity[EnergyMonitorCoordinator], SensorEntity):
    """Sensor exposing the recommendation for one configured load."""

    def __init__(
        self,
        coordinator: EnergyMonitorCoordinator,
        entry_id: str,
        load_id: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._load_id = load_id
        self._attr_unique_id = f"{entry_id}_load_{load_id}"
        self._attr_name = f"Energy Monitor {name}"
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> str | None:
        """Return the recommendation state for this load."""
        recommendation = self._recommendation()
        return recommendation.state if recommendation else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return load recommendation attributes."""
        recommendation = self._recommendation()
        if not recommendation:
            return {}
        return recommendation.as_dict()

    def _recommendation(self):
        data = self.coordinator.data
        if not data or not data.result:
            return None
        for recommendation in data.result.recommendations:
            if recommendation.load_id == self._load_id:
                return recommendation
        return None


def _battery_forecast_state(data) -> float | None:
    if not data.result or data.result.min_soc_percent is None:
        return None
    return round(data.result.min_soc_percent, 2)


def _battery_forecast_attrs(data) -> dict[str, Any]:
    if not data.result:
        return {
            "forecast": [],
            "actual_entity": data.actual_soc_entity,
            "solar_forecast_entity": data.solar_forecast_entity,
            "home_consumption_entity": data.home_consumption_entity,
            "generated_at": data.generated_at.isoformat(),
            "resolution_minutes": data.resolution_minutes,
            "history_samples": data.history_samples,
            "solar_forecast_samples": data.solar_forecast_samples,
            "baseload_average_kwh": data.baseload_average_kwh,
        }
    return {
        "forecast": [point.as_dict() for point in data.result.points],
        "actual_entity": data.actual_soc_entity,
        "solar_forecast_entity": data.solar_forecast_entity,
        "home_consumption_entity": data.home_consumption_entity,
        "generated_at": data.generated_at.isoformat(),
        "resolution_minutes": data.resolution_minutes,
        "history_samples": data.history_samples,
        "solar_forecast_samples": data.solar_forecast_samples,
        "baseload_average_kwh": (
            round(data.baseload_average_kwh, 3)
            if data.baseload_average_kwh is not None
            else None
        ),
        "horizon_end": (
            data.result.points[-1].datetime.isoformat()
            if data.result.points
            else None
        ),
        "solar_takeover_time": (
            data.result.solar_takeover_time.isoformat()
            if data.result.solar_takeover_time
            else None
        ),
        "holds_until_solar": data.result.holds_until_solar,
    }


def _recommendation_summary_state(data) -> str | None:
    if not data.result:
        return None
    if not data.result.recommendations:
        return "no_loads_configured"
    states = [item.state for item in data.result.recommendations]
    if "avoid" in states:
        return "some_loads_avoid"
    if "recommended" in states:
        return "recommended"
    return states[0]


def _recommendation_summary_attrs(data) -> dict[str, Any]:
    if not data.result:
        return {"recommendations": []}
    return {
        "recommendations": [
            recommendation.as_dict()
            for recommendation in data.result.recommendations
        ]
    }


def _result_value(data, attr: str) -> Any:
    if not data.result:
        return None
    value = getattr(data.result, attr)
    return round(value, 2) if isinstance(value, float) else value
