# Alarm Manager v0.2.2

Alarm Manager v0.2.2 focuses on operator workflow, SCADA-style alarm configuration and a cleaner notification experience.

## Highlights

- **Alarm Management** view inside Alarm Manager with all configured alarms, including NORMAL alarms.
- Direct **EDIT**, **DELETE** and **+ ADD ALARM** actions without navigating to Home Assistant integration settings.
- Improved one-click handling for **ACK** and **CLEAR**.
- Alarm History now updates immediately after operator actions.
- **ACK**, **CLEARED** and **NOT ACKED** are kept as distinct outcomes.
- More compact, modern Home Assistant alarm notifications.
- Multi-alarm notification summaries when several alarms are active, with **OPEN ALARM MANAGER**.
- Updated README screenshots for the current UI.

## Alarm lifecycle

- **ACTIVE → ACK** records operator acknowledgement.
- **ACTIVE → normal → INACTIVE** creates a latched occurrence.
- **INACTIVE → CLEAR** removes the current alarm and records **CLEARED** without adding an acknowledgement.
- An occurrence that has returned to normal but has not been acknowledged or cleared remains **NOT ACKED**.

## Upgrade

No migration is required from v0.2.1. Restart Home Assistant after updating.

If Home Assistant serves an older frontend bundle, perform a hard browser refresh (for example Ctrl+F5 on Windows).
