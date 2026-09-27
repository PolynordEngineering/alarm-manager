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
from .condition import evaluate_condition
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
                self._alarms[alarm_id] = (
                    self._alarm_from_storage(
                        alarm_id,
                        raw,
                    )
                )
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

    async def _create_alarm_notification(
        self,
        alarm: Alarm,
    ) -> None:
        """Create a persistent Home Assistant notification."""

        if not self.hass.services.has_service(
            "persistent_notification",
            "create",
        ):
            return

        title = f"🚨 {alarm.name}"

        message = (
            "### ALARM — ACTIVE\n\n"
            f"**Value:** `{alarm.trigger_value}`  \n"
            f"**Condition:** `{alarm.condition}`  \n"
            f"**Limit:** `{alarm.threshold}`  \n"
            f"**Severity:** **{alarm.severity.upper()}**  \n\n"
            "[**OPEN ALARM MANAGER →**](/alarm-manager)"
        )

        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": f"{DOMAIN}_{alarm.alarm_id}",
            },
            blocking=False,
        )

        targets = self._get_notification_targets(
            alarm.severity
        )

        for _target_name, service in targets:
            if not self.hass.services.has_service(
                "notify",
                service,
            ):
                continue

            await self.hass.services.async_call(
                "notify",
                service,
                {
                    "title": f"🚨 {alarm.name}",
                    "message": (
                        f"Alarm active: {alarm.trigger_value} "
                        f"({alarm.condition} {alarm.threshold})"
                    ),
                    "data": {
                        "url": "/alarm-manager",
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
        )

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

            alarm.reset()

            await self.async_save()

            self._notify_alarm_updated(
                alarm_id
            )

            self._notify_history_updated()

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

    async def async_evaluate_alarm(
        self,
        alarm_id: str,
        state: Any,
    ) -> None:
        """Evaluate an alarm against an entity state."""

        alarm = self._alarms.get(alarm_id)

        if alarm is None:
            return

        alarm.last_value = state

        triggered = evaluate_condition(
            state,
            alarm.condition,
            alarm.threshold,
        )

        if triggered:
            await self._handle_triggered(
                alarm
            )
        else:
            await self._handle_normal(
                alarm
            )

        self._notify_alarm_updated(
            alarm_id
        )

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

            current_state = self.hass.states.get(
                alarm.entity_id
            )

            if current_state is None:
                return

            triggered = evaluate_condition(
                current_state.state,
                alarm.condition,
                alarm.threshold,
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

        self._history.append(
            record
        )

        # Keep the most recent 500
        # occurrences.
        self._history = (
            self._history[-500:]
        )

        self._notify_history_updated()

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