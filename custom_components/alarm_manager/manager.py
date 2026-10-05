"""Alarm Manager core logic."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from inspect import isawaitable
from typing import Any, Callable
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .alarm import Alarm
from .alarm_config import AlarmConfig
from .condition import evaluate_alarm_conditions, evaluate_condition
from .const import (
    DOMAIN,
    SIGNAL_ALARM_UPDATED,
    STATE_ACTIVE,
    STATE_ACKNOWLEDGED,
    STATE_CLEARED,
    STATE_INACTIVE,
    STATE_NORMAL,
)
from .storage import AlarmStorage


Callback = Callable[..., Any]


class AlarmManager:
    """Manage alarms, persistence and alarm history."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the alarm manager."""

        self.hass = hass

        self._storage = AlarmStorage(hass)

        self._alarms: dict[str, Alarm] = {}
        self._history: list[dict[str, Any]] = []

        self._pending_tasks: dict[str, asyncio.Task] = {}
        self._condition_delay_tasks: dict[str, asyncio.Task] = {}
        self._condition_runtime: dict[str, dict[str, dict[str, Any]]] = {}

        self._alarm_created_callback: Callback | None = None
        self._alarm_removed_callback: Callback | None = None
        self._alarm_updated_callback: Callback | None = None

    @property
    def alarms(self) -> dict[str, Alarm]:
        """Return configured alarms."""

        return self._alarms

    @property
    def history(self) -> list[dict[str, Any]]:
        """Return alarm history."""

        return self._history

    def get_alarm(
        self,
        alarm_id: str,
    ) -> Alarm | None:
        """Return an alarm by ID."""

        return self._alarms.get(alarm_id)

    async def async_load(self) -> None:
        """Load alarms and history from persistent storage."""

        data = await self._storage.async_load()

        self._alarms = {}

        for alarm_id, raw in data.get(
            "alarms",
            {},
        ).items():
            try:
                alarm = self._alarm_from_storage(
                    alarm_id,
                    raw,
                )
                # Keep the legacy display/compatibility fields synchronized
                # with the primary condition stored in the newer conditions
                # model. Older stored alarms can otherwise retain a stale
                # threshold (for example 1) while the editor shows 29.
                self._sync_primary_condition_fields(alarm)
                self._alarms[alarm_id] = alarm
            except (TypeError, ValueError):
                continue

        self._history = list(
            data.get(
                "history",
                [],
            )
        )

    async def async_save(self) -> None:
        """Persist alarms and history."""

        await self._storage.async_save(
            {
                alarm_id: self._alarm_to_storage(alarm)
                for alarm_id, alarm in self._alarms.items()
            },
            self._history,
        )

    async def _run_callback(
        self,
        callback: Callback | None,
        *args: Any,
    ) -> None:
        """Run an optional callback."""

        if callback is None:
            return

        result = callback(*args)

        if isawaitable(result):
            await result

    def _notify_alarm_updated(
        self,
        alarm_id: str,
    ) -> None:
        """Notify Home Assistant entities."""

        async_dispatcher_send(
            self.hass,
            SIGNAL_ALARM_UPDATED,
            alarm_id,
        )

    def _notify_history_updated(self) -> None:
        """Notify Home Assistant that alarm history changed."""

        self._notify_alarm_updated("history")

        # Legacy signal identifier used by earlier versions.
        self._notify_alarm_updated("__history__")

    def _get_notification_targets(
        self,
        severity: str,
    ) -> list[tuple[str, str]]:
        """Return notification targets configured for a severity."""

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            options = entry.options
            raw_targets = options.get("notification_targets", [])
            targets: dict[str, str] = {}

            if isinstance(raw_targets, list):
                for target in raw_targets:
                    if not isinstance(target, dict):
                        continue
                    name = str(target.get("name", "")).strip()
                    service = str(target.get("service", "")).strip()
                    if name and service:
                        targets[name] = service

            if targets:
                raw_routing = options.get("notification_routing", {})
                selected_names = raw_routing.get(severity, []) if isinstance(raw_routing, dict) else []
                if not isinstance(selected_names, list):
                    selected_names = []
                if not raw_routing:
                    selected_names = list(targets)
                return [(name, targets[name]) for name in selected_names if name in targets]

            service = options.get("notification_service", "disabled")
            if service and service != "disabled":
                return [("Legacy", str(service))]

        return []

    async def _dismiss_alarm_notification(self, notification_id: str) -> None:
        """Dismiss a persistent Alarm Manager notification if present."""
        if not self.hass.services.has_service("persistent_notification", "dismiss"):
            return
        await self.hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": notification_id},
            blocking=False,
        )

    def _active_alarm_objects(self) -> list[Alarm]:
        """Return alarms currently participating in the active lifecycle."""
        return [
            alarm
            for alarm in self._alarms.values()
            if alarm.state in (STATE_ACTIVE, STATE_ACKNOWLEDGED)
        ]

    async def _create_alarm_summary_notification(self) -> None:
        """Create one compact notification when many alarms are active."""
        active = self._active_alarm_objects()
        count = len(active)

        if count <= 3:
            await self._dismiss_alarm_notification(f"{DOMAIN}_summary")
            return

        # Remove the individual persistent cards so the operator gets one
        # compact SCADA-style summary instead of a wall of notifications.
        for alarm in active:
            await self._dismiss_alarm_notification(f"{DOMAIN}_{alarm.alarm_id}")

        if self.hass.services.has_service("persistent_notification", "create"):
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"🚨 {count} ALARMS ACTIVE",
                    "message": (
                        f"**{count} alarms are currently active.**\n\n"
                        "[**OPEN ALARM MANAGER →**](/alarm-manager)"
                    ),
                    "notification_id": f"{DOMAIN}_summary",
                },
                blocking=False,
            )

        # Also update mobile/device targets with the same compact summary.
        target_names: set[str] = set()
        services: set[str] = set()
        for alarm in active:
            for target_name, service in self._get_notification_targets(alarm.severity):
                target_names.add(target_name)
                services.add(service)

        for service in services:
            if not self.hass.services.has_service("notify", service):
                continue
            await self.hass.services.async_call(
                "notify",
                service,
                {
                    "title": f"🚨 {count} ALARMS ACTIVE",
                    "message": "One or more Alarm Manager alarms are active.",
                    "data": {
                        "url": "/alarm-manager",
                        "tag": f"{DOMAIN}_summary",
                        "group": DOMAIN,
                    },
                },
                blocking=False,
            )

    async def _create_alarm_notification(
        self,
        alarm: Alarm,
    ) -> None:
        """Create a compact alarm notification or a multi-alarm summary."""
        active = self._active_alarm_objects()

        # Once more than three alarms are active, collapse the individual
        # notifications into one compact summary.
        if len(active) > 3:
            await self._create_alarm_summary_notification()
            return

        if not self.hass.services.has_service(
            "persistent_notification",
            "create",
        ):
            return

        if alarm.conditions:
            condition_lines = []
            for item in alarm.normalized_conditions:
                if item.get("type") == "time":
                    description = (
                        f"time {item.get('condition')} "
                        f"{item.get('start_time') or item.get('time')}"
                    )
                    if item.get("end_time"):
                        description += f"–{item['end_time']}"
                else:
                    threshold = item.get("threshold")
                    description = (
                        f"{item.get('entity_id')} "
                        f"{item.get('condition')}"
                    )
                    if threshold not in (None, ""):
                        description += f" {threshold}"
                condition_lines.append(description)

            message = (
                f"**{alarm.severity.upper()} · ACTIVE**\n\n"
                f"{chr(10).join(f'`{line}`' for line in condition_lines)}\n\n"
                "[**OPEN ALARM MANAGER →**](/alarm-manager)"
            )
        else:
            message = (
                f"**{alarm.severity.upper()} · ACTIVE**\n\n"
                f"`{alarm.trigger_value}` · `{alarm.condition} {alarm.threshold}`\n\n"
                "[**OPEN ALARM MANAGER →**](/alarm-manager)"
            )

        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"🚨 {alarm.name}",
                "message": message,
                "notification_id": f"{DOMAIN}_{alarm.alarm_id}",
            },
            blocking=False,
        )

        targets = self._get_notification_targets(alarm.severity)

        for _target_name, service in targets:
            if not self.hass.services.has_service(
                "notify",
                service,
            ):
                continue

            if alarm.conditions:
                compact_conditions = []
                for item in alarm.normalized_conditions:
                    text = f"{item.get('entity_id')} {item.get('condition')}"
                    if item.get("threshold") not in (None, ""):
                        text += f" {item.get('threshold')}"
                    compact_conditions.append(text)
                compact_message = f"{alarm.severity.upper()} · ACTIVE\n" + "\n".join(compact_conditions)
            else:
                compact_message = f"{alarm.severity.upper()} · ACTIVE\n{alarm.trigger_value} · {alarm.condition} {alarm.threshold}"

            await self.hass.services.async_call(
                "notify",
                service,
                {
                    "title": f"🚨 {alarm.name}",
                    "message": compact_message,
                    "data": {
                        "url": "/alarm-manager",
                        "tag": f"{DOMAIN}_{alarm.alarm_id}",
                        "group": DOMAIN,
                    },
                },
                blocking=False,
            )

    async def async_add_alarm(
        self,
        config: AlarmConfig | None = None,
        *,
        name: str | None = None,
        entity_id: str | None = None,
        condition: str | None = None,
        threshold: float | str | None = None,
        severity: str | None = None,
        delay: int = 0,
        hysteresis: float = 0.0,
        conditions: list[dict[str, Any]] | None = None,
        logic: str = "all",
    ) -> Alarm:
        """Add and persist a new alarm."""

        if config is not None:
            name = config.name
            entity_id = config.entity_id
            condition = config.condition
            threshold = config.threshold
            severity = config.severity
            delay = config.delay
            hysteresis = config.hysteresis
            conditions = config.conditions
            logic = config.logic

            alarm_id = (
                config.alarm_id
                or str(uuid4())
            )
        else:
            alarm_id = str(uuid4())

        alarm = Alarm(
            alarm_id=alarm_id,
            name=name or "Alarm",
            entity_id=entity_id or "",
            condition=condition or "above",
            threshold=threshold,
            severity=severity or "warning",
            delay=int(delay or 0),
            hysteresis=float(
                hysteresis or 0.0
            ),
            conditions=list(conditions or []),
            logic=logic or "all",
        )

        self._sync_primary_condition_fields(alarm)
        self._alarms[alarm.alarm_id] = alarm

        await self.async_save()

        await self._run_callback(
            self._alarm_created_callback,
            alarm,
        )

        self._notify_alarm_updated(
            alarm.alarm_id
        )

        return alarm

    async def async_update_alarm(
        self,
        config: AlarmConfig | None = None,
        *,
        alarm_id: str | None = None,
        name: str | None = None,
        entity_id: str | None = None,
        condition: str | None = None,
        threshold: float | str | None = None,
        severity: str | None = None,
        delay: int = 0,
        hysteresis: float = 0.0,
        conditions: list[dict[str, Any]] | None = None,
        logic: str = "all",
    ) -> Alarm | None:
        """Update an existing alarm."""

        if config is not None:
            alarm_id = config.alarm_id
            name = config.name
            entity_id = config.entity_id
            condition = config.condition
            threshold = config.threshold
            severity = config.severity
            delay = config.delay
            hysteresis = config.hysteresis
            conditions = config.conditions
            logic = config.logic

        if not alarm_id:
            return None

        alarm = self._alarms.get(alarm_id)

        if alarm is None:
            return None

        self._cancel_pending_activation(
            alarm_id
        )

        if name is not None:
            alarm.name = name

        if entity_id is not None:
            alarm.entity_id = entity_id

        if condition is not None:
            alarm.condition = condition

        alarm.threshold = threshold

        if severity is not None:
            alarm.severity = severity

        alarm.delay = int(delay or 0)

        alarm.hysteresis = float(
            hysteresis or 0.0
        )

        if conditions is not None:
            self._cancel_condition_delay(alarm_id)
            self._condition_runtime.pop(alarm_id, None)
            alarm.conditions = list(conditions)
            # The primary alarm entity is now independent from the optional
            # condition group. Keep an explicitly supplied entity_id.
            # For legacy callers that only provide conditions, use the first
            # entity condition as a backwards-compatible fallback.
            if not alarm.entity_id:
                first_entity = next(
                    (item.get("entity_id") for item in alarm.conditions
                     if item.get("type", "entity") == "entity" and item.get("entity_id")),
                    "",
                )
                alarm.entity_id = first_entity

        alarm.logic = logic or "all"
        self._sync_primary_condition_fields(alarm)

        await self.async_save()

        await self._run_callback(
            self._alarm_updated_callback,
            alarm,
        )

        self._notify_alarm_updated(
            alarm.alarm_id
        )

        current_state = self.hass.states.get(
            alarm.entity_id
        )

        if current_state is not None:
            await self.async_evaluate_alarm(
                alarm_id=alarm.alarm_id,
                state=current_state.state,
            )

        return alarm

    async def async_remove_alarm(
        self,
        alarm_id: str,
    ) -> bool:
        """Remove an alarm."""

        alarm = self._alarms.get(alarm_id)

        if alarm is None:
            return False

        self._cancel_pending_activation(
            alarm_id
        )
        self._cancel_condition_delay(alarm_id)
        self._condition_runtime.pop(alarm_id, None)

        self._alarms.pop(
            alarm_id,
            None,
        )

        await self.async_save()

        await self._run_callback(
            self._alarm_removed_callback,
            alarm_id,
        )

        self._notify_alarm_updated(
            alarm_id
        )

        return True

    async def async_trigger_alarm(
        self,
        alarm_id: str,
    ) -> bool:
        """Manually trigger an alarm, including alarms without conditions."""
        alarm = self._alarms.get(alarm_id)
        if alarm is None:
            return False

        # A manual trigger starts a new occurrence using the same lifecycle
        # and notification path as a condition-triggered alarm.
        if alarm.state in (STATE_ACTIVE, STATE_ACKNOWLEDGED):
            return True

        alarm.last_value = None
        alarm.condition_snapshot = {}
        await self._handle_triggered(alarm)
        self._notify_alarm_updated(alarm_id)
        return True

    async def async_clear_alarm(self, alarm_id: str) -> bool:
        """Clear a latched inactive alarm without acknowledging it.

        The completed history occurrence is marked CLEARED, without adding
        an acknowledgement. This represents an operator clearing a condition
        that had already returned to normal without acknowledging the alarm.
        """
        alarm = self._alarms.get(alarm_id)

        if alarm is None:
            return False

        if alarm.state != STATE_INACTIVE:
            return False

        # The occurrence was already written to history when the condition
        # returned to normal. Mark that occurrence as explicitly CLEARED
        # by the operator, without adding an acknowledgement.
        self._update_history_completion_status(
            alarm_id,
            "CLEARED",
        )

        alarm.reset()

        await self.async_save()

        self._notify_alarm_updated(alarm_id)
        self._notify_history_updated()
        await self._create_alarm_summary_notification()

        return True

    async def async_acknowledge_alarm(
        self,
        alarm_id: str,
        user_id: str | None = None,
    ) -> bool:
        """Acknowledge one alarm and record who acknowledged it."""

        alarm = self._alarms.get(alarm_id)

        if alarm is None:
            return False

        acknowledged_by, acknowledged_by_user_id = (
            await self._get_acknowledger(user_id)
        )

        # ACTIVE -> ACKNOWLEDGED
        if alarm.state == STATE_ACTIVE:
            alarm.acknowledge(
                acknowledged_by=acknowledged_by,
                acknowledged_by_user_id=acknowledged_by_user_id,
            )

            await self.async_save()

            self._notify_alarm_updated(
                alarm_id
            )

            # Re-evaluate immediately after acknowledgement. This handles
            # the case where the condition has already returned to normal
            # before the operator acknowledges the alarm. Without this
            # check, an acknowledged alarm can remain in Current Alarms
            # until a later state update or an edit/save operation triggers
            # another evaluation.
            await self.async_evaluate_alarm(alarm_id=alarm_id)

            return True

        # INACTIVE -> NORMAL
        #
        # The occurrence already exists in history.
        # Add the acknowledgement information to that
        # occurrence before resetting the alarm.
        if alarm.state == STATE_INACTIVE:
            acknowledgement_time = (
                datetime.now(timezone.utc)
            )

            alarm.acknowledged_at = (
                acknowledgement_time
            )
            alarm.acknowledged_by = acknowledged_by
            alarm.acknowledged_by_user_id = (
                acknowledged_by_user_id
            )

            self._update_history_acknowledgement(
                alarm_id,
                acknowledgement_time,
                acknowledged_by,
                acknowledged_by_user_id,
            )
            self._update_history_completion_status(
                alarm_id,
                "ACKNOWLEDGED",
            )

            alarm.reset()

            await self.async_save()

            self._notify_alarm_updated(
                alarm_id
            )

            self._notify_history_updated()
            await self._create_alarm_summary_notification()

            return True

        # Already acknowledged.
        if alarm.state == STATE_ACKNOWLEDGED:
            return True

        return True

    async def async_acknowledge_all(
        self,
        user_id: str | None = None,
    ) -> None:
        """Acknowledge all unacknowledged alarms."""

        changed = False
        history_changed = False

        acknowledgement_time = (
            datetime.now(timezone.utc)
        )

        acknowledged_by, acknowledged_by_user_id = (
            await self._get_acknowledger(user_id)
        )

        for alarm in self._alarms.values():

            if alarm.state == STATE_ACTIVE:
                alarm.acknowledge(
                    acknowledged_by=acknowledged_by,
                    acknowledged_by_user_id=acknowledged_by_user_id,
                )
                changed = True

            elif alarm.state == STATE_INACTIVE:

                alarm.acknowledged_at = (
                    acknowledgement_time
                )
                alarm.acknowledged_by = acknowledged_by
                alarm.acknowledged_by_user_id = (
                    acknowledged_by_user_id
                )

                self._update_history_acknowledgement(
                    alarm.alarm_id,
                    acknowledgement_time,
                    acknowledged_by,
                    acknowledged_by_user_id,
                )
                self._update_history_completion_status(
                    alarm.alarm_id,
                    "ACKNOWLEDGED",
                )

                alarm.reset()

                changed = True
                history_changed = True

        if not changed:
            return

        await self.async_save()

        for alarm in self._alarms.values():
            self._notify_alarm_updated(
                alarm.alarm_id
            )

        if history_changed:
            self._notify_history_updated()

    async def _get_acknowledger(
        self,
        user_id: str | None,
    ) -> tuple[str, str | None]:
        """Return a display name and user ID for an acknowledgement."""

        if not user_id:
            return "System", None

        user = await self.hass.auth.async_get_user(
            user_id
        )

        if user is None:
            return user_id, user_id

        display_name = getattr(
            user,
            "name",
            None,
        ) or user_id

        return display_name, user_id

    async def async_clear_history(self) -> None:
        """Clear all alarm history."""

        self._history = []

        await self.async_save()

        self._notify_history_updated()

    def _sync_primary_condition_fields(self, alarm: Alarm) -> None:
        """Keep legacy fields aligned with the primary entity condition.

        The frontend and older service consumers still expose ``condition``
        and ``threshold`` as top-level alarm attributes. The visual editor
        stores the richer definition in ``conditions``, so mirror the first
        entity condition into the legacy fields for display and compatibility.
        """
        conditions = alarm.conditions or []
        primary = None
        if alarm.entity_id:
            primary = next(
                (item for item in conditions
                 if item.get("type", "entity") == "entity"
                 and item.get("entity_id") == alarm.entity_id),
                None,
            )
        if primary is None:
            primary = next(
                (item for item in conditions
                 if item.get("type", "entity") == "entity"),
                None,
            )
        if primary is None:
            return

        alarm.entity_id = str(primary.get("entity_id") or alarm.entity_id or "")
        alarm.condition = str(primary.get("condition") or alarm.condition or "above")
        alarm.threshold = primary.get("threshold")

    async def async_evaluate_alarm(
        self,
        alarm_id: str,
        state: Any = None,
    ) -> None:
        """Evaluate all conditions for an alarm."""

        alarm = self._alarms.get(alarm_id)
        if alarm is None:
            return

        conditions = alarm.normalized_conditions
        if not conditions:
            # A conditionless alarm is intentionally manual.
            # It can be activated by the trigger_alarm service.
            alarm.condition_snapshot = {}
            self._notify_alarm_updated(alarm_id)
            return

        next_delay = None
        if not alarm.conditions and state is not None and len(conditions) == 1:
            item = conditions[0]
            triggered = evaluate_condition(
                state,
                item.get("condition", alarm.condition),
                item.get("threshold", alarm.threshold),
            )
            snapshot = {
                alarm.entity_id: {
                    "type": "entity",
                    "state": state,
                    "condition": alarm.condition,
                    "threshold": alarm.threshold,
                    "result": triggered,
                }
            }
        else:
            triggered, snapshot, next_delay = evaluate_alarm_conditions(
                self.hass,
                conditions,
                alarm.logic,
                self._condition_runtime.setdefault(alarm_id, {}),
            )

        alarm.condition_snapshot = snapshot
        self._schedule_condition_delay(alarm_id, next_delay)

        if alarm.entity_ids:
            first_state = self.hass.states.get(alarm.entity_ids[0])
            alarm.last_value = (
                first_state.state if first_state is not None else None
            )

        if triggered:
            await self._handle_triggered(alarm)
        else:
            await self._handle_normal(alarm)

        self._notify_alarm_updated(alarm_id)

    async def _handle_triggered(
        self,
        alarm: Alarm,
    ) -> None:
        """Handle a triggered condition."""

        # ---------------------------------------------------------
        # INACTIVE -> NEW OCCURRENCE
        #
        # The previous occurrence has already been cleared and
        # stored in history. A new abnormal condition is therefore
        # a completely new alarm occurrence.
        # ---------------------------------------------------------
        if alarm.state == STATE_INACTIVE:

            self._cancel_pending_activation(
                alarm.alarm_id
            )

            # Preserve the alarm configuration but reset the
            # lifecycle data from the previous occurrence.
            alarm.state = STATE_NORMAL
            alarm.activated_at = None
            alarm.acknowledged_at = None
            alarm.acknowledged_by = None
            alarm.acknowledged_by_user_id = None
            alarm.cleared_at = None
            alarm.trigger_value = None

            # Start the new occurrence immediately if there is
            # no activation delay.
            if alarm.delay <= 0:
                alarm.activate(
                    alarm.last_value
                )

                await self.async_save()
                await self._create_alarm_notification(alarm)

                return

            # Otherwise use the normal delayed activation path.
            if alarm.alarm_id not in self._pending_tasks:
                self._pending_tasks[
                    alarm.alarm_id
                ] = self.hass.async_create_task(
                    self._delayed_activation(
                        alarm.alarm_id,
                        alarm.delay,
                    )
                )

            await self.async_save()

            return

        # Already active or acknowledged.
        if alarm.state in (
            STATE_ACTIVE,
            STATE_ACKNOWLEDGED,
        ):
            return

        # NORMAL -> ACTIVE
        if alarm.delay <= 0:
            alarm.activate(
                alarm.last_value
            )

            await self.async_save()
            await self._create_alarm_notification(alarm)

            return

        if alarm.alarm_id in self._pending_tasks:
            return

        self._pending_tasks[
            alarm.alarm_id
        ] = self.hass.async_create_task(
            self._delayed_activation(
                alarm.alarm_id,
                alarm.delay,
            )
        )

    async def _handle_normal(
        self,
        alarm: Alarm,
    ) -> None:
        """Handle a condition returning to normal."""

        self._cancel_pending_activation(
            alarm.alarm_id
        )

        # ACTIVE -> INACTIVE
        #
        # Create the history record immediately,
        # but keep the alarm itself INACTIVE until
        # the operator acknowledges it.
        if alarm.state == STATE_ACTIVE:
            alarm.clear()

            self._add_history_record(
                alarm
            )

            await self.async_save()
            await self._create_alarm_summary_notification()

            return

        # ACKNOWLEDGED -> NORMAL
        #
        # The occurrence completes here.
        if alarm.state == STATE_ACKNOWLEDGED:
            alarm.clear()

            self._add_history_record(
                alarm
            )

            alarm.reset()

            await self.async_save()
            await self._create_alarm_summary_notification()

            return

        # INACTIVE remains available for a new occurrence.
        if alarm.state == STATE_INACTIVE:
            return

    async def _delayed_activation(
        self,
        alarm_id: str,
        delay: int,
    ) -> None:
        """Activate an alarm after a delay."""

        try:
            await asyncio.sleep(
                delay
            )

            alarm = self._alarms.get(
                alarm_id
            )

            if alarm is None:
                return

            triggered, snapshot, next_delay = evaluate_alarm_conditions(
                self.hass,
                alarm.normalized_conditions,
                alarm.logic,
                self._condition_runtime.setdefault(alarm_id, {}),
            )

            alarm.condition_snapshot = snapshot
            self._schedule_condition_delay(alarm_id, next_delay)

            if alarm.entity_ids:
                current_state = self.hass.states.get(alarm.entity_ids[0])
                alarm.last_value = (
                    current_state.state if current_state is not None else None
                )

            if not triggered:
                return

            if alarm.state != STATE_NORMAL:
                return

            alarm.activate(
                current_state.state
            )

            await self.async_save()
            await self._create_alarm_notification(alarm)

            self._notify_alarm_updated(
                alarm_id
            )

        except asyncio.CancelledError:
            raise

        finally:
            self._pending_tasks.pop(
                alarm_id,
                None,
            )

    def _schedule_condition_delay(
        self,
        alarm_id: str,
        delay: float | None,
    ) -> None:
        """Schedule a re-evaluation when a condition delay expires."""
        current_task = asyncio.current_task()
        existing = self._condition_delay_tasks.get(alarm_id)
        if existing is not None and existing is not current_task:
            self._condition_delay_tasks.pop(alarm_id, None)
            existing.cancel()

        if delay is None or delay <= 0:
            if existing is current_task:
                self._condition_delay_tasks.pop(alarm_id, None)
            return

        async def _wait_and_evaluate() -> None:
            try:
                await asyncio.sleep(delay)
                if alarm_id in self._alarms:
                    await self.async_evaluate_alarm(alarm_id=alarm_id)
            except asyncio.CancelledError:
                raise
            finally:
                if self._condition_delay_tasks.get(alarm_id) is asyncio.current_task():
                    self._condition_delay_tasks.pop(alarm_id, None)

        self._condition_delay_tasks[alarm_id] = self.hass.async_create_task(
            _wait_and_evaluate()
        )

    def _cancel_condition_delay(self, alarm_id: str) -> None:
        """Cancel a pending condition-delay re-evaluation."""
        task = self._condition_delay_tasks.pop(alarm_id, None)
        if task is not None:
            task.cancel()

    def _cancel_pending_activation(
        self,
        alarm_id: str,
    ) -> None:
        """Cancel a pending activation."""

        task = self._pending_tasks.pop(
            alarm_id,
            None,
        )

        if task is not None:
            task.cancel()

    def stop_all_pending_tasks(self) -> None:
        """Cancel all pending activation tasks."""

        for task in self._pending_tasks.values():
            task.cancel()

        self._pending_tasks.clear()

        for task in self._condition_delay_tasks.values():
            task.cancel()

        self._condition_delay_tasks.clear()
        self._condition_runtime.clear()

    def _add_history_record(
        self,
        alarm: Alarm,
    ) -> None:
        """Add a completed alarm occurrence to history."""

        record = {
            "alarm_id": alarm.alarm_id,
            "name": alarm.name,
            "entity_id": alarm.entity_id,
            "condition": alarm.condition,
            "threshold": alarm.threshold,
            "conditions": list(alarm.normalized_conditions),
            "logic": alarm.logic,
            "condition_snapshot": dict(alarm.condition_snapshot),
            "severity": alarm.severity,
            "trigger_value": alarm.trigger_value,
            "last_value": alarm.last_value,
            "activated_at": self._datetime_to_string(
                alarm.activated_at
            ),
            "acknowledged_at": self._datetime_to_string(
                alarm.acknowledged_at
            ),
            "acknowledged_by": alarm.acknowledged_by,
            "acknowledged_by_user_id": (
                alarm.acknowledged_by_user_id
            ),
            "cleared_at": self._datetime_to_string(
                alarm.cleared_at
            ),
            "duration": alarm.duration,
        }

        record[
            "completion_status"
        ] = (
            "ACKNOWLEDGED"
            if alarm.acknowledged_at
            else "UNACKNOWLEDGED"
        )

        self._history.append(
            record
        )

        # Keep the most recent 500
        # occurrences.
        self._history = (
            self._history[-500:]
        )

        self._notify_history_updated()

    def _update_history_completion_status(
        self,
        alarm_id: str,
        status: str,
    ) -> None:
        """Update the most recent occurrence completion status."""

        for record in reversed(self._history):
            if record.get("alarm_id") == alarm_id:
                record["completion_status"] = status
                break

    def _update_history_acknowledgement(
        self,
        alarm_id: str,
        acknowledged_at: datetime,
        acknowledged_by: str | None,
        acknowledged_by_user_id: str | None,
    ) -> None:
        """Update the history record for an inactive alarm."""

        timestamp = (
            self._datetime_to_string(
                acknowledged_at
            )
        )

        # Find the most recent occurrence
        # belonging to this alarm.
        for record in reversed(
            self._history
        ):
            if (
                record.get("alarm_id")
                == alarm_id
            ):
                record[
                    "acknowledged_at"
                ] = timestamp
                record[
                    "acknowledged_by"
                ] = acknowledged_by
                record[
                    "acknowledged_by_user_id"
                ] = acknowledged_by_user_id
                break

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime | None:
        """Parse an ISO datetime."""

        if not value:
            return None

        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(
                str(value)
            )

        if parsed.tzinfo is None:
            return parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    @staticmethod
    def _datetime_to_string(
        value: datetime | None,
    ) -> str | None:
        """Serialize a datetime."""

        if value is None:
            return None

        return value.isoformat()

    def _alarm_from_storage(
        self,
        alarm_id: str,
        raw: dict[str, Any],
    ) -> Alarm:
        """Create an Alarm from stored data."""

        state = raw.get(
            "state",
            STATE_NORMAL,
        )

        # Convert legacy CLEARED state to
        # the new latched INACTIVE state.
        if state == STATE_CLEARED:
            state = STATE_INACTIVE

        return Alarm(
            alarm_id=alarm_id,
            name=raw.get(
                "name",
                "Alarm",
            ),
            entity_id=raw.get(
                "entity_id",
                "",
            ),
            condition=raw.get(
                "condition",
                "above",
            ),
            threshold=raw.get(
                "threshold"
            ),
            severity=raw.get(
                "severity",
                "warning",
            ),
            delay=int(
                raw.get(
                    "delay",
                    0,
                )
                or 0
            ),
            hysteresis=float(
                raw.get(
                    "hysteresis",
                    0.0,
                )
                or 0.0
            ),
            conditions=list(raw.get("conditions", []) or []),
            logic=str(raw.get("logic", "all") or "all"),
            state=state,
            activated_at=self._parse_datetime(
                raw.get(
                    "activated_at"
                )
            ),
            acknowledged_at=self._parse_datetime(
                raw.get(
                    "acknowledged_at"
                )
            ),
            acknowledged_by=raw.get(
                "acknowledged_by"
            ),
            acknowledged_by_user_id=raw.get(
                "acknowledged_by_user_id"
            ),
            cleared_at=self._parse_datetime(
                raw.get(
                    "cleared_at"
                )
            ),
            last_value=raw.get(
                "last_value"
            ),
            trigger_value=raw.get(
                "trigger_value"
            ),
            condition_snapshot=dict(raw.get("condition_snapshot", {}) or {}),
        )

    def _alarm_to_storage(
        self,
        alarm: Alarm,
    ) -> dict[str, Any]:
        """Serialize an Alarm."""

        return {
            "name": alarm.name,
            "entity_id": alarm.entity_id,
            "condition": alarm.condition,
            "threshold": alarm.threshold,
            "severity": alarm.severity,
            "delay": alarm.delay,
            "hysteresis": alarm.hysteresis,
            "conditions": list(alarm.normalized_conditions) if alarm.conditions else [],
            "logic": alarm.logic,
            "condition_snapshot": dict(alarm.condition_snapshot),
            "state": alarm.state,
            "activated_at": self._datetime_to_string(
                alarm.activated_at
            ),
            "acknowledged_at": self._datetime_to_string(
                alarm.acknowledged_at
            ),
            "acknowledged_by": alarm.acknowledged_by,
            "acknowledged_by_user_id": (
                alarm.acknowledged_by_user_id
            ),
            "cleared_at": self._datetime_to_string(
                alarm.cleared_at
            ),
            "last_value": alarm.last_value,
            "trigger_value": alarm.trigger_value,
        }