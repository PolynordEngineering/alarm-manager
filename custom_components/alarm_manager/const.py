"""Constants for Alarm Manager."""

DOMAIN = "alarm_manager"

# Configuration
CONF_NAME = "name"
CONF_ENTITY_ID = "entity_id"
CONF_CONDITION = "condition"
CONF_THRESHOLD = "threshold"
CONF_SEVERITY = "severity"
CONF_DELAY = "delay"
CONF_HYSTERESIS = "hysteresis"

# Conditions
CONDITION_ABOVE = "above"
CONDITION_BELOW = "below"
CONDITION_EQUAL = "equal"
CONDITION_NOT_EQUAL = "not_equal"
CONDITION_ON = "on"
CONDITION_OFF = "off"
CONDITION_UNAVAILABLE = "unavailable"

# Severity
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ALARM = "alarm"
SEVERITY_CRITICAL = "critical"

# Alarm states
STATE_NORMAL = "normal"
STATE_ACTIVE = "active"
STATE_ACKNOWLEDGED = "acknowledged"
STATE_INACTIVE = "inactive"

# Legacy state retained for backwards compatibility with older stored data.
STATE_CLEARED = "cleared"

# Internal dispatcher signals
SIGNAL_ALARM_UPDATED = f"{DOMAIN}_alarm_updated"