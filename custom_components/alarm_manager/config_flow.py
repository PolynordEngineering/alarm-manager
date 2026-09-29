"""Config flow for Alarm Manager."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .alarm_config import AlarmConfig
from .const import (
    CONDITION_ABOVE,
    CONDITION_BELOW,
    CONDITION_EQUAL,
    CONDITION_NOT_EQUAL,
    CONDITION_OFF,
    CONDITION_ON,
    CONDITION_UNAVAILABLE,
    CONF_CONDITION,
    CONF_DELAY,
    CONF_ENTITY_ID,
    CONF_HYSTERESIS,
    CONF_SEVERITY,
    CONF_THRESHOLD,
    CONF_LOGIC,
    CONF_CONDITION_TYPE,
    CONF_START_TIME,
    CONF_END_TIME,
    CONDITION_AFTER,
    CONDITION_BEFORE,
    CONDITION_BETWEEN,
    CONDITION_TYPE_ENTITY,
    CONDITION_TYPE_TIME,
    DOMAIN,
    SEVERITY_ALARM,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    LOGIC_ALL,
    LOGIC_ANY,
)


CONDITIONS = [
    CONDITION_ABOVE,
    CONDITION_BELOW,
    CONDITION_EQUAL,
    CONDITION_NOT_EQUAL,
    CONDITION_ON,
    CONDITION_OFF,
    CONDITION_UNAVAILABLE,
]


SEVERITIES = [
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SEVERITY_ALARM,
    SEVERITY_CRITICAL,
]


class AlarmManagerConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle the initial configuration."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Create the integration entry."""

        if user_input is not None:
            return self.async_create_entry(
                title="Alarm Manager",
                data={},
            )

        return self.async_show_form(
            step_id="user",
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""

        return AlarmManagerOptionsFlow()


class AlarmManagerOptionsFlow(
    OptionsFlow
):
    """Handle Alarm Manager options."""

    def __init__(self) -> None:
        """Initialize the options flow."""

        self._selected_alarm_id: str | None = None
        self._selected_notification_target: str | None = None
        self._pending_alarm: dict[str, Any] = {}
        self._pending_conditions: list[dict[str, Any]] = []

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the options menu."""

        return self.async_show_menu(
            step_id="init",
            menu_options={
                "add_alarm": "Add Alarm",
                "edit_alarm": "Edit Alarm",
                "delete_alarm": "Delete Alarm",
                "notifications": "Notifications",
            },
        )

    def _show_main_menu(self) -> ConfigFlowResult:
        """Return to the main Alarm Manager settings menu."""

        return self.async_show_menu(
            step_id="init",
            menu_options={
                "add_alarm": "Add Alarm",
                "edit_alarm": "Edit Alarm",
                "delete_alarm": "Delete Alarm",
                "notifications": "Notifications",
            },
        )

    def _show_notifications_menu(self) -> ConfigFlowResult:
        """Return to the notification settings menu."""

        return self.async_show_menu(
            step_id="notifications",
            menu_options={
                "default_notification": "Default Notification Service",
                "add_notification_target": "Add Notification Target",
                "edit_notification_target": "Edit Notification Target",
                "delete_notification_target": "Delete Notification Target",
                "notification_routing": "Severity Routing",
            },
        )

    async def async_step_add_alarm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Start a new alarm and collect its general settings."""
        if user_input is not None:
            self._pending_alarm = dict(user_input)
            self._pending_conditions = []
            return self._show_condition_menu()

        return self.async_show_form(
            step_id="add_alarm",
            data_schema=self._alarm_general_schema(),
        )

    def _show_condition_menu(self) -> ConfigFlowResult:
        """Show the condition builder menu."""
        options = {"add_condition": "Add Condition"}
        if self._pending_conditions:
            options["edit_condition"] = "Edit Condition"
            options["remove_condition"] = "Remove Condition"
        options["finish_alarm"] = "Save Alarm"
        return self.async_show_menu(
            step_id="condition_menu",
            menu_options=options,
            description_placeholders={"summary": self._condition_summary()},
        )

    async def async_step_condition_menu(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the condition builder menu."""
        return self._show_condition_menu()

    async def async_step_add_condition(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Select the type of condition to add."""
        if user_input is not None:
            if user_input[CONF_CONDITION_TYPE] == CONDITION_TYPE_TIME:
                return await self.async_step_add_time_condition()
            return await self.async_step_add_entity_condition()

        schema = vol.Schema({
            vol.Required(CONF_CONDITION_TYPE, default=CONDITION_TYPE_ENTITY): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=CONDITION_TYPE_ENTITY, label="Entity"),
                        selector.SelectOptionDict(value=CONDITION_TYPE_TIME, label="Time"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        })
        return self.async_show_form(step_id="add_condition", data_schema=schema)

    async def async_step_add_entity_condition(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Add an entity-based condition."""
        if user_input is not None:
            self._pending_conditions.append({
                "type": CONDITION_TYPE_ENTITY,
                "entity_id": user_input[CONF_ENTITY_ID],
                "condition": user_input[CONF_CONDITION],
                "threshold": user_input.get(CONF_THRESHOLD),
            })
            return self._show_condition_menu()

        schema = vol.Schema({
            vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(multiple=False)
            ),
            vol.Required(CONF_CONDITION, default=CONDITION_ABOVE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=CONDITION_ABOVE, label="Above"),
                        selector.SelectOptionDict(value=CONDITION_BELOW, label="Below"),
                        selector.SelectOptionDict(value=CONDITION_EQUAL, label="Equal"),
                        selector.SelectOptionDict(value=CONDITION_NOT_EQUAL, label="Not equal"),
                        selector.SelectOptionDict(value=CONDITION_ON, label="On"),
                        selector.SelectOptionDict(value=CONDITION_OFF, label="Off"),
                        selector.SelectOptionDict(value=CONDITION_UNAVAILABLE, label="Unavailable"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_THRESHOLD, default=0.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-1000000, max=1000000, step=0.1, mode=selector.NumberSelectorMode.BOX)
            ),
        })
        return self.async_show_form(step_id="add_entity_condition", data_schema=schema)

    async def async_step_add_time_condition(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Add a time-based condition."""
        if user_input is not None:
            condition = user_input[CONF_CONDITION]
            item = {
                "type": CONDITION_TYPE_TIME,
                "condition": condition,
                "start_time": str(user_input[CONF_START_TIME]),
            }
            if condition == CONDITION_BETWEEN:
                item["end_time"] = str(user_input[CONF_END_TIME])
            self._pending_conditions.append(item)
            return self._show_condition_menu()

        schema = vol.Schema({
            vol.Required(CONF_CONDITION, default=CONDITION_AFTER): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=CONDITION_AFTER, label="After"),
                        selector.SelectOptionDict(value=CONDITION_BEFORE, label="Before"),
                        selector.SelectOptionDict(value=CONDITION_BETWEEN, label="Between"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_START_TIME): selector.TimeSelector(),
            vol.Optional(CONF_END_TIME, default="00:00:00"): selector.TimeSelector(),
        })
        return self.async_show_form(step_id="add_time_condition", data_schema=schema)

    async def async_step_edit_condition(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Select and edit an existing condition."""
        if not self._pending_conditions:
            return self._show_condition_menu()
        if user_input is not None:
            index = int(user_input["condition_index"])
            condition = self._pending_conditions[index]
            self._editing_condition_index = index
            if condition.get("type") == CONDITION_TYPE_TIME:
                return await self.async_step_edit_time_condition()
            return await self.async_step_edit_entity_condition()
        options = [
            selector.SelectOptionDict(value=str(index), label=self._condition_display(item, index))
            for index, item in enumerate(self._pending_conditions)
        ]
        return self.async_show_form(
            step_id="edit_condition",
            data_schema=vol.Schema({
                vol.Required("condition_index"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
                )
            }),
        )

    async def async_step_edit_entity_condition(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Edit an entity condition."""
        index = getattr(self, "_editing_condition_index", None)
        condition = self._pending_conditions[index] if index is not None else None
        if condition is None:
            return self._show_condition_menu()
        if user_input is not None:
            self._pending_conditions[index] = {
                "type": CONDITION_TYPE_ENTITY,
                "entity_id": user_input[CONF_ENTITY_ID],
                "condition": user_input[CONF_CONDITION],
                "threshold": user_input.get(CONF_THRESHOLD),
            }
            return self._show_condition_menu()
        return self.async_show_form(
            step_id="edit_entity_condition",
            data_schema=vol.Schema({
                vol.Required(CONF_ENTITY_ID, default=condition.get("entity_id", "")): selector.EntitySelector(selector.EntitySelectorConfig(multiple=False)),
                vol.Required(CONF_CONDITION, default=condition.get("condition", CONDITION_ABOVE)): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value=x, label=x.replace("_", " ").title()) for x in CONDITIONS], mode=selector.SelectSelectorMode.DROPDOWN)),
                vol.Optional(CONF_THRESHOLD, default=condition.get("threshold", 0.0)): selector.NumberSelector(selector.NumberSelectorConfig(min=-1000000, max=1000000, step=0.1, mode=selector.NumberSelectorMode.BOX)),
            }),
        )

    async def async_step_edit_time_condition(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Edit a time condition."""
        index = getattr(self, "_editing_condition_index", None)
        condition = self._pending_conditions[index] if index is not None else None
        if condition is None:
            return self._show_condition_menu()
        if user_input is not None:
            item = {
                "type": CONDITION_TYPE_TIME,
                "condition": user_input[CONF_CONDITION],
                "start_time": str(user_input[CONF_START_TIME]),
            }
            if user_input[CONF_CONDITION] == CONDITION_BETWEEN:
                item["end_time"] = str(user_input[CONF_END_TIME])
            self._pending_conditions[index] = item
            return self._show_condition_menu()
        return self.async_show_form(
            step_id="edit_time_condition",
            data_schema=vol.Schema({
                vol.Required(CONF_CONDITION, default=condition.get("condition", CONDITION_AFTER)): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value=x, label=x.title()) for x in [CONDITION_AFTER, CONDITION_BEFORE, CONDITION_BETWEEN]], mode=selector.SelectSelectorMode.DROPDOWN)),
                vol.Required(CONF_START_TIME, default=condition.get("start_time", "21:00:00")): selector.TimeSelector(),
                vol.Optional(CONF_END_TIME, default=condition.get("end_time", "06:00:00")): selector.TimeSelector(),
            }),
        )

    async def async_step_remove_condition(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Remove a condition."""
        if not self._pending_conditions:
            return self._show_condition_menu()
        if user_input is not None:
            index = int(user_input["condition_index"])
            self._pending_conditions.pop(index)
            return self._show_condition_menu()
        options = [
            selector.SelectOptionDict(value=str(index), label=self._condition_display(item, index))
            for index, item in enumerate(self._pending_conditions)
        ]
        return self.async_show_form(
            step_id="remove_condition",
            data_schema=vol.Schema({
                vol.Required("condition_index"): selector.SelectSelector(selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN))
            }),
        )

    async def async_step_finish_alarm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Create or update the alarm from the condition builder."""
        manager = self._get_manager()
        if manager is None:
            return self.async_abort(reason="manager_not_loaded")
        first_entity = next(
            (c for c in self._pending_conditions if c.get("type") == CONDITION_TYPE_ENTITY),
            None,
        )
        config = AlarmConfig(
            alarm_id=self._selected_alarm_id or str(uuid.uuid4()),
            name=self._pending_alarm[CONF_NAME],
            entity_id=first_entity.get("entity_id", "") if first_entity else "",
            condition=first_entity.get("condition", CONDITION_ABOVE) if first_entity else CONDITION_AFTER,
            threshold=first_entity.get("threshold") if first_entity else None,
            severity=self._pending_alarm[CONF_SEVERITY],
            delay=self._pending_alarm[CONF_DELAY],
            hysteresis=self._pending_alarm[CONF_HYSTERESIS],
            conditions=list(self._pending_conditions),
            logic=self._pending_alarm.get(CONF_LOGIC, LOGIC_ALL),
        )
        if self._selected_alarm_id:
            await manager.async_update_alarm(config)
        else:
            await manager.async_add_alarm(config)

        self._selected_alarm_id = None
        self._pending_alarm = {}
        self._pending_conditions = []
        return self._show_main_menu()

    def _condition_display(self, item: dict[str, Any], index: int) -> str:
        """Return a readable condition label."""
        if item.get("type") == CONDITION_TYPE_TIME:
            text = f"Time {item.get('condition', '')} {item.get('start_time', '')}"
            if item.get("condition") == CONDITION_BETWEEN:
                text += f" – {item.get('end_time', '')}"
        else:
            text = f"{item.get('entity_id', 'Entity')} {item.get('condition', '')}"
            if item.get("condition") in {CONDITION_ABOVE, CONDITION_BELOW, CONDITION_EQUAL, CONDITION_NOT_EQUAL}:
                text += f" {item.get('threshold', '')}"
        return f"{index + 1}. {text}"

    def _condition_summary(self) -> str:
        """Return a compact condition summary."""
        if not self._pending_conditions:
            return "No conditions added yet."
        lines = [f"Logic: {self._pending_alarm.get(CONF_LOGIC, LOGIC_ALL).upper()}"]
        for index, item in enumerate(self._pending_conditions, 1):
            if item.get("type") == CONDITION_TYPE_TIME:
                text = f"{item.get('condition')} {item.get('start_time')}"
                if item.get("end_time"):
                    text += f"–{item['end_time']}"
            else:
                text = f"{item.get('entity_id')} {item.get('condition')} {item.get('threshold', '')}"
            lines.append(f"{index}. {text}")
        return "\n".join(lines)

    def _alarm_general_schema(self) -> vol.Schema:
        """Build general alarm settings schema."""
        return vol.Schema({
            vol.Required(CONF_NAME, default="New Alarm"): selector.TextSelector(selector.TextSelectorConfig()),
            vol.Required(CONF_SEVERITY, default=SEVERITY_WARNING): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=SEVERITY_INFO, label="Info"),
                        selector.SelectOptionDict(value=SEVERITY_WARNING, label="Warning"),
                        selector.SelectOptionDict(value=SEVERITY_ALARM, label="Alarm"),
                        selector.SelectOptionDict(value=SEVERITY_CRITICAL, label="Critical"),
                    ], mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_LOGIC, default=LOGIC_ALL): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=LOGIC_ALL, label="ALL conditions must be true"),
                        selector.SelectOptionDict(value=LOGIC_ANY, label="ANY condition may be true"),
                    ], mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_DELAY, default=0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=3600, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
            ),
            vol.Required(CONF_HYSTERESIS, default=0.0): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=1000000, step=0.1, mode=selector.NumberSelectorMode.BOX)
            ),
        })

    async def async_step_edit_alarm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Select an alarm to edit."""

        manager = self._get_manager()

        if manager is None:
            return self.async_abort(
                reason="manager_not_loaded"
            )

        if not manager.alarms:
            return self.async_abort(
                reason="no_alarms"
            )

        alarm_options = {
            alarm_id: alarm.name
            for alarm_id, alarm in manager.alarms.items()
        }

        if user_input is not None:
            self._selected_alarm_id = user_input[
                "alarm_id"
            ]

            return await self.async_step_edit_details()

        schema = vol.Schema(
            {
                vol.Required(
                    "alarm_id"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=alarm_id,
                                label=name,
                            )
                            for alarm_id, name
                            in alarm_options.items()
                        ],
                        mode=(
                            selector.SelectSelectorMode.DROPDOWN
                        ),
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="edit_alarm",
            data_schema=schema,
        )

    async def async_step_delete_alarm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Select an alarm to delete."""

        manager = self._get_manager()

        if manager is None:
            return self.async_abort(
                reason="manager_not_loaded"
            )

        if not manager.alarms:
            return self.async_abort(
                reason="no_alarms"
            )

        alarm_options = {
            alarm_id: alarm.name
            for alarm_id, alarm in manager.alarms.items()
        }

        if user_input is not None:
            self._selected_alarm_id = user_input[
                "alarm_id"
            ]

            return await self.async_step_confirm_delete()

        schema = vol.Schema(
            {
                vol.Required(
                    "alarm_id"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=alarm_id,
                                label=name,
                            )
                            for alarm_id, name
                            in alarm_options.items()
                        ],
                        mode=(
                            selector.SelectSelectorMode.DROPDOWN
                        ),
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="delete_alarm",
            data_schema=schema,
        )

    async def async_step_confirm_delete(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Confirm deletion of an alarm."""

        manager = self._get_manager()

        if manager is None:
            return self.async_abort(
                reason="manager_not_loaded"
            )

        alarm_id = self._selected_alarm_id

        if alarm_id is None:
            return self.async_abort(
                reason="alarm_not_selected"
            )

        alarm = manager.get_alarm(
            alarm_id
        )

        if alarm is None:
            return self.async_abort(
                reason="alarm_not_found"
            )

        if user_input is not None:
            if not user_input.get("confirm"):
                return self.async_abort(
                    reason="delete_cancelled"
                )

            removed = await manager.async_remove_alarm(
                alarm_id
            )

            if not removed:
                return self.async_abort(
                    reason="alarm_not_found"
                )

            self._selected_alarm_id = None

            return self._show_main_menu()

        schema = vol.Schema(
            {
                vol.Required(
                    "confirm",
                    default=False,
                ): selector.BooleanSelector(
                    selector.BooleanSelectorConfig()
                )
            }
        )

        return self.async_show_form(
            step_id="confirm_delete",
            data_schema=schema,
        )

    async def async_step_notifications(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show notification configuration options."""

        return self._show_notifications_menu()

    async def async_step_default_notification(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure the default/legacy notification service."""

        if user_input is not None:
            return self._save_notification_options(
                notification_service=user_input["notification_service"],
            )

        current_service = self.config_entry.options.get(
            "notification_service",
            "disabled",
        )

        services = self.hass.services.async_services().get(
            "notify",
            {},
        )
        options = [
            selector.SelectOptionDict(
                value="disabled",
                label="Disabled",
            )
        ]
        options.extend(
            selector.SelectOptionDict(
                value=service,
                label=service,
            )
            for service in sorted(services)
        )

        schema = vol.Schema(
            {
                vol.Required(
                    "notification_service",
                    default=current_service,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="default_notification",
            data_schema=schema,
        )

    async def async_step_add_notification_target(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add a named notification target."""
        if user_input is not None:
            name = user_input["target_name"].strip(); service = user_input["notification_service"]
            targets = self._notification_targets()
            if any(t.get("name", "").casefold() == name.casefold() for t in targets):
                return self.async_show_form(step_id="add_notification_target", data_schema=self._notification_target_schema(name, service), errors={"target_name": "target_exists"})
            if any(t.get("service") == service for t in targets):
                return self.async_show_form(step_id="add_notification_target", data_schema=self._notification_target_schema(name, service), errors={"notification_service": "service_exists"})
            targets.append({"name": name, "service": service})
            return self._save_notification_options(notification_targets=targets)
        return self.async_show_form(step_id="add_notification_target", data_schema=self._notification_target_schema())

    async def async_step_edit_notification_target(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Select a notification target to edit."""
        targets = self._notification_targets()
        if not targets: return self.async_abort(reason="no_notification_targets")
        if user_input is not None:
            self._selected_notification_target = user_input["target_name"]
            return await self.async_step_edit_notification_target_details()
        return self.async_show_form(step_id="edit_notification_target", data_schema=self._target_select_schema(targets))

    async def async_step_edit_notification_target_details(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit a notification target."""
        targets = self._notification_targets(); selected = self._selected_notification_target
        current = next((t for t in targets if t["name"] == selected), None)
        if current is None: return self.async_abort(reason="notification_target_not_found")
        if user_input is not None:
            new_name = user_input["target_name"].strip(); new_service = user_input["notification_service"]
            for target in targets:
                if target is current: continue
                if target.get("name", "").casefold() == new_name.casefold():
                    return self.async_show_form(step_id="edit_notification_target_details", data_schema=self._notification_target_schema(new_name, new_service), errors={"target_name": "target_exists"})
                if target.get("service") == new_service:
                    return self.async_show_form(step_id="edit_notification_target_details", data_schema=self._notification_target_schema(new_name, new_service), errors={"notification_service": "service_exists"})
            old_name=current["name"]; current["name"]=new_name; current["service"]=new_service
            routing=self._notification_routing()
            for severity,names in routing.items(): routing[severity]=[new_name if name==old_name else name for name in names]
            self._selected_notification_target=None
            return self._save_notification_options(notification_targets=targets, notification_routing=routing)
        return self.async_show_form(step_id="edit_notification_target_details", data_schema=self._notification_target_schema(current["name"], current["service"]))

    async def async_step_delete_notification_target(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Select a notification target to delete."""
        targets=self._notification_targets()
        if not targets: return self.async_abort(reason="no_notification_targets")
        if user_input is not None:
            self._selected_notification_target=user_input["target_name"]
            return await self.async_step_confirm_delete_notification_target()
        return self.async_show_form(step_id="delete_notification_target", data_schema=self._target_select_schema(targets))

    async def async_step_confirm_delete_notification_target(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm deletion of a notification target."""
        selected=self._selected_notification_target
        if user_input is not None:
            if not user_input.get("confirm"): return self.async_abort(reason="delete_cancelled")
            targets=[t for t in self._notification_targets() if t.get("name") != selected]
            routing=self._notification_routing()
            for severity,names in routing.items(): routing[severity]=[name for name in names if name != selected]
            self._selected_notification_target=None
            return self._save_notification_options(notification_targets=targets, notification_routing=routing)
        return self.async_show_form(step_id="confirm_delete_notification_target", data_schema=vol.Schema({vol.Required("confirm", default=False): selector.BooleanSelector(selector.BooleanSelectorConfig())}))

    async def async_step_notification_routing(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure notification targets by alarm severity."""
        targets=self._notification_targets()
        if not targets: return self.async_abort(reason="no_notification_targets")
        names=[t["name"] for t in targets]; routing=self._notification_routing()
        if user_input is not None:
            return self._save_notification_options(notification_routing={severity:list(user_input.get(severity, [])) for severity in SEVERITIES})
        schema=vol.Schema({vol.Required(severity, default=[name for name in routing.get(severity,names) if name in names]): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value=name,label=name) for name in names], multiple=True, mode=selector.SelectSelectorMode.LIST)) for severity in SEVERITIES})
        return self.async_show_form(step_id="notification_routing", data_schema=schema)

    def _notification_targets(self) -> list[dict[str, str]]:
        """Return configured notification targets."""
        raw=self.config_entry.options.get("notification_targets", [])
        if not isinstance(raw,list): return []
        return [dict(t) for t in raw if isinstance(t,dict) and t.get("name") and t.get("service")]

    def _notification_routing(self) -> dict[str, list[str]]:
        """Return configured severity routing."""
        raw=self.config_entry.options.get("notification_routing", {})
        if not isinstance(raw,dict): return {}
        return {severity:list(raw.get(severity,[])) if isinstance(raw.get(severity,[]),list) else [] for severity in SEVERITIES}

    def _target_select_schema(self, targets: list[dict[str, str]]) -> vol.Schema:
        """Build a notification target selector."""
        return vol.Schema({vol.Required("target_name"): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value=t["name"],label=t["name"]) for t in targets], mode=selector.SelectSelectorMode.DROPDOWN))})

    def _notification_target_schema(self, name: str = "", service: str | None = None) -> vol.Schema:
        """Build the notification target schema."""
        services=self.hass.services.async_services().get("notify", {})
        options=[selector.SelectOptionDict(value=s,label=s) for s in sorted(services)]
        schema={vol.Required("target_name",default=name): selector.TextSelector(selector.TextSelectorConfig())}
        key=vol.Required("notification_service") if service is None else vol.Required("notification_service",default=service)
        schema[key]=selector.SelectSelector(selector.SelectSelectorConfig(options=options,mode=selector.SelectSelectorMode.DROPDOWN))
        return vol.Schema(schema)

    def _save_notification_options(
        self,
        notification_targets: list[dict[str, str]] | None = None,
        notification_routing: dict[str, list[str]] | None = None,
        notification_service: str | None = None,
    ) -> ConfigFlowResult:
        """Persist notification settings without discarding other options."""

        options = dict(self.config_entry.options)

        if notification_targets is not None:
            options["notification_targets"] = notification_targets

        if notification_routing is not None:
            options["notification_routing"] = notification_routing

        if notification_service is not None:
            options["notification_service"] = notification_service

        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=options,
        )

        return self._show_notifications_menu()

    async def async_step_edit_details(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Edit an existing alarm."""
        manager = self._get_manager()
        if manager is None:
            return self.async_abort(reason="manager_not_loaded")
        alarm_id = self._selected_alarm_id
        if alarm_id is None:
            return self.async_abort(reason="alarm_not_selected")
        alarm = manager.get_alarm(alarm_id)
        if alarm is None:
            return self.async_abort(reason="alarm_not_found")

        if user_input is not None:
            self._pending_alarm = dict(user_input)
            self._pending_conditions = list(alarm.normalized_conditions)
            return self._show_condition_menu()

        return self.async_show_form(
            step_id="edit_details",
            data_schema=self._alarm_general_schema_for_alarm(alarm),
        )

    def _alarm_general_schema_for_alarm(self, alarm) -> vol.Schema:
        """Build the general settings schema for an existing alarm."""
        schema = self._alarm_general_schema()
        # Rebuild with existing defaults.
        return vol.Schema({
            vol.Required(CONF_NAME, default=alarm.name): selector.TextSelector(selector.TextSelectorConfig()),
            vol.Required(CONF_SEVERITY, default=alarm.severity): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=SEVERITY_INFO, label="Info"),
                        selector.SelectOptionDict(value=SEVERITY_WARNING, label="Warning"),
                        selector.SelectOptionDict(value=SEVERITY_ALARM, label="Alarm"),
                        selector.SelectOptionDict(value=SEVERITY_CRITICAL, label="Critical"),
                    ], mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_LOGIC, default=alarm.logic): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=LOGIC_ALL, label="ALL conditions must be true"),
                        selector.SelectOptionDict(value=LOGIC_ANY, label="ANY condition may be true"),
                    ], mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_DELAY, default=alarm.delay): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=3600, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
            ),
            vol.Required(CONF_HYSTERESIS, default=alarm.hysteresis): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=1000000, step=0.1, mode=selector.NumberSelectorMode.BOX)
            ),
        })

    def _get_manager(self):
        """Return the active Alarm Manager."""

        domain_data = self.hass.data.get(
            DOMAIN
        )

        if not domain_data:
            return None

        for entry_data in domain_data.values():
            manager = entry_data.get(
                "manager"
            )

            if manager is not None:
                return manager

        return None