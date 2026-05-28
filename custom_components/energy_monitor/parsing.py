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
