# Upgrading to Alarm Manager v0.2.0

## Before upgrading

Back up your Home Assistant configuration, especially:

```text
/config/.storage/
/config/custom_components/alarm_manager/
```

## What changes

v0.2.0 introduces a new condition model and a new visual editor.

Legacy single-condition alarms are normalized into the new model when loaded. The original alarm concept remains supported, while additional conditions can now be added.

## Recommended upgrade test

After restarting Home Assistant:

1. Open **Alarm Manager** from the sidebar.
2. Open an existing alarm.
3. Confirm the primary entity, operator and threshold are correct.
4. Add an additional condition and save.
5. Reopen the alarm and confirm the condition persisted.
6. Trigger the alarm and acknowledge it.
7. Return the underlying entity to normal and confirm the alarm clears.
8. Check History.
9. Open **Notifications** and verify notification targets.
10. Restart Home Assistant and verify alarms and history remain available.

## Service users

Existing service-based workflows should be tested after upgrading. v0.2.0 retains the service layer while expanding the underlying alarm model.
