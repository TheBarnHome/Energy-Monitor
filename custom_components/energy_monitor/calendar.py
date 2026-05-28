"""Calendar platform for Energy Monitor recommendations."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnergyMonitorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the recommendation calendar."""
    coordinator: EnergyMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EnergyMonitorCalendar(coordinator, entry.entry_id)])


class EnergyMonitorCalendar(CoordinatorEntity[EnergyMonitorCoordinator], CalendarEntity):
    """Calendar entity exposing recommended load windows."""

    def __init__(self, coordinator: EnergyMonitorCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_recommendation_calendar"
        self._attr_name = "Energy Monitor recommendations"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next recommendation event."""
        events = self._events()
        return events[0] if events else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return recommendation events in the requested range."""
        return [
            event
            for event in self._events()
            if event.start < end_date and event.end > start_date
        ]

    def _events(self) -> list[CalendarEvent]:
        data = self.coordinator.data
        if not data or not data.result:
            return []

        events: list[CalendarEvent] = []
        for recommendation in data.result.recommendations:
            if (
                recommendation.state != "recommended"
                or recommendation.start is None
                or recommendation.end is None
            ):
                continue
            events.append(
                CalendarEvent(
                    start=recommendation.start,
                    end=recommendation.end,
                    summary=f"{recommendation.name}: recommended",
                    description=recommendation.reason,
                )
            )
        return sorted(events, key=lambda event: event.start)
