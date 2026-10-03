# Changelog

All notable changes to Alarm Manager are documented here.

## [0.2.1] - 2026-10-03

### Added

- Added `alarm_manager.clear_alarm` to clear an inactive, unacknowledged alarm without recording an acknowledgement.

### Improved

- Changed the Current Alarms action for inactive, unacknowledged alarms from **ACK** to **CLEAR**.
- Preserved **NOT ACKED** in history when an inactive alarm is cleared without acknowledgement.
- Reworked the Add/Edit Alarm editor so the primary alarm trigger is clearly separated from optional additional conditions.
- Removed the duplicate top-level hysteresis field from the editor.
- Moved **Activation Delay** into the **Then do → Activate alarm** section.
- Kept condition delay and condition hysteresis with the individual primary/additional condition where they belong.
- Removed the separate **Notifications** sidebar item; notification targets and routing remain available inside Alarm Manager.
- Bumped the frontend cache version to ensure the updated panel is loaded after upgrade.

### Fixed

- Fixed the misleading inactive-alarm action that could cause an operator to record an acknowledgement merely to remove an already-inactive alarm from Current Alarms.
- Fixed the editor layout ambiguity around the primary alarm entity and the two different types of delay.

### Notes

- v0.2.1 is a refinement release following v0.2.0.
- Existing v0.2.0 alarm configurations remain supported.
- The separate Notifications panel route is no longer registered in the Home Assistant sidebar.


## [0.2.0] - 2026-09-28

### Added

- Added a new Automation-style Alarm Manager frontend editor.
- Added dedicated Alarm Manager sidebar navigation for day-to-day alarm management.
- Added dedicated Notifications sidebar navigation.
- Added primary alarm entity configuration directly in the alarm editor.
- Added optional additional alarm conditions.
- Added `ALL` / `ANY` condition logic.
- Added entity conditions for above, below, equal, not equal, on, off, unavailable and unknown states.
- Added time conditions for after, before and between time windows.
- Added overnight time-window support.
- Added per-condition activation delay.
- Added per-condition hysteresis for numeric conditions.
- Added conditionless/manual alarms.
- Added `alarm_manager.trigger_alarm` for externally triggered alarms.
- Added editable and removable condition cards in the alarm editor.
- Added notification target management from the Alarm Manager frontend.
- Added default notification service management from the Alarm Manager frontend.
- Added severity-based notification routing in the dedicated Notifications page.
- Added mobile safe-area handling for Alarm Manager editors.
- Added mobile Home Assistant sidebar navigation from the Alarm Manager panel.
- Added severity filtering to Alarm History.
- Added current value / limit presentation for primary numeric alarm conditions.
- Added alarm-condition reconciliation to prevent stale active alarm occurrences.

### Improved

- Reworked alarm creation and editing so the complete configuration is visible in one screen.
- Made the primary alarm entity the first-class alarm definition instead of forcing users through a separate condition workflow.
- Improved editing of existing alarms and persistence of additional conditions.
- Improved condition evaluation and lifecycle reconciliation.
- Improved alarm clearing after conditions return to normal.
- Improved notification configuration workflow.
- Improved mobile usability of the custom panel.
- Improved history filtering so the severity selector does not interrupt the panel rendering.
- Improved acknowledgement handling and operator tracking.
- Preserved compatibility with legacy single-condition alarms by normalizing them into the new condition model.

### Fixed

- Fixed additional conditions not persisting after editing an alarm.
- Fixed notification settings causing the Alarm Manager sidebar panel to disappear after saving.
- Fixed editor fields losing focus while typing.
- Fixed mobile Back and Save controls being obscured by the device safe area.
- Fixed the Alarm Manager mobile sidebar button being missing.
- Fixed primary numeric alarm limits being displayed as zero/legacy values when the configured threshold was stored in the condition model.
- Fixed stale active alarms not being re-evaluated and cleared when conditions returned to normal.
- Fixed the History severity dropdown being destroyed while the user was attempting to select an option.
- Fixed a frontend history rendering error that could produce a blank Alarm Manager page.

