"""Alarm Manager integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .alarm import Alarm
from .const import DOMAIN
from .entity_monitor import EntityMonitor
from .manager import AlarmManager
from .panel import (
    async_register_panel,
    async_unregister_panel,
)
from .services import (
    async_register_services,
    async_remove_services,
)


PLATFORMS = [
    Platform.SENSOR,
]


async def async_setup(
    hass: HomeAssistant,
    config: dict,
) -> bool:
    """Set up Alarm Manager."""

    async_register_services(
        hass
    )

    await async_register_panel(
        hass
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Alarm Manager from a config entry."""

    monitor = EntityMonitor(
        hass=hass,
        manager=None,
    )

    manager = AlarmManager(
        hass=hass,
    )

    monitor.manager = manager

    await manager.async_load()

    hass.data.setdefault(
        DOMAIN,
        {},
    )

    hass.data[
        DOMAIN
    ][entry.entry_id] = {
        "manager": manager,
        "monitor": monitor,
        "add_alarm_entity": None,
        "remove_alarm_entity": None,
    }

    async def alarm_created(
        alarm: Alarm,
    ) -> None:
        """Handle a newly created alarm."""

        await monitor.async_start_monitoring(
            alarm_id=alarm.alarm_id,
            entity_id=alarm.entity_id,
        )

        add_alarm_entity = hass.data[
            DOMAIN
        ][entry.entry_id].get(
            "add_alarm_entity"
        )

        if add_alarm_entity is not None:
            add_alarm_entity(
                alarm
            )

    async def alarm_updated(
        alarm: Alarm,
    ) -> None:
        """Handle an updated alarm."""

        # Stop the old listener first. This is important
        # if the monitored entity was changed during editing.
        monitor.stop_monitoring(
            alarm.alarm_id
        )

        await monitor.async_start_monitoring(
            alarm_id=alarm.alarm_id,
            entity_id=alarm.entity_id,
        )

    async def alarm_removed(
        alarm_id: str,
    ) -> None:
        """Handle a removed alarm."""

        monitor.stop_monitoring(
            alarm_id
        )

        remove_alarm_entity = hass.data[
            DOMAIN
        ][entry.entry_id].get(
            "remove_alarm_entity"
        )

        if remove_alarm_entity is not None:
            await remove_alarm_entity(
                alarm_id
            )

    manager._alarm_created_callback = (
        alarm_created
    )

    manager._alarm_updated_callback = (
        alarm_updated
    )

    manager._alarm_removed_callback = (
        alarm_removed
    )

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    for alarm in manager.alarms.values():
        await monitor.async_start_monitoring(
            alarm_id=alarm.alarm_id,
            entity_id=alarm.entity_id,
        )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload Alarm Manager."""

    unload_ok = (
        await hass.config_entries.async_unload_platforms(
            entry,
            PLATFORMS,
        )
    )

    data = hass.data.get(
        DOMAIN,
        {},
    ).pop(
        entry.entry_id,
        None,
    )

    if data is not None:
        data[
            "monitor"
        ].stop_all()

        data[
            "manager"
        ].stop_all_pending_tasks()

    if not hass.data.get(
        DOMAIN
    ):
        async_unregister_panel(
            hass
        )

        async_remove_services(
            hass
        )

    return unload_ok