"""Services for Alarm Manager."""

import uuid

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .alarm_config import AlarmConfig
from .const import (
    CONDITION_ABOVE,
    CONDITION_BELOW,
    CONDITION_EQUAL,
    CONDITION_NOT_EQUAL,
    CONDITION_OFF,
    CONDITION_ON,
    CONDITION_UNAVAILABLE,
    DOMAIN,
    SEVERITY_ALARM,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)
from .manager import AlarmManager


CONDITIONS = {
    CONDITION_ABOVE,
    CONDITION_BELOW,
    CONDITION_EQUAL,
    CONDITION_NOT_EQUAL,
    CONDITION_ON,
    CONDITION_OFF,
    CONDITION_UNAVAILABLE,
}

SEVERITIES = {
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SEVERITY_ALARM,
    SEVERITY_CRITICAL,
}


CREATE_ALARM_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("condition"): vol.In(
            CONDITIONS
        ),
        vol.Optional("threshold"): vol.Any(
            cv.string,
            vol.Coerce(float),
        ),
        vol.Optional(
            "severity",
            default=SEVERITY_WARNING,
        ): vol.In(
            SEVERITIES
        ),
        vol.Optional(
            "delay",
            default=0,
        ): vol.All(
            vol.Coerce(int),
            vol.Range(min=0),
        ),
        vol.Optional(
            "hysteresis",
            default=0.0,
        ): vol.Coerce(float),
    }
)


ACKNOWLEDGE_ALARM_SCHEMA = vol.Schema(
    {
        vol.Required(
            "alarm_id"
        ): cv.string,
    }
)


REMOVE_ALARM_SCHEMA = vol.Schema(
    {
        vol.Required(
            "alarm_id"
        ): cv.string,
    }
)


def _get_manager(
    hass: HomeAssistant,
) -> AlarmManager | None:
    """Return the active Alarm Manager."""

    domain_data = hass.data.get(
        DOMAIN
    )

    if not domain_data:
        return None

    for entry_data in domain_data.values():
        manager = entry_data.get(
            "manager"
        )

        if isinstance(
            manager,
            AlarmManager,
        ):
            return manager

    return None


async def _handle_create_alarm(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Handle create alarm."""

    manager = _get_manager(hass)

    if manager is None:
        raise RuntimeError(
            "Alarm Manager is not loaded."
        )

    config = AlarmConfig(
        alarm_id=str(
            uuid.uuid4()
        ),
        name=call.data["name"],
        entity_id=call.data[
            "entity_id"
        ],
        condition=call.data[
            "condition"
        ],
        threshold=call.data.get(
            "threshold"
        ),
        severity=call.data[
            "severity"
        ],
        delay=call.data[
            "delay"
        ],
        hysteresis=call.data[
            "hysteresis"
        ],
    )

    await manager.async_add_alarm(
        config
    )


async def _handle_acknowledge_alarm(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Handle acknowledge alarm."""

    manager = _get_manager(hass)

    if manager is None:
        raise RuntimeError(
            "Alarm Manager is not loaded."
        )

    alarm_id = call.data[
        "alarm_id"
    ]

    success = (
        await manager.async_acknowledge_alarm(
            alarm_id
        )
    )

    if not success:
        raise ValueError(
            f"Alarm '{alarm_id}' was not found."
        )


async def _handle_acknowledge_all(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Handle acknowledge all alarms."""

    manager = _get_manager(hass)

    if manager is None:
        raise RuntimeError(
            "Alarm Manager is not loaded."
        )

    await manager.async_acknowledge_all()


async def _handle_clear_history(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Handle clear history."""

    manager = _get_manager(hass)

    if manager is None:
        raise RuntimeError(
            "Alarm Manager is not loaded."
        )

    await manager.async_clear_history()


async def _handle_remove_alarm(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Handle remove alarm."""

    manager = _get_manager(hass)

    if manager is None:
        raise RuntimeError(
            "Alarm Manager is not loaded."
        )

    alarm_id = call.data[
        "alarm_id"
    ]

    success = (
        await manager.async_remove_alarm(
            alarm_id
        )
    )

    if not success:
        raise ValueError(
            f"Alarm '{alarm_id}' was not found."
        )


def async_register_services(
    hass: HomeAssistant,
) -> None:
    """Register Alarm Manager services."""

    async def create_alarm(
        call: ServiceCall,
    ) -> None:
        """Create an alarm."""

        await _handle_create_alarm(
            hass,
            call,
        )

    async def acknowledge_alarm(
        call: ServiceCall,
    ) -> None:
        """Acknowledge an alarm."""

        await _handle_acknowledge_alarm(
            hass,
            call,
        )

    async def acknowledge_all(
        call: ServiceCall,
    ) -> None:
        """Acknowledge all alarms."""

        await _handle_acknowledge_all(
            hass,
            call,
        )

    async def clear_history(
        call: ServiceCall,
    ) -> None:
        """Clear history."""

        await _handle_clear_history(
            hass,
            call,
        )

    async def remove_alarm(
        call: ServiceCall,
    ) -> None:
        """Remove an alarm."""

        await _handle_remove_alarm(
            hass,
            call,
        )

    hass.services.async_register(
        DOMAIN,
        "create_alarm",
        create_alarm,
        schema=CREATE_ALARM_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        "acknowledge_alarm",
        acknowledge_alarm,
        schema=ACKNOWLEDGE_ALARM_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        "acknowledge_all",
        acknowledge_all,
    )

    hass.services.async_register(
        DOMAIN,
        "clear_history",
        clear_history,
    )

    hass.services.async_register(
        DOMAIN,
        "remove_alarm",
        remove_alarm,
        schema=REMOVE_ALARM_SCHEMA,
    )


def async_remove_services(
    hass: HomeAssistant,
) -> None:
    """Remove Alarm Manager services."""

    hass.services.async_remove(
        DOMAIN,
        "create_alarm",
    )

    hass.services.async_remove(
        DOMAIN,
        "acknowledge_alarm",
    )

    hass.services.async_remove(
        DOMAIN,
        "acknowledge_all",
    )

    hass.services.async_remove(
        DOMAIN,
        "clear_history",
    )

    hass.services.async_remove(
        DOMAIN,
        "remove_alarm",
    )