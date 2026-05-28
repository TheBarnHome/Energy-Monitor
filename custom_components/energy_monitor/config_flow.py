"""Config flow for Energy Monitor."""

from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_RESERVE_PERCENT,
    CONF_BATTERY_SOC_ENTITY,
    CONF_ENABLE_GRID_EXPORT,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HISTORY_DAYS,
    CONF_HOME_CONSUMPTION_ENTITY,
    CONF_LOADS,
    CONF_RESOLUTION_MINUTES,
    CONF_ROUNDTRIP_EFFICIENCY,
    CONF_SOLAR_FORECAST_ENTITY,
    DEFAULT_BATTERY_RESERVE_PERCENT,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_NAME,
    DEFAULT_RESOLUTION_MINUTES,
    DEFAULT_ROUNDTRIP_EFFICIENCY,
    DOMAIN,
)


class EnergyMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Energy Monitor config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_config_schema(),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return EnergyMonitorOptionsFlow(config_entry)


class EnergyMonitorOptionsFlow(config_entries.OptionsFlow):
    """Handle Energy Monitor options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                json.loads(user_input.get(CONF_LOADS, "[]") or "[]")
            except json.JSONDecodeError:
                errors[CONF_LOADS] = "invalid_json"
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._config_entry.options),
            errors=errors,
        )


def _config_schema() -> vol.Schema:
    entity = selector.EntitySelector()
    optional_entity = selector.EntitySelector(selector.EntitySelectorConfig())
    return vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(CONF_BATTERY_SOC_ENTITY): entity,
            vol.Required(CONF_BATTERY_CAPACITY_KWH): vol.Coerce(float),
            vol.Required(CONF_SOLAR_FORECAST_ENTITY): entity,
            vol.Required(CONF_HOME_CONSUMPTION_ENTITY): entity,
            vol.Optional(CONF_GRID_IMPORT_ENTITY): optional_entity,
            vol.Optional(CONF_ENABLE_GRID_EXPORT, default=False): bool,
            vol.Optional(CONF_GRID_EXPORT_ENTITY): optional_entity,
            vol.Optional(
                CONF_RESOLUTION_MINUTES, default=DEFAULT_RESOLUTION_MINUTES
            ): vol.In([15, 30, 60]),
            vol.Optional(CONF_HISTORY_DAYS, default=DEFAULT_HISTORY_DAYS): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
            vol.Optional(
                CONF_BATTERY_RESERVE_PERCENT,
                default=DEFAULT_BATTERY_RESERVE_PERCENT,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=50)),
            vol.Optional(
                CONF_ROUNDTRIP_EFFICIENCY,
                default=DEFAULT_ROUNDTRIP_EFFICIENCY,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=1.0)),
        }
    )


def _options_schema(options: config_entries.ConfigEntryOptions) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_LOADS,
                default=options.get(CONF_LOADS, "[]"),
            ): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True, type=selector.TextSelectorType.TEXT)
            )
        }
    )
