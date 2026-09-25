"""Sensor platform for Alarm Manager."""

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .alarm import Alarm
from .alarm_entity import AlarmEntity
from .const import DOMAIN, SIGNAL_ALARM_UPDATED


class AlarmHistoryEntity(SensorEntity):
    """Represent Alarm Manager history."""

    _attr_should_poll = False
    _attr_name = "Alarm History"
    _attr_icon = "mdi:history"
    _attr_unique_id = "alarm_manager_history"

    def __init__(
        self,
        hass: HomeAssistant,
        manager,
    ) -> None:
        """Initialize the history entity."""

        self.hass = hass
        self.manager = manager

    @property
    def native_value(self) -> int:
        """Return the number of historical alarms."""

        return len(self.manager.history)

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, Any]:
        """Return alarm history."""

        return {
            "history": list(self.manager.history),
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity being added."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ALARM_UPDATED,
                self._alarm_updated,
            )
        )

        # Make sure the entity immediately reflects the current
        # manager state after being added to Home Assistant.
        self.async_write_ha_state()

    @callback
    def _alarm_updated(
        self,
        alarm_id: str,
    ) -> None:
        """Handle an alarm or history update."""

        # The dispatcher is used by the manager for both alarm
        # lifecycle changes and history changes. The history sensor
        # therefore needs to publish a new HA state immediately.
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable,
) -> None:
    """Set up Alarm Manager sensor entities."""

    data = hass.data[
        DOMAIN
    ][entry.entry_id]

    manager = data["manager"]

    # ---------------------------------------------------------
    # Clean up stale Alarm Manager entities from the entity
    # registry.
    #
    # Alarm entities have unique IDs such as:
    #
    # alarm_manager_<alarm_id>
    #
    # When an alarm was previously deleted, the old entity
    # could remain in Home Assistant's entity registry even
    # though the entity itself was removed from the state
    # machine.
    #
    # Keep:
    #   - currently existing alarm entities
    #   - Alarm History
    #
    # Remove:
    #   - registry entries for alarms that no longer exist
    # ---------------------------------------------------------

    registry = er.async_get(hass)

    active_alarm_unique_ids = {
        f"alarm_manager_{alarm_id}"
        for alarm_id in manager.alarms
    }

    for registry_entry in er.async_entries_for_config_entry(
        registry,
        entry.entry_id,
    ):
        if registry_entry.platform != DOMAIN:
            continue

        if registry_entry.unique_id == "alarm_manager_history":
            continue

        if not registry_entry.unique_id.startswith(
            "alarm_manager_"
        ):
            continue

        if registry_entry.unique_id not in active_alarm_unique_ids:
            registry.async_remove(
                registry_entry.entity_id
            )

    # ---------------------------------------------------------
    # Create entities for alarms currently stored by the
    # Alarm Manager.
    # ---------------------------------------------------------

    entities: dict[
        str,
        AlarmEntity,
    ] = {}

    existing_entities = [
        AlarmEntity(
            hass=hass,
            alarm=alarm,
        )
        for alarm in manager.alarms.values()
    ]

    for entity in existing_entities:
        entities[
            entity.alarm.alarm_id
        ] = entity

    # ---------------------------------------------------------
    # History entity
    # ---------------------------------------------------------

    history_entity = AlarmHistoryEntity(
        hass=hass,
        manager=manager,
    )

    async_add_entities(
        [
            *existing_entities,
            history_entity,
        ],
        update_before_add=True,
    )

    # ---------------------------------------------------------
    # Add newly created alarm entities
    # ---------------------------------------------------------

    def add_alarm_entity(
        alarm: Alarm,
    ) -> None:
        """Add a newly created alarm entity."""

        if alarm.alarm_id in entities:
            return

        entity = AlarmEntity(
            hass=hass,
            alarm=alarm,
        )

        entities[
            alarm.alarm_id
        ] = entity

        async_add_entities(
            [entity],
            update_before_add=True,
        )

    # ---------------------------------------------------------
    # Remove alarm entities
    # ---------------------------------------------------------

    async def remove_alarm_entity(
        alarm_id: str,
    ) -> None:
        """Remove an alarm entity."""

        entity = entities.pop(
            alarm_id,
            None,
        )

        if entity is None:
            return

        # Save the entity_id before removing the entity.
        entity_id = entity.entity_id

        # Remove the entity from Home Assistant's state machine.
        await entity.async_remove(
            force_remove=True,
        )

        # force_remove removes the entity itself, but the
        # entity registry entry can remain. Explicitly remove
        # that registry entry as well.
        if entity_id is not None:
            registry = er.async_get(hass)
            registry.async_remove(
                entity_id
            )

    data[
        "add_alarm_entity"
    ] = add_alarm_entity

    data[
        "remove_alarm_entity"
    ] = remove_alarm_entity