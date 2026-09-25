"""Alarm object for Alarm Manager."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .const import (
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

    state: str = STATE_NORMAL

    activated_at: datetime | None = None
    acknowledged_at: datetime | None = None
    cleared_at: datetime | None = None

    last_value: Any = None
    trigger_value: Any = None

    def activate(self, value: Any = None) -> None:
        """Activate the alarm."""

        self.last_value = value

        # A new occurrence only starts when the alarm is in NORMAL.
        if self.state == STATE_NORMAL:
            self.activated_at = utcnow()
            self.acknowledged_at = None
            self.cleared_at = None
            self.trigger_value = value

        self.state = STATE_ACTIVE

    def acknowledge(self) -> None:
        """Acknowledge the alarm."""

        if self.state == STATE_ACTIVE:
            # The condition is still abnormal.
            #
            # ACTIVE -> ACKNOWLEDGED
            #
            # Keep all lifecycle timestamps so the manager can
            # eventually create a complete history record.
            self.state = STATE_ACKNOWLEDGED

            if self.acknowledged_at is None:
                self.acknowledged_at = utcnow()

        elif self.state == STATE_INACTIVE:
            # The condition has already returned to normal.
            #
            # INACTIVE -> NORMAL
            #
            # The occurrence is complete, but the manager must be
            # able to update its history record before the final reset.
            if self.acknowledged_at is None:
                self.acknowledged_at = utcnow()

            self.state = STATE_NORMAL

    def clear(self) -> None:
        """Handle the alarm condition returning to normal."""

        if self.state == STATE_ACTIVE:
            # The condition has returned to normal before the
            # operator acknowledged the alarm.
            #
            # ACTIVE -> INACTIVE
            #
            # The occurrence remains latched until acknowledged.
            self.state = STATE_INACTIVE
            self.cleared_at = utcnow()

        elif self.state == STATE_ACKNOWLEDGED:
            # The operator already acknowledged the alarm and the
            # condition has now returned to normal.
            #
            # ACKNOWLEDGED -> NORMAL
            #
            # Do NOT reset here. The manager needs the timestamps
            # to create the history record first.
            self.cleared_at = utcnow()
            self.state = STATE_NORMAL

        elif self.state == STATE_INACTIVE:
            # INACTIVE remains latched while the condition is normal.
            #
            # If the condition becomes abnormal again, the manager
            # will start a new occurrence.
            return

    def reset(self) -> None:
        """Return the alarm to its normal state and clear lifecycle data."""

        self.state = STATE_NORMAL
        self.activated_at = None
        self.acknowledged_at = None
        self.cleared_at = None
        self.trigger_value = None

    @property
    def is_active(self) -> bool:
        """Return whether the alarm condition is currently active."""

        return self.state in (
            STATE_ACTIVE,
            STATE_ACKNOWLEDGED,
        )

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

        return (
            end_time - self.activated_at
        ).total_seconds()