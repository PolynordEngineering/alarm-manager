# Alarm Manager v0.2.1

Alarm Manager v0.2.1 is a focused UI and usability update built on the v0.2.0 alarm model.

## Highlights

- Inactive, unacknowledged alarms now show **CLEAR** instead of **ACK**.
- CLEAR removes the inactive alarm from Current Alarms without recording an acknowledgement.
- Alarm History correctly remains **NOT ACKED** when an occurrence was never acknowledged.
- Removed the separate **Notifications** sidebar item.
- Notification targets and severity routing remain available inside Alarm Manager.
- Updated README screenshots to reflect the current UI.
- Bumped the frontend cache version.

## Upgrade notes

No migration is required for existing v0.2.0 alarm configurations.

After updating, restart Home Assistant. If the old Notifications sidebar item remains visible, refresh the browser with a hard reload (for example, Ctrl+F5 on Windows).

## Operator behavior

- **ACTIVE → ACK** records that an operator has acknowledged the alarm.
- **ACTIVE → normal** creates an inactive/latching occurrence.
- **INACTIVE → CLEAR** removes the current alarm without changing the occurrence's acknowledgement status.
- History therefore distinguishes between alarms that were acknowledged and alarms that were cleared without acknowledgement.
