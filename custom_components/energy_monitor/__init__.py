"""Energy Monitor custom integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS, SERVICE_RECALCULATE


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Energy Monitor from a config entry."""
    from .coordinator import EnergyMonitorCoordinator

    coordinator = EnergyMonitorCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _handle_recalculate(call) -> None:
        target_entry_id = call.data.get("entry_id")
        coordinators = hass.data.get(DOMAIN, {})
        for entry_id, item in coordinators.items():
            if target_entry_id and target_entry_id != entry_id:
                continue
            await item.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_RECALCULATE):
        hass.services.async_register(DOMAIN, SERVICE_RECALCULATE, _handle_recalculate)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_RECALCULATE)
    return unload_ok
