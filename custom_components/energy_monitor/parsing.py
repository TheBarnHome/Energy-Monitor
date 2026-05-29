"""Parsing helpers shared by the integration."""

from __future__ import annotations

from typing import Any


UNAVAILABLE_STATES = {"unknown", "unavailable", "none", ""}


def coerce_float(value: Any) -> float | None:
    """Convert common Home Assistant state formats to a float."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None

    normalised = value.strip().lower()
    if normalised in UNAVAILABLE_STATES:
        return None

    normalised = normalised.replace(",", ".")
    if normalised.endswith("%"):
        normalised = normalised[:-1].strip()

    try:
        return float(normalised)
    except ValueError:
        return None


def normalise_slot_energy(
    value: float,
    resolution_minutes: int,
    unit_of_measurement: str | None = None,
) -> float:
    """Convert common HA power/energy values to kWh for one forecast slot."""
    unit = (unit_of_measurement or "").strip().lower()
    hours = resolution_minutes / 60

    if unit in {"w", "watt", "watts"}:
        return value / 1000 * hours
    if unit in {"kw", "kilowatt", "kilowatts"}:
        return value * hours
    if unit in {"wh", "watt-hour", "watt-hours"}:
        return value / 1000
    if unit in {"kwh", "kilowatt-hour", "kilowatt-hours"}:
        return value

    # Unknown units are most often either kWh forecast values or W power states.
    # A half-hour energy sample above 20 kWh is unrealistic for a baseload, so
    # treat large values as W while preserving small kWh forecast values.
    if abs(value) > 20:
        return value / 1000 * hours
    return value


def is_energy_unit(unit_of_measurement: str | None) -> bool:
    """Return whether the unit represents energy rather than power."""
    unit = (unit_of_measurement or "").strip().lower()
    return unit in {
        "wh",
        "watt-hour",
        "watt-hours",
        "kwh",
        "kilowatt-hour",
        "kilowatt-hours",
    }
