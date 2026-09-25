"""Alarm configuration for Alarm Manager."""

from dataclasses import dataclass


@dataclass
class AlarmConfig:
    """Configuration for an alarm."""

    alarm_id: str
    name: str
    entity_id: str
    condition: str
    threshold: float | str | None
    severity: str
    delay: int = 0
    hysteresis: float = 0.0