"""Home Assistant entity monitoring for Alarm Manager."""

from collections.abc import Callable

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .manager import AlarmManager


class EntityMonitor:
    """Monitor Home Assistant entities for alarm conditions."""

    def __init__(
        self,
        hass: HomeAssistant,
        manager: AlarmManager | None,
    ) -> None:
        """Initialize the entity monitor."""
        self.hass = hass
        self.manager = manager
        self._listeners: dict[str, Callable[[], None]] = {}

    async def async_start_monitoring(
        self,
        alarm_id: str,
        entity_id: str,
    ) -> None:
        """Start monitoring an entity for an alarm."""

        if self.manager is None:
            return

        @callback
        def state_changed(event: Event) -> None:
            """Handle an entity state change."""

            if self.manager is None:
                return

            new_state = event.data.get("new_state")

            if new_state is None:
                return

            self.hass.async_create_task(
                self.manager.async_evaluate_alarm(
                    alarm_id=alarm_id,
                    state=new_state.state,
                )
            )

        unsubscribe = async_track_state_change_event(
            self.hass,
            [entity_id],
            state_changed,
        )

        existing_listener = self._listeners.get(alarm_id)

        if existing_listener is not None:
            existing_listener()

        self._listeners[alarm_id] = unsubscribe

        # Evaluate the current entity state immediately.
        current_state = self.hass.states.get(entity_id)

        if current_state is not None:
            await self.manager.async_evaluate_alarm(
                alarm_id=alarm_id,
                state=current_state.state,
            )

    def stop_monitoring(
        self,
        alarm_id: str,
    ) -> None:
        """Stop monitoring an alarm."""

        unsubscribe = self._listeners.pop(
            alarm_id,
            None,
        )

        if unsubscribe is not None:
            unsubscribe()

    def stop_all(self) -> None:
        """Stop monitoring all alarms."""

        for unsubscribe in self._listeners.values():
            unsubscribe()

        self._listeners.clear()