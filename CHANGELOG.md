# Changelog

All notable changes to Alarm Manager are documented here.

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
- Notification configuration now remains within the relevant settings menu after saving.
- Improved alarm acknowledgement handling.
- Improved alarm history acknowledgement information.
- Improved notification routing configuration.
- Improved overall integration settings usability.

### Fixed

- Fixed notification settings not persisting correctly.
- Fixed notification targets being lost when leaving the configuration flow.
- Fixed configuration flow steps unintentionally overwriting existing notification options.
- Fixed acknowledgement information not being retained correctly in alarm history.

---

## [0.1.6] - 2026-09-25

### Added

- Initial HACS test release.
- Verified HACS automatic update detection and release workflow.

### Alarm Manager v0.1.6

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

---

## [0.1.3] - 2026-09-25

### Added

- Added the **Delete Alarm** option to the Alarm Manager configuration flow.
- Added support for deleting configured alarms directly through the Home Assistant UI.

### Improved

- Improved the configuration flow menu structure.
- Improved alarm entity cleanup when alarms are deleted.
- Improved handling of stale Alarm Manager entities in the Home Assistant entity registry.
- Updated the Alarm Manager frontend to work with the current alarm and history lifecycle.

---

## [0.1.2] - 2026-09-25

### Added

- Complete modernized README with installation, configuration and alarm lifecycle documentation.
- Detailed explanation of alarm states and occurrence handling.
- Documentation for all alarm conditions, severity levels, delay and hysteresis.
- Service reference and development information.
- Changelog for release tracking.

### Improved

- Repository presentation and onboarding documentation.
- Explanation of how to create and operate alarms from the Home Assistant UI.
- Prepared the repository for HACS distribution and GitHub releases.

---

## [0.1.1]

### Added

- Initial published repository version.