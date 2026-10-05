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
    CONDITION_TYPE_ENTITY,
    CONDITION_TYPE_TIME,
    CONDITION_AFTER,
    CONDITION_BEFORE,
    CONDITION_BETWEEN,
    LOGIC_ALL,
    LOGIC_ANY,
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


def _normalize_condition(value: str) -> str:
    """Normalize UI/user condition labels to the internal condition keys."""
    text = str(value).strip().lower()
    aliases = {
        "is on": CONDITION_ON,
        "on": CONDITION_ON,
        "is off": CONDITION_OFF,
        "off": CONDITION_OFF,
        "is above": CONDITION_ABOVE,
        "above": CONDITION_ABOVE,
        "is below": CONDITION_BELOW,
        "below": CONDITION_BELOW,
        "equals": CONDITION_EQUAL,
        "equal": CONDITION_EQUAL,
        "is equal to": CONDITION_EQUAL,
        "is not equal to": CONDITION_NOT_EQUAL,
        "not equal": CONDITION_NOT_EQUAL,
        "not_equal": CONDITION_NOT_EQUAL,
        "is unavailable": CONDITION_UNAVAILABLE,
        "unavailable": CONDITION_UNAVAILABLE,
    }
    normalized = aliases.get(text, text)
    if normalized not in CONDITIONS:
        raise vol.Invalid(f"Unknown alarm condition: {value}")
    return normalized


