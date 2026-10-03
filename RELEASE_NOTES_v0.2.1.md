# Alarm Manager v0.2.1

## Highlights

v0.2.1 is a refinement release following v0.2.0. It focuses on making the alarm lifecycle and configuration UI clearer and less ambiguous.

### Alarm lifecycle

- Inactive, unacknowledged alarms now show **CLEAR** instead of **ACK**.
- CLEAR removes the latched inactive alarm from Current Alarms without recording an acknowledgement.
- History therefore correctly remains **NOT ACKED** when the operator never acknowledged the alarm.
- Active alarms continue to use **ACK**, which records the Home Assistant user when available.

### Alarm editor

The Add/Edit Alarm UI is now organized as:

1. **Alarm** — name and severity
2. **When** — primary alarm trigger
3. **Additional conditions** — optional AND/OR logic
4. **Then do** — activation delay and alarm activation

The duplicate top-level hysteresis field has been removed. Condition delay and hysteresis remain attached to their respective conditions.

### Sidebar

The separate **Notifications** sidebar item has been removed. Notification targets, routing and the default notification service remain available inside the main Alarm Manager panel.

## Upgrade

Restart Home Assistant after updating so the integration and frontend are reloaded.

If the old frontend remains visible, perform a browser hard refresh.

