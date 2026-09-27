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
    DOMAIN,
    SEVERITY_ALARM,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
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
        """Create a new alarm."""

        if user_input is not None:
            return await self._create_alarm(
                user_input
            )

        return self.async_show_form(
            step_id="add_alarm",
            data_schema=self._alarm_schema(),
        )

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
            config = AlarmConfig(
                alarm_id=alarm_id,
                name=user_input[
                    CONF_NAME
                ],
                entity_id=user_input[
                    CONF_ENTITY_ID
                ],
                condition=user_input[
                    CONF_CONDITION
                ],
                threshold=user_input.get(
                    CONF_THRESHOLD
                ),
                severity=user_input[
                    CONF_SEVERITY
                ],
                delay=user_input[
                    CONF_DELAY
                ],
                hysteresis=user_input[
                    CONF_HYSTERESIS
                ],
            )

            updated = await manager.async_update_alarm(
                config
            )

            if updated is None:
                return self.async_abort(
                    reason="alarm_not_found"
                )

            return self._show_main_menu()

        schema = self._alarm_schema(
            alarm=alarm
        )

        return self.async_show_form(
            step_id="edit_details",
            data_schema=schema,
        )

    def _alarm_schema(
        self,
        alarm=None,
    ) -> vol.Schema:
        """Build the alarm configuration schema."""

        if alarm is None:
            name_default = "New Alarm"
            entity_default = None
            condition_default = CONDITION_ABOVE
            threshold_default = 0.0
            severity_default = SEVERITY_WARNING
            delay_default = 0
            hysteresis_default = 0.0

        else:
            name_default = alarm.name
            entity_default = alarm.entity_id
            condition_default = alarm.condition

            threshold_default = (
                alarm.threshold
                if isinstance(
                    alarm.threshold,
                    (int, float),
                )
                else 0.0
            )

            severity_default = alarm.severity
            delay_default = alarm.delay
            hysteresis_default = alarm.hysteresis

        schema = {
            vol.Required(
                CONF_NAME,
                default=name_default,
            ): selector.TextSelector(
                selector.TextSelectorConfig()
            ),

            vol.Required(
                CONF_ENTITY_ID,
                default=entity_default,
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    multiple=False
                )
            ),

            vol.Required(
                CONF_CONDITION,
                default=condition_default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=CONDITION_ABOVE,
                            label="Above",
                        ),
                        selector.SelectOptionDict(
                            value=CONDITION_BELOW,
                            label="Below",
                        ),
                        selector.SelectOptionDict(
                            value=CONDITION_EQUAL,
                            label="Equal",
                        ),
                        selector.SelectOptionDict(
                            value=CONDITION_NOT_EQUAL,
                            label="Not equal",
                        ),
                        selector.SelectOptionDict(
                            value=CONDITION_ON,
                            label="On",
                        ),
                        selector.SelectOptionDict(
                            value=CONDITION_OFF,
                            label="Off",
                        ),
                        selector.SelectOptionDict(
                            value=CONDITION_UNAVAILABLE,
                            label="Unavailable",
                        ),
                    ],
                    mode=(
                        selector.SelectSelectorMode.DROPDOWN
                    ),
                )
            ),

            vol.Optional(
                CONF_THRESHOLD,
                default=threshold_default,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-1000000,
                    max=1000000,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),

            vol.Required(
                CONF_SEVERITY,
                default=severity_default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=SEVERITY_INFO,
                            label="Info",
                        ),
                        selector.SelectOptionDict(
                            value=SEVERITY_WARNING,
                            label="Warning",
                        ),
                        selector.SelectOptionDict(
                            value=SEVERITY_ALARM,
                            label="Alarm",
                        ),
                        selector.SelectOptionDict(
                            value=SEVERITY_CRITICAL,
                            label="Critical",
                        ),
                    ],
                    mode=(
                        selector.SelectSelectorMode.DROPDOWN
                    ),
                )
            ),

            vol.Required(
                CONF_DELAY,
                default=delay_default,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=3600,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),

            vol.Required(
                CONF_HYSTERESIS,
                default=hysteresis_default,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=1000000,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }

        return vol.Schema(schema)

    async def _create_alarm(
        self,
        user_input: dict[str, Any],
    ) -> ConfigFlowResult:
        """Create and persist a new alarm."""

        manager = self._get_manager()

        if manager is None:
            return self.async_abort(
                reason="manager_not_loaded"
            )

        config = AlarmConfig(
            alarm_id=str(
                uuid.uuid4()
            ),
            name=user_input[
                CONF_NAME
            ],
            entity_id=user_input[
                CONF_ENTITY_ID
            ],
            condition=user_input[
                CONF_CONDITION
            ],
            threshold=user_input.get(
                CONF_THRESHOLD
            ),
            severity=user_input[
                CONF_SEVERITY
            ],
            delay=user_input[
                CONF_DELAY
            ],
            hysteresis=user_input[
                CONF_HYSTERESIS
            ],
        )

        await manager.async_add_alarm(
            config
        )

        return self._show_main_menu()

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