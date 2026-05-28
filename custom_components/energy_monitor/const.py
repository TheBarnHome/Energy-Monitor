"""Constants for the Energy Monitor integration."""

from __future__ import annotations

DOMAIN = "energy_monitor"
PLATFORMS = ["sensor", "calendar"]

DEFAULT_NAME = "Energy Monitor"
DEFAULT_RESOLUTION_MINUTES = 30
DEFAULT_HISTORY_DAYS = 14
DEFAULT_BATTERY_RESERVE_PERCENT = 5.0
DEFAULT_ROUNDTRIP_EFFICIENCY = 0.92
DEFAULT_MINIMUM_SOLAR_TAKEOVER_SLOTS = 2

CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"
CONF_BATTERY_CAPACITY_KWH = "battery_capacity_kwh"
CONF_SOLAR_FORECAST_ENTITY = "solar_forecast_entity"
CONF_HOME_CONSUMPTION_ENTITY = "home_consumption_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"
CONF_ENABLE_GRID_EXPORT = "enable_grid_export"
CONF_RESOLUTION_MINUTES = "resolution_minutes"
CONF_HISTORY_DAYS = "history_days"
CONF_BATTERY_RESERVE_PERCENT = "battery_reserve_percent"
CONF_ROUNDTRIP_EFFICIENCY = "roundtrip_efficiency"
CONF_LOADS = "loads"

SERVICE_RECALCULATE = "recalculate"