### Notes

- v0.2.0 introduces a significantly expanded condition model. Existing legacy single-condition alarms are normalized for compatibility.
- History currently has no automatic retention limit; records remain until cleared by the user.
- The visual editor is the recommended configuration path. Service schemas remain available for automation and integration use cases.

### License

- Changed the project license from MIT to **PolyForm Noncommercial License 1.0.0** for v0.2.0 and later.
- Noncommercial use remains permitted under the license; commercial use, commercial deployment, commercial redistribution, resale, and commercial integration require a separate written license from Polynord Engineering.
- Earlier versions remain under the licenses under which they were originally distributed.

## [0.1.7] - 2026-09-26

### Added

- Added persistent Home Assistant notifications when an alarm becomes active.
- Added mobile notification support through Home Assistant `notify` services.
- Added support for multiple named notification targets.
- Added severity-based notification routing.
- Added notification target configuration through the Alarm Manager settings.
- Added notification target add, edit and delete functionality.
- Added Home Assistant user identification for alarm acknowledgements.
- Added acknowledgement user information to current alarms.
- Added acknowledgement user information to alarm history.
- Added acknowledgement user tracking for **Acknowledge All**.
- Added direct links from notifications to the Alarm Manager panel.

### Improved

- Improved the Alarm Manager configuration flow navigation.
- Improved the Notifications settings workflow.
- Improved alarm acknowledgement handling.
- Improved alarm history acknowledgement information.
- Improved notification routing configuration.
- Improved overall integration settings usability.

### Fixed

- Fixed notification settings not persisting correctly.
- Fixed notification targets being lost when leaving the configuration flow.
- Fixed configuration flow steps unintentionally overwriting existing notification options.
- Fixed acknowledgement information not being retained correctly in alarm history.

## [0.1.6] - 2026-09-25

### Added

- Initial HACS test release.
- Verified HACS automatic update detection and release workflow.

## [0.1.5] - 2026-09-25

### Test Release

- Test release for the HACS automatic update workflow.
- Verifies that Home Assistant detects a new Alarm Manager version through HACS.
- Verifies that the Home Assistant update dialog displays the installed version, latest version and release notes.
- Verifies that the integration can be updated directly from the Home Assistant update interface.

## [0.1.4] - 2026-09-25

### Fixed

- Fixed registration of the Alarm History sensor entity.
- Fixed Alarm History entity persistence across integration reloads and Home Assistant restarts.
- Fixed cleanup logic so the Alarm History entity is not removed when stale alarm entities are cleaned up.
- Improved the stability of the `sensor.alarm_history` entity used by the Alarm Manager frontend.

### Improved

- Alarm History now exposes the number of stored historical alarm occurrences as its state.
- Alarm History provides historical alarm records through the `history` entity attribute.
- Alarm History now updates automatically when alarm lifecycle or history changes occur.
- Explicitly maintained the `sensor.alarm_history` entity ID for reliable frontend integration.

## [0.1.3] - 2026-09-25

### Added

- Added the **Delete Alarm** option to the Alarm Manager configuration flow.
- Added support for deleting configured alarms directly through the Home Assistant UI.

### Improved

- Improved the configuration flow menu structure.
- Improved alarm entity cleanup when alarms are deleted.
- Improved handling of stale Alarm Manager entities in the Home Assistant entity registry.
- Updated the Alarm Manager frontend to work with the current alarm and history lifecycle.

## [0.1.2] - 2026-09-25

### Added

- Complete modernized README with installation, configuration and alarm lifecycle documentation.
- Detailed explanation of alarm states and occurrence handling.
- Documentation for alarm conditions, severity levels, delay and hysteresis.
- Service reference and development information.
- Changelog for release tracking.

### Improved

- Repository presentation and onboarding documentation.
- Explanation of how to create and operate alarms from the Home Assistant UI.
- Prepared the repository for HACS distribution and GitHub releases.

## [0.1.1]

### Added

- Initial published repository version.
