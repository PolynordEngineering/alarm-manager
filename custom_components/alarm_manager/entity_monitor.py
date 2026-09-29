"""Home Assistant entity monitoring for Alarm Manager."""

from collections.abc import Callable
from datetime import timedelta

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .manager import AlarmManager


class EntityMonitor:
    """Monitor Home Assistant entities and time conditions for alarms."""

    def __init__(
        self,
        hass: HomeAssistant,
        manager: AlarmManager | None,
    ) -> None:
        """Initialize the entity monitor."""
        self.hass = hass
        self.manager = manager
        self._listeners: dict[str, list[Callable[[], None]]] = {}

    async def async_start_monitoring(
        self,
        alarm_id: str,
        entity_ids: list[str],
        has_time_conditions: bool = False,
    ) -> None:
        """Start monitoring all sources used by an alarm."""
        if self.manager is None:
            return

        self.stop_monitoring(alarm_id)
        listeners: list[Callable[[], None]] = []

        @callback
        def state_changed(event: Event) -> None:
            """Handle an entity state change."""
            if self.manager is None:
                return
            self.hass.async_create_task(
                self.manager.async_evaluate_alarm(alarm_id=alarm_id)
            )

        if entity_ids:
            listeners.append(
                async_track_state_change_event(
                    self.hass,
                    entity_ids,
                    state_changed,
                )
            )

        if has_time_conditions:
            @callback
            def time_changed(now) -> None:
                """Re-evaluate time conditions periodically."""
                if self.manager is None:
                    return
                self.hass.async_create_task(
                    self.manager.async_evaluate_alarm(alarm_id=alarm_id)
                )

            listeners.append(
                async_track_time_interval(
                    self.hass,
                    time_changed,
                    timedelta(seconds=30),
                )
            )

        # State-change events are the primary evaluation path. This short
        # reconciliation interval is a safety net for entities that are
        # restored/updated without producing a normal state_changed event.
        # It guarantees that an alarm cannot remain active indefinitely after
        # its condition has returned to normal.
        @callback
        def reconcile(now) -> None:
            if self.manager is None:
                return
            self.hass.async_create_task(
                self.manager.async_evaluate_alarm(alarm_id=alarm_id)
            )

        listeners.append(
            async_track_time_interval(
                self.hass,
                reconcile,
                timedelta(seconds=2),
            )
        )

        self._listeners[alarm_id] = listeners

        # Evaluate immediately so a newly-created alarm reflects the
        # current Home Assistant state without waiting for an event.
        await self.manager.async_evaluate_alarm(alarm_id=alarm_id)

    def stop_monitoring(self, alarm_id: str) -> None:
        """Stop monitoring an alarm."""
        listeners = self._listeners.pop(alarm_id, [])
        for unsubscribe in listeners:
            unsubscribe()

    def stop_all(self) -> None:
        """Stop monitoring all alarms."""
        for listeners in self._listeners.values():
            for unsubscribe in listeners:
                unsubscribe()
        self._listeners.clear()
