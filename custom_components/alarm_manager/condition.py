"""Condition evaluation for Alarm Manager."""

from typing import Any

from .const import (
    CONDITION_ABOVE,
    CONDITION_BELOW,
    CONDITION_EQUAL,
    CONDITION_NOT_EQUAL,
    CONDITION_ON,
    CONDITION_OFF,
    CONDITION_UNAVAILABLE,
)


def evaluate_condition(
    state: Any,
    condition: str,
    threshold: Any = None,
) -> bool:
    """Evaluate an alarm condition against an entity state."""

    # Convert the state to a string for state-based conditions.
    state_str = str(state).lower()

    # Availability condition.
    if condition == CONDITION_UNAVAILABLE:
        return state_str in ("unavailable", "unknown")

    # Binary/state conditions.
    if condition == CONDITION_ON:
        return state_str == "on"

    if condition == CONDITION_OFF:
        return state_str == "off"

    # Numeric conditions require a valid threshold.
    if threshold is None:
        return False

    try:
        state_value = float(state)
        threshold_value = float(threshold)
    except (TypeError, ValueError):
        return False

    if condition == CONDITION_ABOVE:
        return state_value > threshold_value

    if condition == CONDITION_BELOW:
        return state_value < threshold_value

    if condition == CONDITION_EQUAL:
        return state_value == threshold_value

    if condition == CONDITION_NOT_EQUAL:
        return state_value != threshold_value

    return False