ENTITY_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required("type", default=CONDITION_TYPE_ENTITY): vol.In(
            {CONDITION_TYPE_ENTITY}
        ),
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("condition"): vol.All(cv.string, _normalize_condition),
        vol.Optional("threshold"): vol.Any(
            cv.string,
            vol.Coerce(float),
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

TIME_CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required("type", default=CONDITION_TYPE_TIME): vol.In(
            {CONDITION_TYPE_TIME}
        ),
        vol.Required("condition"): vol.In(
            {CONDITION_AFTER, CONDITION_BEFORE, CONDITION_BETWEEN}
        ),
        vol.Required("start_time"): cv.string,
        vol.Optional("end_time"): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

CONDITION_SCHEMA = vol.Any(
    ENTITY_CONDITION_SCHEMA,
    TIME_CONDITION_SCHEMA,
)

CONDITIONS_LIST_SCHEMA = vol.All(
    cv.ensure_list,
    [CONDITION_SCHEMA],
    vol.Length(min=0),
)

CREATE_ALARM_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        # Legacy single-condition fields remain supported for automations/services.
        vol.Optional("entity_id", default=""): cv.string,
        vol.Optional("condition", default="above"): vol.All(cv.string, _normalize_condition),
        vol.Optional("threshold"): vol.Any(
            cv.string,
            vol.Coerce(float),
        ),
        vol.Optional(
            "conditions",
        ): CONDITIONS_LIST_SCHEMA,
        vol.Optional(
            "logic",
            default=LOGIC_ALL,
        ): vol.In({LOGIC_ALL, LOGIC_ANY}),
        vol.Optional(
            "severity",
            default=SEVERITY_WARNING,
        ): vol.In(SEVERITIES),
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

UPDATE_ALARM_SCHEMA = vol.Schema(
    {
        vol.Required("alarm_id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Optional("entity_id", default=""): cv.string,
        vol.Optional("condition", default="above"): vol.All(cv.string, _normalize_condition),
        vol.Optional("threshold"): vol.Any(
            cv.string,
            vol.Coerce(float),
        ),
        vol.Optional("conditions"): CONDITIONS_LIST_SCHEMA,
        vol.Optional("logic", default=LOGIC_ALL): vol.In({LOGIC_ALL, LOGIC_ANY}),
        vol.Optional("severity", default=SEVERITY_WARNING): vol.In(SEVERITIES),
        vol.Optional("delay", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("hysteresis", default=0.0): vol.Coerce(float),
    }
)


TRIGGER_ALARM_SCHEMA = vol.Schema(
    {
        vol.Required("alarm_id"): cv.string,
    }
)


NOTIFICATION_TARGET_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("service"): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

SET_NOTIFICATION_TARGETS_SCHEMA = vol.Schema(
    {
        vol.Required("targets"): vol.All(cv.ensure_list, [NOTIFICATION_TARGET_SCHEMA]),
        vol.Required("routing"): dict,
    }
)


ACKNOWLEDGE_ALARM_SCHEMA = vol.Schema(
    {
        vol.Required(
            "alarm_id"
        ): cv.string,
    }
)


DEFAULT_NOTIFICATION_SCHEMA = vol.Schema(
    {
        vol.Required("notification_service"): cv.string,
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

    conditions = call.data.get("conditions") or []
    first_entity = next(
        (item for item in conditions if item.get("type") == CONDITION_TYPE_ENTITY),
        None,
    )
    config = AlarmConfig(
        alarm_id=str(uuid.uuid4()),
        name=call.data["name"],
        entity_id=(
            call.data.get("entity_id", "")
            or (first_entity.get("entity_id", "") if first_entity else "")
        ),
        condition=(
            first_entity.get("condition", "above")
            if first_entity
            else call.data.get("condition", "above")
        ),
        threshold=(
            first_entity.get("threshold")
            if first_entity
            else call.data.get("threshold")
        ),
        severity=call.data["severity"],
        delay=call.data["delay"],
        hysteresis=call.data["hysteresis"],
        conditions=conditions,
        logic=call.data.get("logic", LOGIC_ALL),
    )

    await manager.async_add_alarm(
        config
    )


async def _handle_update_alarm(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Handle update alarm."""

    manager = _get_manager(hass)

    if manager is None:
        raise RuntimeError("Alarm Manager is not loaded.")

    conditions = call.data.get("conditions") or []
    first_entity = next(
        (item for item in conditions if item.get("type") == CONDITION_TYPE_ENTITY),
        None,
    )

    config = AlarmConfig(
        alarm_id=call.data["alarm_id"],
        name=call.data["name"],
        entity_id=(
            call.data.get("entity_id", "")
            or (first_entity.get("entity_id", "") if first_entity else "")
        ),
        condition=(first_entity.get("condition", "above") if first_entity else call.data.get("condition", "above")),
        threshold=(first_entity.get("threshold") if first_entity else call.data.get("threshold")),
        severity=call.data["severity"],
        delay=call.data["delay"],
        hysteresis=call.data["hysteresis"],
        conditions=conditions,
        logic=call.data.get("logic", LOGIC_ALL),
    )

    updated = await manager.async_update_alarm(config)
    if updated is None:
        raise ValueError(f"Alarm '{config.alarm_id}' was not found.")


async def _handle_trigger_alarm(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Manually trigger an alarm."""
    manager = _get_manager(hass)
    if manager is None:
        return
    await manager.async_trigger_alarm(call.data["alarm_id"])


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
            alarm_id,
            user_id=call.context.user_id,
        )
    )

    if not success:
        raise ValueError(
            f"Alarm '{alarm_id}' was not found."
        )


async def _handle_clear_alarm(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Handle clearing an inactive alarm without acknowledging it."""

    manager = _get_manager(hass)

    if manager is None:
        raise RuntimeError(
            "Alarm Manager is not loaded."
        )

    alarm_id = call.data["alarm_id"]

    success = await manager.async_clear_alarm(alarm_id)

    if not success:
        raise ValueError(
            f"Alarm '{alarm_id}' is not inactive or was not found."
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

    await manager.async_acknowledge_all(
        user_id=call.context.user_id,
    )


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


async def _handle_set_default_notification(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Set the legacy/default notification service."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise RuntimeError("Alarm Manager is not configured.")
    entry = entries[0]
    service = str(call.data.get("notification_service", "disabled")).strip() or "disabled"
    options = dict(entry.options)
    options["notification_service"] = service
    hass.config_entries.async_update_entry(entry, options=options)
    # Options are read directly by Alarm Manager; no config-entry reload is needed.


async def _handle_set_notification_targets(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Replace notification targets and severity routing."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise RuntimeError("Alarm Manager is not configured.")
    entry = entries[0]
    targets = [
        {"name": str(t["name"]).strip(), "service": str(t["service"]).strip()}
        for t in call.data["targets"]
        if str(t["name"]).strip() and str(t["service"]).strip()
    ]
    valid_names = {t["name"] for t in targets}
    raw_routing = call.data.get("routing", {})
    routing = {}
    for severity in (SEVERITY_CRITICAL, SEVERITY_ALARM, SEVERITY_WARNING, SEVERITY_INFO):
        names = raw_routing.get(severity, []) if isinstance(raw_routing, dict) else []
        routing[severity] = [str(name) for name in names if str(name) in valid_names]
    options = dict(entry.options)
    options["notification_targets"] = targets
    options["notification_routing"] = routing
    hass.config_entries.async_update_entry(entry, options=options)
    # Options are read directly by Alarm Manager; no config-entry reload is needed.


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

    async def update_alarm(
        call: ServiceCall,
    ) -> None:
        """Update an alarm."""

        await _handle_update_alarm(
            hass,
            call,
        )

    async def trigger_alarm(
        call: ServiceCall,
    ) -> None:
        """Trigger an alarm manually."""
        await _handle_trigger_alarm(hass, call)

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
        "update_alarm",
        update_alarm,
        schema=UPDATE_ALARM_SCHEMA,
    )

    async def set_default_notification(call: ServiceCall) -> None:
        await _handle_set_default_notification(hass, call)

    hass.services.async_register(
        DOMAIN,
        "set_default_notification",
        set_default_notification,
        schema=DEFAULT_NOTIFICATION_SCHEMA,
    )

    async def set_notification_targets(call: ServiceCall) -> None:
        await _handle_set_notification_targets(hass, call)

    hass.services.async_register(
        DOMAIN,
        "set_notification_targets",
        set_notification_targets,
        schema=SET_NOTIFICATION_TARGETS_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        "trigger_alarm",
        trigger_alarm,
        schema=TRIGGER_ALARM_SCHEMA,
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

    async def clear_alarm(call: ServiceCall) -> None:
        await _handle_clear_alarm(hass, call)

    hass.services.async_register(
        DOMAIN,
        "clear_alarm",
        clear_alarm,
        schema=ACKNOWLEDGE_ALARM_SCHEMA,
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
        "update_alarm",
    )

    hass.services.async_remove(
        DOMAIN,
        "set_default_notification",
    )

    hass.services.async_remove(
        DOMAIN,
        "set_notification_targets",
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
        "clear_alarm",
    )

    hass.services.async_remove(
        DOMAIN,
        "clear_history",
    )

    hass.services.async_remove(
        DOMAIN,
        "remove_alarm",
    )