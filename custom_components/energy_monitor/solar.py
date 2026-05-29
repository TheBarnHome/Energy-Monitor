"""Solar forecast parsing helpers."""

from __future__ import annotations

from typing import Any


def solar_forecast_raw(attributes: dict[str, Any]) -> tuple[Any, str | None]:
    """Return the richest solar forecast attribute and its unit."""
    for key in ("forecast", "forecasts", "data"):
        raw = attributes.get(key)
        if raw:
            return raw, attributes.get("unit_of_measurement")
    if attributes.get("wh_period"):
        return attributes["wh_period"], "Wh"
    if attributes.get("watts"):
        return attributes["watts"], "W"
    return [], attributes.get("unit_of_measurement")


def solar_forecast_values(
    raw: Any,
    default_unit: str | None,
) -> list[tuple[Any, Any, str | None]]:
    """Normalise supported forecast structures to datetime/value/unit tuples."""
    if isinstance(raw, dict):
        return [(when, value, default_unit) for when, value in raw.items()]
    if not isinstance(raw, list):
        return []

    values: list[tuple[Any, Any, str | None]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        when = item.get("datetime") or item.get("start") or item.get("period_start")
        value = (
            item.get("solar_forecast_kwh")
            or item.get("energy_kwh")
            or item.get("pv_estimate")
            or item.get("estimate")
            or item.get("value")
        )
        unit = item.get("unit_of_measurement") or item.get("unit") or default_unit
        values.append((when, value, unit))
    return values
