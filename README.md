# Alarm Manager for Home Assistant

An alarm management integration for Home Assistant, inspired by industrial PLC and SCADA alarm systems.

Developed by **Polynord Engineering**.

## Features

* Create, edit and delete alarms through the Home Assistant UI.
* Monitor Home Assistant sensors and other entities.
* Configure thresholds, delays, hysteresis and severity.
* Industrial-style alarm lifecycle: Normal, Active, Acknowledged and Inactive.
* Acknowledge individual alarms or all alarms.
* View alarm history, timestamps and durations.
* Dedicated Alarm Manager dashboard.
* Persistent alarm configuration and history.

## Installation

### HACS (Custom Repository)

1. Open HACS in Home Assistant.
2. Add `https://github.com/PolynordEngineering/alarm-manager` as a custom repository of type **Integration**.
3. Download Alarm Manager.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add Integration**.
6. Search for **Alarm Manager** and complete the setup.

## Configuration

Open **Settings → Devices & services → Alarm Manager → Configure** to add, edit or delete alarms.

Each alarm can monitor a Home Assistant entity using conditions such as above, below, equal, not equal, on, off or unavailable.

## Alarm states

| State        | Description                                                    |
| ------------ | -------------------------------------------------------------- |
| Normal       | No active or unacknowledged alarm                              |
| Active       | Alarm condition is present and has not been acknowledged       |
| Acknowledged | Alarm condition is present and has been acknowledged           |
| Inactive     | Alarm condition has cleared but still requires acknowledgement |

## Development

Alarm Manager is an independent custom integration for Home Assistant.

Developed and maintained by [Polynord Engineering](https://github.com/PolynordEngineering).

## License

MIT License.
