"""Load configuration helpers."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .const import (
    CONF_LOAD_DURATION_MINUTES,
    CONF_LOAD_EARLIEST_START,
    CONF_LOAD_ENERGY_KWH,
    CONF_LOAD_ID,
    CONF_LOAD_LATEST_END,
    CONF_LOAD_NAME,
    CONF_LOAD_POWER_KW,
    CONF_LOAD_PRIORITY,
    SUBENTRY_TYPE_LOAD,
)
from .forecast import LoadProfile


def load_profiles_from_json(raw_json: str) -> list[LoadProfile]:
    """Parse legacy JSON options into load profiles."""
    try:
        raw = json.loads(raw_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return _load_profiles_from_items(raw)


def load_profiles_from_subentries(config_entry: Any) -> list[LoadProfile]:
    """Parse Home Assistant config subentries into load profiles."""
    raw_subentries = getattr(config_entry, "subentries", {}) or {}
    if isinstance(raw_subentries, dict):
        subentries = raw_subentries.values()
    else:
        subentries = raw_subentries

    items: list[dict[str, Any]] = []
    for subentry in subentries:
        subentry_type = (
            getattr(subentry, "subentry_type", None)
            or getattr(subentry, "type", None)
            or getattr(subentry, "domain", None)
        )
        if subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        data = getattr(subentry, "data", None)
        if isinstance(data, dict):
            items.append(data)

    return _load_profiles_from_items(items)


def merge_load_profiles(
    subentry_loads: list[LoadProfile],
    legacy_loads: list[LoadProfile],
) -> list[LoadProfile]:
    """Prefer subentry loads and append legacy loads with distinct IDs."""
    merged = list(subentry_loads)
    seen_ids = {load.load_id for load in merged}
    for load in legacy_loads:
        if load.load_id in seen_ids:
            continue
        merged.append(load)
        seen_ids.add(load.load_id)
    return merged


def _load_profiles_from_items(items: list[Any]) -> list[LoadProfile]:
    loads: list[LoadProfile] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        name = str(item.get(CONF_LOAD_NAME) or f"Load {index + 1}")
        loads.append(
            LoadProfile(
                name=name,
                load_id=str(
                    item.get(CONF_LOAD_ID)
                    or name.lower().replace(" ", "_").replace("-", "_")
                ),
                priority=int(item.get(CONF_LOAD_PRIORITY, index + 1)),
                duration_minutes=int(item.get(CONF_LOAD_DURATION_MINUTES, 0)),
                power_kw=_optional_float(item.get(CONF_LOAD_POWER_KW)),
                energy_kwh=_optional_float(item.get(CONF_LOAD_ENERGY_KWH)),
                earliest_start=_parse_time(item.get(CONF_LOAD_EARLIEST_START)),
                latest_end=_parse_time(item.get(CONF_LOAD_LATEST_END)),
            )
        )
    return loads


def _parse_time(value: Any):
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
