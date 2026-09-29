"""Alarm Manager integration."""

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

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

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(
    hass: HomeAssistant,
    config: dict,
) -> bool:
    """Set up Alarm Manager."""

    async_register_services(
        hass
    )

    # Panels are registered with the config entry lifecycle below so they
    # survive config-entry reloads (for example when notification settings
    # are saved from the Alarm Manager UI).
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

    # Register the sidebar panels for this active config entry. Keeping this
    # in setup_entry means a config-entry reload recreates the panels instead
    # of leaving the user on the Home Assistant dashboard.
    await async_register_panel(hass)

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
            entity_ids=alarm.entity_ids,
            has_time_conditions=alarm.has_time_conditions,
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
            entity_ids=alarm.entity_ids,
            has_time_conditions=alarm.has_time_conditions,
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
            entity_ids=alarm.entity_ids,
            has_time_conditions=alarm.has_time_conditions,
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