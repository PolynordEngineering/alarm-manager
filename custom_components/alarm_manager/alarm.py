"""Alarm object for Alarm Manager."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .const import (
    CONDITION_TYPE_ENTITY,
    CONDITION_TYPE_TIME,
    STATE_ACTIVE,
    STATE_ACKNOWLEDGED,
    STATE_INACTIVE,
    STATE_NORMAL,
)


def utcnow() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class Alarm:
    """Represent a single alarm."""

    alarm_id: str
    name: str
    entity_id: str
    condition: str
    threshold: float | str | None = None
    severity: str = "warning"
    delay: int = 0
    hysteresis: float = 0.0
    conditions: list[dict[str, Any]] = field(default_factory=list)
    logic: str = "all"

    state: str = STATE_NORMAL

    activated_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    acknowledged_by_user_id: str | None = None
    cleared_at: datetime | None = None

    last_value: Any = None
    trigger_value: Any = None
    condition_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_conditions(self) -> list[dict[str, Any]]:
        """Return conditions, converting legacy alarms to one entity condition."""
        if self.conditions:
            return self.conditions

        if not self.entity_id:
            return []

        return [
            {
                "type": CONDITION_TYPE_ENTITY,
                "entity_id": self.entity_id,
                "condition": self.condition,
                "threshold": self.threshold,
            }
        ]

    @property
    def entity_ids(self) -> list[str]:
        """Return the primary alarm entity plus entities used by conditions."""
        entity_ids: list[str] = []
        if self.entity_id:
            entity_ids.append(str(self.entity_id))

        entity_ids.extend(
            str(item.get("entity_id"))
            for item in self.normalized_conditions
            if item.get("type", CONDITION_TYPE_ENTITY) == CONDITION_TYPE_ENTITY
            and item.get("entity_id")
        )
        return list(dict.fromkeys(entity_ids))

    @property
    def has_time_conditions(self) -> bool:
        """Return whether this alarm contains a time condition."""
        return any(
            item.get("type") == CONDITION_TYPE_TIME
            for item in self.normalized_conditions
        )

    def activate(self, value: Any = None) -> None:
        """Activate the alarm."""
        self.last_value = value

        if self.state == STATE_NORMAL:
            self.activated_at = utcnow()
            self.acknowledged_at = None
            self.acknowledged_by = None
            self.acknowledged_by_user_id = None
            self.cleared_at = None
            self.trigger_value = value

        self.state = STATE_ACTIVE

    def acknowledge(
        self,
        acknowledged_by: str | None = None,
        acknowledged_by_user_id: str | None = None,
    ) -> None:
        """Acknowledge the alarm."""
        if self.state == STATE_ACTIVE:
            self.state = STATE_ACKNOWLEDGED
            if self.acknowledged_at is None:
                self.acknowledged_at = utcnow()
            if acknowledged_by is not None:
                self.acknowledged_by = acknowledged_by
            if acknowledged_by_user_id is not None:
                self.acknowledged_by_user_id = acknowledged_by_user_id
        elif self.state == STATE_INACTIVE:
            if self.acknowledged_at is None:
                self.acknowledged_at = utcnow()
            if acknowledged_by is not None:
                self.acknowledged_by = acknowledged_by
            if acknowledged_by_user_id is not None:
                self.acknowledged_by_user_id = acknowledged_by_user_id
            self.state = STATE_NORMAL

    def clear(self) -> None:
        """Handle the alarm condition returning to normal."""
        if self.state == STATE_ACTIVE:
            self.state = STATE_INACTIVE
            self.cleared_at = utcnow()
        elif self.state == STATE_ACKNOWLEDGED:
            self.cleared_at = utcnow()
            self.state = STATE_NORMAL
        elif self.state == STATE_INACTIVE:
            return

    def reset(self) -> None:
        """Return the alarm to its normal state and clear lifecycle data."""
        self.state = STATE_NORMAL
        self.activated_at = None
        self.acknowledged_at = None
        self.acknowledged_by = None
        self.acknowledged_by_user_id = None
        self.cleared_at = None
        self.trigger_value = None
        self.condition_snapshot = {}

    @property
    def is_active(self) -> bool:
        """Return whether the alarm condition is currently active."""
        return self.state in (STATE_ACTIVE, STATE_ACKNOWLEDGED)

    @property
    def is_acknowledged(self) -> bool:
        """Return whether the alarm is acknowledged."""
        return self.state == STATE_ACKNOWLEDGED

    @property
    def is_inactive(self) -> bool:
        """Return whether the alarm is inactive but latched."""
        return self.state == STATE_INACTIVE

    @property
    def duration(self) -> float | None:
        """Return the alarm duration in seconds."""
        if self.activated_at is None:
            return None
        end_time = self.cleared_at or utcnow()
        return (end_time - self.activated_at).total_seconds()
