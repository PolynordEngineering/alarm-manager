"""Home Assistant entities for Alarm Manager."""

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval

from .alarm import Alarm
from .const import SIGNAL_ALARM_UPDATED


class AlarmEntity(SensorEntity):
    """Represent a Home Assistant alarm entity."""

    _attr_should_poll = False
    _attr_icon = "mdi:alarm-light"

    def __init__(
        self,
        hass: HomeAssistant,
        alarm: Alarm,
    ) -> None:
        """Initialize the alarm entity."""

        self.hass = hass
        self.alarm = alarm

        self._attr_name = alarm.name
        self._attr_unique_id = (
            f"alarm_manager_{alarm.alarm_id}"
        )

    @property
    def native_value(self) -> str:
        """Return the current alarm state."""

        return self.alarm.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return alarm attributes."""

        return {
            "alarm_id": self.alarm.alarm_id,
            "name": self.alarm.name,
            "entity_id": self.alarm.entity_id,
            "condition": self.alarm.condition,
            "threshold": self.alarm.threshold,
            "severity": self.alarm.severity,
            "delay": self.alarm.delay,
            "hysteresis": self.alarm.hysteresis,
            "current_value": self.alarm.last_value,
            "trigger_value": self.alarm.trigger_value,
            "activated_at": (
                self.alarm.activated_at.isoformat()
                if self.alarm.activated_at
                else None
            ),
            "acknowledged_at": (
                self.alarm.acknowledged_at.isoformat()
                if self.alarm.acknowledged_at
                else None
            ),
            "cleared_at": (
                self.alarm.cleared_at.isoformat()
                if self.alarm.cleared_at
                else None
            ),
            "duration": self.alarm.duration,
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ALARM_UPDATED,
                self._alarm_updated,
            )
        )

        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._update_duration,
                timedelta(seconds=1),
            )
        )

    @callback
    def _alarm_updated(
        self,
        alarm_id: str,
    ) -> None:
        """Handle an alarm update."""

        if alarm_id != self.alarm.alarm_id:
            return

        self.async_write_ha_state()

    @callback
    def _update_duration(self, now) -> None:
        """Update the alarm duration."""

        if not self.alarm.is_active:
            return

        self.async_write_ha_state()