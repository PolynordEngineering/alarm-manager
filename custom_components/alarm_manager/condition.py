"""Condition evaluation for Alarm Manager."""

from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    CONDITION_ABOVE,
    CONDITION_AFTER,
    CONDITION_BELOW,
    CONDITION_BETWEEN,
    CONDITION_BEFORE,
    CONDITION_EQUAL,
    CONDITION_NOT_EQUAL,
    CONDITION_OFF,
    CONDITION_ON,
    CONDITION_TYPE_ENTITY,
    CONDITION_TYPE_TIME,
    CONDITION_UNAVAILABLE,
    LOGIC_ALL,
)


def evaluate_condition(state: Any, condition: str, threshold: Any = None) -> bool:
    """Evaluate an alarm condition against an entity state."""
    state_str = str(state).lower()
    if condition == CONDITION_UNAVAILABLE:
        return state_str in ("unavailable", "unknown")
    if condition == CONDITION_ON:
        return state_str == "on"
    if condition == CONDITION_OFF:
        return state_str == "off"
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


def _parse_time(value: Any) -> time | None:
    """Parse HH:MM or HH:MM:SS into a time object."""
    if isinstance(value, time):
        return value
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def evaluate_time_condition(
    condition: str,
    start_time: Any = None,
    end_time: Any = None,
    now: datetime | None = None,
) -> bool:
    """Evaluate a local-time alarm condition."""
    current = (now or dt_util.now()).time()
    start = _parse_time(start_time)
    end = _parse_time(end_time)

    if start is None:
        return False

    if condition == CONDITION_AFTER:
        return current >= start
    if condition == CONDITION_BEFORE:
        return current < start
    if condition == CONDITION_BETWEEN:
        if end is None:
            return False
        if start <= end:
            return start <= current < end
        # Overnight window, e.g. 21:00 -> 06:00.
        return current >= start or current < end
    return False


def evaluate_alarm_conditions(
    hass,
    conditions: list[dict[str, Any]],
    logic: str = LOGIC_ALL,
    runtime: dict[str, dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> tuple[bool, dict[str, Any], float | None]:
    """Evaluate conditions, including per-condition delay and hysteresis.

    Returns the combined result, a diagnostic snapshot, and the number of
    seconds until the next delayed condition should be re-evaluated.
    """
    results: list[bool] = []
    snapshot: dict[str, Any] = {}
    runtime = runtime if runtime is not None else {}
    current_dt = now or dt_util.now()
    next_delay: float | None = None

    for index, item in enumerate(conditions):
        condition_key = str(item.get("id") or f"condition_{index + 1}")
        runtime_item = runtime.setdefault(condition_key, {})
        condition_type = item.get("type", CONDITION_TYPE_ENTITY)
        key = item.get("entity_id") or condition_key

        raw_result = False
        state_value: Any = None
        threshold = item.get("threshold")
        hysteresis = max(0.0, float(item.get("hysteresis") or 0.0))

        if condition_type == CONDITION_TYPE_TIME:
            raw_result = evaluate_time_condition(
                str(item.get("condition", CONDITION_AFTER)),
                item.get("start_time") or item.get("time"),
                item.get("end_time"),
                current_dt,
            )
        else:
            entity_id = item.get("entity_id")
            state = hass.states.get(entity_id) if entity_id else None
            state_value = state.state if state is not None else "unavailable"
            raw_result = evaluate_condition(
                state_value,
                str(item.get("condition", "")),
                threshold,
            )

            # Hysteresis is meaningful for numeric threshold conditions.
            if hysteresis > 0 and str(item.get("condition")) in {
                CONDITION_ABOVE,
                CONDITION_BELOW,
            }:
                try:
                    numeric_state = float(state_value)
                    numeric_threshold = float(threshold)
                except (TypeError, ValueError):
                    numeric_state = None
                    numeric_threshold = None

                if numeric_state is not None and numeric_threshold is not None:
                    latched = bool(runtime_item.get("hysteresis_active", False))
                    if str(item.get("condition")) == CONDITION_ABOVE:
                        if raw_result:
                            latched = True
                        elif latched:
                            latched = numeric_state > numeric_threshold - hysteresis
                    else:
                        if raw_result:
                            latched = True
                        elif latched:
                            latched = numeric_state < numeric_threshold + hysteresis
                    runtime_item["hysteresis_active"] = latched
                    raw_result = latched

        delay = max(0.0, float(item.get("delay") or 0.0))
        effective_result = raw_result

        if raw_result and delay > 0:
            true_since = runtime_item.get("true_since")
            if true_since is None:
                runtime_item["true_since"] = current_dt
                remaining = delay
            else:
                elapsed = max(0.0, (current_dt - true_since).total_seconds())
                remaining = max(0.0, delay - elapsed)

            if remaining > 0:
                effective_result = False
                next_delay = remaining if next_delay is None else min(next_delay, remaining)
        else:
            runtime_item.pop("true_since", None)

        snapshot[key] = {
            "type": condition_type,
            "state": state_value,
            "condition": item.get("condition"),
            "threshold": threshold,
            "delay": delay,
            "hysteresis": hysteresis,
            "raw_result": raw_result,
            "result": effective_result,
        }
        if condition_type == CONDITION_TYPE_TIME:
            snapshot[key].update({
                "start_time": item.get("start_time") or item.get("time"),
                "end_time": item.get("end_time"),
            })

        results.append(effective_result)

    if not results:
        return False, snapshot, None

    triggered = all(results) if logic == LOGIC_ALL else any(results)
    return triggered, snapshot, next_delay

