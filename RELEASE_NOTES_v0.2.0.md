# Alarm Manager v0.2.0

Alarm Manager v0.2.0 is the first major release of the new alarm configuration model.

## Highlights

- New Automation-style alarm editor
- Primary alarm entity + optional additional conditions
- ALL / ANY condition logic
- Entity and time conditions
- Per-condition delay and hysteresis
- Conditionless/manual alarms
- Dedicated Alarm Manager and Notifications sidebar pages
- Notification targets and severity routing
- Mobile navigation and safe-area fixes
- History severity filtering
- Improved alarm-state reconciliation and clearing
- Improved persistence of edited conditions

## Upgrade notes

Existing v0.1.x single-condition alarms are normalized into the new condition model when loaded. Keep a backup of your Home Assistant configuration before upgrading a production system.

The v0.2.0 visual editor is the recommended configuration interface.

## Testing focus

Before production use, test existing alarms, notifications, acknowledgement, history, restart persistence, mobile UI and any automations that call Alarm Manager services.
