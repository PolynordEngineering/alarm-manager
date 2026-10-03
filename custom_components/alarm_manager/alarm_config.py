"""Alarm configuration for Alarm Manager."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AlarmConfig:
    """Configuration for an alarm.

    The legacy single-condition fields are retained for backwards
    compatibility. New alarms may additionally use ``conditions`` and
    ``logic`` to build multi-condition alarm expressions.
    """

    alarm_id: str
    name: str
    entity_id: str
    condition: str
    threshold: float | str | None
    severity: str
    delay: int = 0
    hysteresis: float = 0.0
    conditions: list[dict[str, Any]] = field(default_factory=list)
    logic: str = "all"
