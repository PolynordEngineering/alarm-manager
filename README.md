<div align="center">

# 🚨 Alarm Manager

### Industrial-style alarm management for Home Assistant

**Current version:** `0.1.7`

**Turn ordinary Home Assistant entities into managed alarms with lifecycle, acknowledgement, delay, hysteresis and history.**

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-blue?logo=home-assistant)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom%20Repository-41BDF5?logo=home-assistant)](https://hacs.xyz/)
[![Latest Release](https://img.shields.io/github/v/release/PolynordEngineering/alarm-manager?display_name=tag&sort=semver)](https://github.com/PolynordEngineering/alarm-manager/releases/latest)
[![License](https://img.shields.io/github/license/PolynordEngineering/alarm-manager)](https://github.com/PolynordEngineering/alarm-manager/blob/main/LICENSE)

</div>

---

## What is Alarm Manager?

**Alarm Manager** adds an industrial PLC/SCADA-style alarm layer to Home Assistant.

A Home Assistant sensor normally tells you what is happening **right now**. Alarm Manager adds the concept of an **alarm occurrence**: when a condition becomes abnormal, the alarm can activate, be acknowledged, remain visible after the condition clears, and finally return to normal. Completed occurrences are retained in alarm history.

This is useful for things such as:

- 🌡️ High or low temperatures
- ⚡ Electrical or energy conditions
- 🔌 Equipment and switch states
- 🌐 Availability / connectivity monitoring
- 🏠 Home automation faults
- 🏭 PLC, industrial and workshop monitoring
- 🚢 Marine and technical systems

> **Think of it as an alarm-management layer between your Home Assistant entities and the operator.**

---

## ✨ Features

| Feature | Description |
|---|---|
| **Alarm lifecycle** | Normal → Active → Acknowledged → Inactive → Normal |
| **Acknowledgement** | Acknowledge individual alarms or all active alarms |
| **Alarm history** | Keep completed alarm occurrences with timestamps and duration |
| **Activation delay** | Require a condition to remain abnormal before activating |
| **Hysteresis** | Reduce alarm chatter around numeric thresholds |
| **Severity** | Info, Warning, Alarm and Critical |
| **Multiple conditions** | Above, Below, Equal, Not equal, On, Off and Unavailable |
| **UI configuration** | Add, edit and delete alarms from Home Assistant |
| **Dedicated panel** | View current alarms and history in the Alarm Manager panel |
| **Persistent configuration** | Alarm definitions and history survive restarts |
| **Entity cleanup** | Removed alarms are cleaned from the Home Assistant entity registry |
| **Services** | Create, acknowledge, clear history and remove alarms programmatically |

---

# 🚀 Installation

## HACS — Custom Repository

Alarm Manager is currently distributed as a **HACS custom repository**.

### 1. Add the repository

In Home Assistant:

**HACS → Integrations → ⋮ → Custom repositories**

Add:

```text
https://github.com/PolynordEngineering/alarm-manager
```

Set the type to:

```text
Integration
```

### 2. Download Alarm Manager

Find **Alarm Manager** in HACS and select **Download**.

### 3. Restart Home Assistant

Restart Home Assistant after the download has completed.

### 4. Add the integration

Go to:

**Settings → Devices & services → Add Integration → Alarm Manager**

Complete the setup flow.

No YAML configuration is required.

---

# 🛠️ Creating your first alarm

Once Alarm Manager is installed:

**Settings → Devices & services → Alarm Manager → Configure**

Choose:

**Add Alarm**

You will be asked for the alarm configuration.

## Alarm fields

### Name

The name operators will see for the alarm.

Example:

```text
Boiler Return Temperature High
```

### Entity

The Home Assistant entity that should be monitored.

For example:

```text
sensor.boiler_return_temperature
```

### Condition

Defines when the entity is considered abnormal.

Available conditions:

| Condition | Meaning |
|---|---|
| **Above** | Value is above the threshold |
| **Below** | Value is below the threshold |
| **Equal** | Value equals the threshold |
| **Not equal** | Value does not equal the threshold |
| **On** | Entity is in the `on` state |
| **Off** | Entity is in the `off` state |
| **Unavailable** | Entity is unavailable |

Numeric conditions use the **Threshold** field.

### Threshold

The numeric value used by **Above**, **Below**, **Equal** and **Not equal**.

Example:

```text
60
```

### Severity

Choose the severity shown for the alarm:

- **Info**
- **Warning**
- **Alarm**
- **Critical**

Severity is metadata for the alarm and can be used by the frontend or future automations to distinguish importance.

### Activation Delay

The number of seconds the abnormal condition must remain active before the alarm becomes **Active**.

Example:

```text
30 seconds
```

This is useful when a sensor may briefly cross a limit and return to normal.

### Hysteresis

Hysteresis helps prevent an alarm from repeatedly switching state when a value moves around a threshold.

For example, a high-temperature alarm can use a hysteresis value so that small fluctuations around the limit do not cause unnecessary alarm chatter.

---

---

# 🔔 Notifications

Alarm Manager can notify operators when an alarm becomes **Active**.

Notifications support:

- Persistent Home Assistant notifications
- Mobile notifications through Home Assistant `notify` services
- Multiple named notification targets
- Severity-based notification routing
- Separate notification targets for different recipients or devices
- Direct links from notifications to the Alarm Manager panel

## Notification targets

Notification targets are configured from:

**Settings → Devices & services → Alarm Manager → Configure → Notifications**

A target consists of:

- **Name** — a friendly name such as `Admin`, `Engineer` or `Operator`
- **Service** — the Home Assistant notification service to use

Example:

| Target | Home Assistant service |
|---|---|
| Admin | `notify.mobile_app_admin` |
| Engineer | `notify.mobile_app_engineer` |
| Operator | `notify.mobile_app_operator` |

## Severity routing

Notification targets can be assigned to alarm severities.

For example:

| Severity | Notification targets |
|---|---|
| Info | Admin |
| Warning | Admin |
| Alarm | Admin, Engineer |
| Critical | Admin, Engineer, Operator |

The actual routing is configured by the user in Alarm Manager.

Persistent Home Assistant notifications remain available until dismissed, while configured mobile notification services can notify operators on their devices.


# 🌡️ Example: high-temperature alarm

Suppose you have:

```text
Entity:      sensor.boiler_return_temperature
Condition:   Above
Threshold:   60 °C
Severity:    Alarm
Delay:       30 seconds
Hysteresis: 1 °C
```

The behavior is:

```text
Temperature normal
        │
        │ rises above limit
        ▼
  Delay starts
        │
        │ remains abnormal for 30 s
        ▼
     🔴 ACTIVE
        │
        │ operator acknowledges
        ▼
  🟠 ACKNOWLEDGED
        │
        │ temperature returns to normal
        ▼
     🟢 NORMAL
```

If the condition clears **before the activation delay expires**, the alarm does not become active.

---

# 🔄 Alarm lifecycle

Alarm Manager uses four primary states.

```text
                         Condition abnormal
                                │
                                ▼
                         ┌─────────────┐
                         │    ACTIVE   │
                         └──────┬──────┘
                                │
                           Acknowledge
                                │
                                ▼
                     ┌──────────────────┐
                     │  ACKNOWLEDGED    │
                     └────────┬─────────┘
                              │
                       Condition clears
                              │
                              ▼
                         ┌──────────┐
                         │  NORMAL  │
                         └──────────┘
```

There is also an **Inactive** state for alarms that have cleared but still require acknowledgement:

```text
ACTIVE
  │
  │ condition clears
  ▼
INACTIVE
  │
  │ acknowledge
  ▼
NORMAL
```

### What happens if the alarm returns?

If an **Inactive** alarm becomes abnormal again, Alarm Manager starts a **new occurrence**.

The new occurrence gets its own activation time and trigger information, while the previous occurrence remains in history.

This allows repeated alarm events to be treated as separate occurrences rather than one endlessly changing alarm.

---

# 🖥️ Alarm Manager panel

When the integration is loaded, Alarm Manager provides a dedicated panel in the Home Assistant sidebar.

The panel is designed to give you an operator-style view of:

- Current **Active** alarms
- **Acknowledged** alarms
- **Inactive** alarms awaiting acknowledgement
- Alarm severity
- Alarm duration
- Alarm history
- Acknowledgement actions
- Acknowledgement user
- Notification status

The panel updates as alarm states change.

---

# 📚 Alarm history

Completed alarm occurrences are stored in Alarm Manager history.

History can be used to review when alarms occurred and how long the occurrence lasted.

History is separate from the current alarm state, so a completed occurrence remains available even after the alarm has returned to normal.

Alarm history also records the Home Assistant user who acknowledged an alarm, allowing operators to see who performed the acknowledgement.

The integration also provides a **Clear Alarm History** service for permanently removing completed occurrences.

---

# ⚙️ Services

Alarm Manager exposes the following Home Assistant services.

| Service | Purpose |
|---|---|
| `alarm_manager.create_alarm` | Create and start monitoring a new alarm |
| `alarm_manager.acknowledge_alarm` | Acknowledge one alarm |
| `alarm_manager.acknowledge_all` | Acknowledge all currently active, unacknowledged alarms |
| `alarm_manager.clear_history` | Permanently clear completed alarm history |
| `alarm_manager.remove_alarm` | Permanently remove an alarm and stop monitoring it |

These services make Alarm Manager usable from automations, scripts and other Home Assistant workflows.

For the exact service fields and selectors, see `custom_components/alarm_manager/services.yaml`.

---

# 🧩 Example automation concept

Because Alarm Manager exposes standard Home Assistant services, an automation can create or acknowledge alarms as part of a larger workflow.

For example, a future workflow could:

```text
Sensor / PLC condition
        ↓
Home Assistant automation
        ↓
alarm_manager.create_alarm
        ↓
Alarm Manager
        ↓
Operator acknowledgement
```

The integration itself does not require YAML configuration for normal setup.

---

# 🏗️ Architecture

Alarm Manager is built as a native Home Assistant custom integration.

```text
Home Assistant entity
        │
        ▼
   Entity Monitor
        │
        ▼
   Alarm Condition
        │
        ▼
    Alarm Manager
        │
   ┌────┴───────────────┐
   ▼                    ▼
Alarm Entity       Alarm History
   │                    │
   └────────┬───────────┘
            ▼
     Alarm Manager Panel
```

Alarm definitions and history are persisted by the integration, allowing them to survive Home Assistant restarts.

---

---

# 🆕 What's new in 0.1.7

Version **0.1.7** adds the first complete notification and operator-acknowledgement workflow:

- 🔔 Persistent Home Assistant alarm notifications
- 📱 Mobile notification support through Home Assistant `notify` services
- 👥 Multiple notification targets
- 🚨 Severity-based notification routing
- 👤 Home Assistant user shown for alarm acknowledgement
- 📚 Acknowledgement user retained in alarm history
- ⚙️ Improved notification configuration workflow
- 🛠️ Improved Alarm Manager settings navigation
- 💾 Fixed notification settings persistence
- 🔄 Improved configuration-flow handling


# 🔧 Development

Repository:

**https://github.com/PolynordEngineering/alarm-manager**

The integration lives under:

```text
custom_components/alarm_manager/
```

The repository also contains:

```text
frontend/       Alarm Manager panel
translations/   Home Assistant translations
brand/          Integration branding
```

Issues and feature requests:

**https://github.com/PolynordEngineering/alarm-manager/issues**

---

# 🗺️ Roadmap

Alarm Manager is actively being developed. Possible future improvements include:

- More operator controls
- Expanded alarm filtering
- Improved severity visualization
- More history analysis
- Additional notification and automation helpers
- Further HACS and Home Assistant integration polish

The roadmap may change as the project evolves.

---

# 📄 License

Alarm Manager is released under the **MIT License**.

Copyright © 2026 **Polynord Engineering**.

---

<div align="center">

**Alarm Manager**

*Industrial alarm management for Home Assistant.*

Built by **Polynord Engineering**

</div>
