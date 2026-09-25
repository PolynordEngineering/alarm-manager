class AlarmManagerPanel extends HTMLElement {
  constructor() {
    super();

    this.attachShadow({ mode: "open" });

    this._hass = null;
    this._panel = null;
    this._unsubscribeStateChanges = null;

    this.shadowRoot.addEventListener(
      "click",
      async (event) => {
        const target = event.target;

        if (!(target instanceof Element)) {
          return;
        }

        const button = target.closest("button");

        if (!button || !this._hass) {
          return;
        }

        try {
          if (button.classList.contains("ack-button")) {
            const alarmId = button.dataset.alarmId;

            if (alarmId) {
              await this._acknowledge(alarmId);
            }

            return;
          }

          if (button.id === "ack-all-button") {
            await this._acknowledgeAll();
            return;
          }

          if (button.id === "clear-history-button") {
            await this._clearHistory();
          }
        } catch (error) {
          console.error(
            "Alarm Manager action failed",
            error
          );
        }
      }
    );
  }

  set hass(hass) {
    if (
      this._hass?.connection !==
      hass?.connection
    ) {
      this._unsubscribeStateChanges?.();
      this._unsubscribeStateChanges = null;
    }

    this._hass = hass;

    this._subscribeToStateChanges();

    this._render();
  }

  async _subscribeToStateChanges() {
    if (
      this._unsubscribeStateChanges ||
      !this._hass?.connection
    ) {
      return;
    }

    this._unsubscribeStateChanges =
      await this._hass.connection.subscribeEvents(
        (event) => {
          const entityId =
            event.data?.entity_id;

          if (!entityId) {
            return;
          }

          if (
            entityId ===
              "sensor.alarm_history" ||
            (
              entityId.startsWith("sensor.") &&
              event.data?.new_state?.attributes
                ?.alarm_id
            )
          ) {
            this._render();
          }
        },
        "state_changed"
      );
  }

  disconnectedCallback() {
    this._unsubscribeStateChanges?.();
    this._unsubscribeStateChanges = null;
  }

  set panel(panel) {
    this._panel = panel;
    this._render();
  }

  _getAlarms() {
    if (!this._hass) {
      return [];
    }

    return Object.values(
      this._hass.states
    )
      .filter((state) => {
        return (
          state.entity_id.startsWith(
            "sensor."
          ) &&
          state.attributes &&
          state.attributes.alarm_id
        );
      })
      .sort((a, b) => {
        const severityOrder = {
          critical: 0,
          alarm: 1,
          warning: 2,
          info: 3,
        };

        const severityA =
          severityOrder[
            a.attributes?.severity
          ] ?? 99;

        const severityB =
          severityOrder[
            b.attributes?.severity
          ] ?? 99;

        if (severityA !== severityB) {
          return severityA - severityB;
        }

        return (
          a.attributes?.name ||
          a.entity_id
        ).localeCompare(
          b.attributes?.name ||
          b.entity_id
        );
      });
  }

  _getCurrentAlarms() {
    return this._getAlarms().filter(
      (alarm) =>
        alarm.state === "active" ||
        alarm.state === "acknowledged" ||
        alarm.state === "inactive"
    );
  }

  _getActiveAlarms() {
    return this._getAlarms().filter(
      (alarm) =>
        alarm.state === "active" ||
        alarm.state === "acknowledged"
    );
  }

  _getInactiveAlarms() {
    return this._getAlarms().filter(
      (alarm) =>
        alarm.state === "inactive"
    );
  }

  _getUnacknowledgedAlarms() {
    return this._getAlarms().filter(
      (alarm) =>
        alarm.state === "active"
    );
  }

  _getAcknowledgedAlarms() {
    return this._getAlarms().filter(
      (alarm) =>
        alarm.state === "acknowledged"
    );
  }

  _getHistory() {
    if (!this._hass) {
      return [];
    }

    const historyEntity =
      this._hass.states[
        "sensor.alarm_history"
      ];

    if (!historyEntity) {
      return [];
    }

    return (
      historyEntity.attributes?.history ||
      []
    );
  }

  _countSeverity(severity) {
    return this._getCurrentAlarms().filter(
      (alarm) =>
        alarm.attributes?.severity ===
        severity
    ).length;
  }

  _severityIcon(severity) {
    const common =
      'viewBox="0 0 24 24" aria-hidden="true" focusable="false"';

    switch (severity) {
      case "critical":
        return `
          <svg class="severity-icon" ${common}>
            <path
              d="M12 2.5 21.5 8v8L12 21.5 2.5 16V8L12 2.5Z"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linejoin="round"
            />
            <path
              d="M12 7v7"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
            <circle
              cx="12"
              cy="17"
              r="1.2"
              fill="currentColor"
            />
          </svg>
        `;

      case "alarm":
        return `
          <svg class="severity-icon" ${common}>
            <path
              d="M7.2 10.2a4.8 4.8 0 0 1 9.6 0v4.2l1.8 2.1H5.4l1.8-2.1v-4.2Z"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linejoin="round"
            />
            <path
              d="M9.5 19h5"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
            <path
              d="M5 6 3.5 4.5M19 6l1.5-1.5"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
          </svg>
        `;

      case "warning":
        return `
          <svg class="severity-icon" ${common}>
            <path
              d="m12 3 10 18H2L12 3Z"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linejoin="round"
            />
            <path
              d="M12 9v5"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
            <circle
              cx="12"
              cy="17"
              r="1.2"
              fill="currentColor"
            />
          </svg>
        `;

      case "info":
        return `
          <svg class="severity-icon" ${common}>
            <circle
              cx="12"
              cy="12"
              r="9"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            />
            <path
              d="M12 10.5v6"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
            <circle
              cx="12"
              cy="7.2"
              r="1.2"
              fill="currentColor"
            />
          </svg>
        `;

      default:
        return `
          <svg class="severity-icon" ${common}>
            <path
              d="m12 3 10 18H2L12 3Z"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linejoin="round"
            />
            <path
              d="M12 9v5"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            />
            <circle
              cx="12"
              cy="17"
              r="1.2"
              fill="currentColor"
            />
          </svg>
        `;
    }
  }

  _severityClass(severity) {
    return `severity-${
      severity || "warning"
    }`;
  }

  _conditionText(
    condition,
    threshold
  ) {
    switch (condition) {
      case "above":
        return `> ${threshold}`;

      case "below":
        return `< ${threshold}`;

      case "equal":
        return `= ${threshold}`;

      case "not_equal":
        return `≠ ${threshold}`;

      case "on":
        return "ON";

      case "off":
        return "OFF";

      case "unavailable":
        return "UNAVAILABLE";

      default:
        return "—";
    }
  }

  _formatDuration(seconds) {
    if (
      seconds === null ||
      seconds === undefined
    ) {
      return "—";
    }

    let remaining = Math.floor(
      Number(seconds)
    );

    if (Number.isNaN(remaining)) {
      return "—";
    }

    const hours = Math.floor(
      remaining / 3600
    );

    remaining %= 3600;

    const minutes = Math.floor(
      remaining / 60
    );

    const secondsValue =
      remaining % 60;

    if (hours > 0) {
      return `${hours}h ${String(
        minutes
      ).padStart(2, "0")}m`;
    }

    if (minutes > 0) {
      return `${minutes}m ${String(
        secondsValue
      ).padStart(2, "0")}s`;
    }

    return `${secondsValue}s`;
  }

  _formatDateTime(value) {
    if (!value) {
      return "—";
    }

    const date = new Date(value);

    if (
      Number.isNaN(date.getTime())
    ) {
      return "—";
    }

    return date.toLocaleString([], {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  async _acknowledge(alarmId) {
    if (!this._hass || !alarmId) {
      return;
    }

    await this._hass.callService(
      "alarm_manager",
      "acknowledge_alarm",
      {
        alarm_id: alarmId,
      }
    );
  }

  async _acknowledgeAll() {
    if (!this._hass) {
      return;
    }

    const unacknowledged =
      this._getUnacknowledgedAlarms();

    if (
      unacknowledged.length === 0
    ) {
      return;
    }

    await this._hass.callService(
      "alarm_manager",
      "acknowledge_all"
    );
  }

  async _clearHistory() {
    if (!this._hass) {
      return;
    }

    const history =
      this._getHistory();

    if (history.length === 0) {
      return;
    }

    const confirmed =
      window.confirm(
        `Clear all ${history.length} alarm history records? This cannot be undone.`
      );

    if (!confirmed) {
      return;
    }

    await this._hass.callService(
      "alarm_manager",
      "clear_history"
    );
  }

  _renderStatusCard(
    label,
    value,
    className = ""
  ) {
    return `
      <div class="status-card ${className}">
        <div class="status-value">
          ${value}
        </div>

        <div class="status-label">
          ${label}
        </div>
      </div>
    `;
  }

  _renderAlarmRow(alarm) {
    const attributes =
      alarm.attributes || {};

    const severity =
      attributes.severity ||
      "warning";

    const state =
      alarm.state || "normal";

    const acknowledged =
      state === "acknowledged";

    const inactive =
      state === "inactive";

    const currentValue =
      attributes.current_value ??
      "—";

    const threshold =
      this._conditionText(
        attributes.condition,
        attributes.threshold
      );

    const alarmId =
      attributes.alarm_id;

    let stateLabel = "ACTIVE";
    let stateClass = "state-active";

    if (acknowledged) {
      stateLabel = "ACKNOWLEDGED";
      stateClass =
        "state-acknowledged";
    } else if (inactive) {
      stateLabel = "INACTIVE";
      stateClass =
        "state-inactive";
    }

    return `
      <div class="
        alarm-row
        ${this._severityClass(
          severity
        )}
        ${
          acknowledged
            ? "acknowledged"
            : ""
        }
        ${
          inactive
            ? "inactive"
            : ""
        }
      ">

        <div class="alarm-severity-cell">
          <span class="severity-symbol">
            ${this._severityIcon(
              severity
            )}
          </span>

          <span class="severity-text">
            ${severity.toUpperCase()}
          </span>
        </div>

        <div class="alarm-name-cell">
          <div class="alarm-name">
            ${
              attributes.name ||
              alarm.entity_id
            }
          </div>

          <div class="alarm-entity">
            ${
              attributes.entity_id ||
              "—"
            }
          </div>
        </div>

        <div class="alarm-value-cell">
          <span class="current-value">
            ${currentValue}
          </span>

          <span class="threshold">
            ${threshold}
          </span>
        </div>

        <div class="alarm-trigger-cell">
          ${
            attributes.trigger_value ??
            "—"
          }
        </div>

        <div class="alarm-state-cell">
          <span class="
            state-badge
            ${stateClass}
          ">
            ${stateLabel}
          </span>
        </div>

        <div class="alarm-duration-cell">
          ${this._formatDuration(
            attributes.duration
          )}
        </div>

        <div class="alarm-time-cell">
          ${this._formatDateTime(
            attributes.activated_at
          )}
        </div>

        <div class="alarm-action-cell">

          ${
            inactive
              ? `
                  <button
                    class="ack-button"
                    data-alarm-id="${alarmId}"
                    ${
                      alarmId
                        ? ""
                        : "disabled"
                    }
                  >
                    ACK
                  </button>
                `
              : acknowledged
                ? `
                    <span class="
                      acknowledged-mark
                    ">
                      ✓ ACK
                    </span>
                  `
                : `
                    <button
                      class="ack-button"
                      data-alarm-id="${alarmId}"
                      ${
                        alarmId
                          ? ""
                          : "disabled"
                      }
                    >
                      ACK
                    </button>
                  `
          }

        </div>

      </div>
    `;
  }

  _renderHistoryRow(record) {
    const severity =
      record.severity ||
      "warning";

    const acknowledged =
      Boolean(
        record.acknowledged_at
      );

    return `
      <div class="history-row">

        <div class="history-severity">
          <span class="
            history-severity-symbol
            ${this._severityClass(
              severity
            )}
          ">
            ${this._severityIcon(
              severity
            )}
          </span>
        </div>

        <div class="history-alarm">

          <div class="history-name">
            ${
              record.name ||
              "Alarm"
            }
          </div>

          <div class="history-entity">
            ${
              record.entity_id ||
              "—"
            }
          </div>

        </div>

        <div class="history-trigger">
          ${
            record.trigger_value ??
            "—"
          }
        </div>

        <div class="history-duration">
          ${this._formatDuration(
            record.duration
          )}
        </div>

        <div class="history-activated">
          ${this._formatDateTime(
            record.activated_at
          )}
        </div>

        <div class="history-cleared">
          ${this._formatDateTime(
            record.cleared_at
          )}
        </div>

        <div class="history-ack">

          ${
            acknowledged
              ? `
                  <span class="
                    history-ack-ok
                  ">
                    ✓ ACK
                  </span>

                  <div class="
                    history-ack-time
                  ">
                    ${this._formatDateTime(
                      record.acknowledged_at
                    )}
                  </div>
                `
              : `
                  <span class="
                    history-ack-none
                  ">
                    NOT ACKED
                  </span>
                `
          }

        </div>

      </div>
    `;
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    if (!this._hass) {
      this.shadowRoot.innerHTML = `
        <div class="loading">
          Loading Alarm Manager...
        </div>
      `;

      return;
    }

    const alarms =
      this._getAlarms();

    const currentAlarms =
      this._getCurrentAlarms();

    const activeAlarms =
      this._getActiveAlarms();

    const inactiveAlarms =
      this._getInactiveAlarms();

    const unacknowledged =
      this._getUnacknowledgedAlarms();

    const acknowledged =
      this._getAcknowledgedAlarms();

    const history =
      this._getHistory()
        .slice()
        .reverse();

    const critical =
      this._countSeverity(
        "critical"
      );

    const alarmCount =
      this._countSeverity(
        "alarm"
      );

    const warning =
      this._countSeverity(
        "warning"
      );

    const info =
      this._countSeverity(
        "info"
      );

    this.shadowRoot.innerHTML = `
      <style>

        :host {
          display: block;
          width: 100%;
          min-height: 100%;

          font-family:
            var(
              --primary-font-family,
              sans-serif
            );

          color:
            var(
              --primary-text-color
            );
        }

        * {
          box-sizing: border-box;
        }

        .page {
          min-height: 100vh;

          background:
            var(
              --primary-background-color
            );
        }

        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;

          padding: 18px 24px;

          border-bottom:
            1px solid
            var(
              --divider-color
            );

          background:
            var(
              --card-background-color
            );
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .header-icon {
          width: 46px;
          height: 46px;

          display: flex;
          align-items: center;
          justify-content: center;

          overflow: hidden;

          border-radius: 8px;

          background:
            var(
              --secondary-background-color
            );
        }

        .header-logo {
          width: 100%;
          height: 100%;

          object-fit: contain;
        }

        .title {
          font-size: 20px;
          font-weight: 600;
        }

        .subtitle {
          margin-top: 3px;

          font-size: 11px;

          color:
            var(
              --secondary-text-color
            );
        }

        .status-area {
          display: flex;
          gap: 8px;
        }

        .status-card {
          min-width: 78px;

          padding: 8px 11px;

          border:
            1px solid
            var(
              --divider-color
            );

          border-radius: 6px;

          text-align: center;

          background:
            var(
              --secondary-background-color
            );
        }

        .status-value {
          font-size: 20px;
          line-height: 20px;
          font-weight: 700;
        }

        .status-label {
          margin-top: 4px;

          font-size: 8px;
          font-weight: 700;

          letter-spacing: 0.1em;

          color:
            var(
              --secondary-text-color
            );
        }

        .status-critical
          .status-value {
          color: #b71c1c;
        }

        .status-alarm
          .status-value {
          color: #d32f2f;
        }

        .status-warning
          .status-value {
          color: #f9a825;
        }

        .status-info
          .status-value {
          color: #1976d2;
        }

        .content {
          padding:
            22px
            24px
            40px;
        }

        .section {
          margin-bottom: 28px;
        }

        .section-header {
          display: flex;
          align-items: center;
          justify-content: space-between;

          margin-bottom: 9px;
        }

        .section-title {
          font-size: 11px;
          font-weight: 700;

          letter-spacing: 0.12em;

          color:
            var(
              --secondary-text-color
            );
        }

        .section-count {
          font-size: 10px;

          color:
            var(
              --secondary-text-color
            );
        }

        .section-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .toolbar-button {
          padding:
            7px
            12px;

          border:
            1px solid
            var(
              --divider-color
            );

          border-radius: 5px;

          cursor: pointer;

          background:
            var(
              --secondary-background-color
            );

          color:
            var(
              --primary-text-color
            );

          font-size: 9px;
          font-weight: 700;

          letter-spacing:
            0.05em;
        }

        .toolbar-button:hover {
          background:
            var(
              --primary-background-color
            );
        }

        .toolbar-button.primary {
          background:
            var(
              --primary-color
            );

          border-color:
            var(
              --primary-color
            );

          color: white;
        }

        .toolbar-button.danger {
          color: #c62828;
        }

        .toolbar-button:disabled {
          opacity: 0.4;
          cursor: default;
        }

        .alarm-table {
          overflow: hidden;

          border:
            1px solid
            var(
              --divider-color
            );

          border-radius: 6px;

          background:
            var(
              --card-background-color
            );
        }

        .alarm-table-header,
        .alarm-row {
          display: grid;

          grid-template-columns:
            105px
            minmax(190px, 1.6fr)
            minmax(120px, 0.9fr)
            90px
            115px
            85px
            155px
            72px;

          gap: 10px;

          align-items: center;
        }

        .alarm-table-header {
          padding:
            9px
            12px;

          background:
            var(
              --secondary-background-color
            );

          border-bottom:
            1px solid
            var(
              --divider-color
            );

          font-size: 8px;
          font-weight: 700;

          letter-spacing:
            0.1em;

          color:
            var(
              --secondary-text-color
            );
        }

        .alarm-row {
          position: relative;

          min-height: 62px;

          padding:
            9px
            12px
            9px
            16px;

          border-bottom:
            1px solid
            var(
              --divider-color
            );
        }

        .alarm-row:last-child {
          border-bottom: none;
        }

        .alarm-row::before {
          content: "";

          position: absolute;

          left: 0;
          top: 0;
          bottom: 0;

          width: 4px;
        }

        .severity-critical::before {
          background: #b71c1c;
        }

        .severity-alarm::before {
          background: #d32f2f;
        }

        .severity-warning::before {
          background: #f9a825;
        }

        .severity-info::before {
          background: #1976d2;
        }

        .alarm-row.acknowledged {
          opacity: 0.72;
        }

        .alarm-row.inactive {
          opacity: 0.78;
        }

        .alarm-severity-cell {
          display: flex;
          align-items: center;
          gap: 7px;
        }

        .severity-symbol {
          width: 20px;
          height: 20px;

          display: inline-flex;
          align-items: center;
          justify-content: center;

          flex: 0 0 20px;
        }

        .severity-icon {
          width: 18px;
          height: 18px;

          display: block;
        }

        .history-severity-symbol {
          width: 20px;
          height: 20px;

          display: inline-flex;
          align-items: center;
          justify-content: center;
        }

        .history-severity-symbol .severity-icon {
          width: 16px;
          height: 16px;
        }

        .severity-text {
          font-size: 8px;
          font-weight: 700;
          letter-spacing:
            0.08em;
        }

        .alarm-name {
          font-size: 12px;
          font-weight: 600;
        }

        .alarm-entity {
          margin-top: 3px;

          overflow: hidden;

          text-overflow: ellipsis;

          white-space: nowrap;

          font-size: 9px;

          color:
            var(
              --secondary-text-color
            );
        }

        .alarm-value-cell {
          display: flex;
          align-items: baseline;
          gap: 6px;
        }

        .current-value {
          font-size: 17px;
          font-weight: 700;
        }

        .threshold {
          font-size: 10px;

          color:
            var(
              --secondary-text-color
            );
        }

        .alarm-trigger-cell {
          font-size: 11px;
          font-weight: 600;
        }

        .state-badge {
          display: inline-block;

          padding:
            4px
            6px;

          border-radius: 4px;

          font-size: 8px;
          font-weight: 700;

          letter-spacing:
            0.05em;
        }

        .state-active {
          background:
            rgba(
              211,
              47,
              47,
              0.12
            );

          color: #d32f2f;
        }

        .state-acknowledged {
          background:
            rgba(
              46,
              125,
              50,
              0.12
            );

          color: #2e7d32;
        }

        .state-inactive {
          background:
            rgba(
              117,
              117,
              117,
              0.12
            );

          color: #757575;
        }

        .alarm-duration-cell,
        .alarm-time-cell {
          font-size: 9px;

          color:
            var(
              --secondary-text-color
            );
        }

        .ack-button {
          padding:
            6px
            10px;

          border:
            1px solid
            var(
              --divider-color
            );

          border-radius: 4px;

          background:
            var(
              --secondary-background-color
            );

          color:
            var(
              --primary-text-color
            );

          font-size: 9px;
          font-weight: 700;

          cursor: pointer;
        }

        .ack-button:hover {
          background:
            var(
              --primary-color
            );

          color: white;
        }

        .ack-button:disabled {
          opacity: 0.4;
          cursor: default;
        }

        .acknowledged-mark {
          font-size: 9px;
          font-weight: 700;

          color: #2e7d32;
        }

        .system-normal {
          display: flex;
          align-items: center;

          gap: 14px;

          padding: 28px;

          border:
            1px solid
            var(
              --divider-color
            );

          border-radius: 6px;

          background:
            var(
              --card-background-color
            );
        }

        .normal-icon {
          width: 42px;
          height: 42px;

          display: flex;
          align-items: center;
          justify-content: center;

          border-radius: 50%;

          background:
            rgba(
              46,
              125,
              50,
              0.12
            );

          color: #2e7d32;

          font-size: 20px;
          font-weight: 700;
        }

        .normal-title {
          font-size: 12px;
          font-weight: 700;
        }

        .normal-text {
          margin-top: 4px;

          font-size: 10px;

          color:
            var(
              --secondary-text-color
            );
        }

        .history-table {
          overflow: hidden;

          border:
            1px solid
            var(
              --divider-color
            );

          border-radius: 6px;

          background:
            var(
              --card-background-color
            );
        }

        .history-header,
        .history-row {
          display: grid;

          grid-template-columns:
            50px
            minmax(190px, 1.6fr)
            90px
            90px
            155px
            155px
            150px;

          gap: 10px;

          align-items: center;
        }

        .history-header {
          padding:
            9px
            12px;

          background:
            var(
              --secondary-background-color
            );

          border-bottom:
            1px solid
            var(
              --divider-color
            );

          font-size: 8px;
          font-weight: 700;

          letter-spacing:
            0.1em;

          color:
            var(
              --secondary-text-color
            );
        }

        .history-row {
          min-height: 54px;

          padding:
            8px
            12px;

          border-bottom:
            1px solid
            var(
              --divider-color
            );
        }

        .history-row:last-child {
          border-bottom: none;
        }

        .history-name {
          font-size: 11px;
          font-weight: 600;
        }

        .history-entity {
          margin-top: 2px;

          font-size: 8px;

          color:
            var(
              --secondary-text-color
            );
        }

        .history-trigger,
        .history-duration {
          font-size: 10px;
        }

        .history-activated,
        .history-cleared {
          font-size: 9px;

          color:
            var(
              --secondary-text-color
            );
        }

        .history-ack {
          font-size: 9px;
        }

        .history-ack-ok {
          font-weight: 700;
          color: #2e7d32;
        }

        .history-ack-none {
          font-weight: 700;

          color:
            var(
              --secondary-text-color
            );
        }

        .history-ack-time {
          margin-top: 2px;

          font-size: 8px;

          color:
            var(
              --secondary-text-color
            );
        }

        .no-history {
          padding: 24px;

          text-align: center;

          font-size: 11px;

          color:
            var(
              --secondary-text-color
            );
        }

        .loading {
          padding: 40px;

          text-align: center;
        }

        @media (max-width: 1100px) {
          .alarm-table-header,
          .alarm-row {
            grid-template-columns:
              90px
              minmax(160px, 1.5fr)
              100px
              80px
              110px
              80px
              130px
              65px;
          }

          .history-header,
          .history-row {
            grid-template-columns:
              40px
              minmax(160px, 1.5fr)
              80px
              80px
              120px
              120px
              120px;
          }
        }

        @media (max-width: 800px) {
          .header {
            align-items: flex-start;
            flex-direction: column;
            gap: 15px;
          }

          .status-area {
            width: 100%;
            flex-wrap: wrap;
          }

          .status-card {
            flex: 1;
            min-width: 90px;
          }

          .section-header {
            align-items: flex-start;
            flex-direction: column;
            gap: 8px;
          }

          .alarm-table-header,
          .history-header {
            display: none;
          }

          .alarm-row,
          .history-row {
            grid-template-columns:
              1fr
              1fr;

            gap: 10px;

            padding:
              14px
              14px
              14px
              18px;
          }
        }

        @media (max-width: 600px) {
          .header,
          .content {
            padding-left: 14px;
            padding-right: 14px;
          }

          .status-card {
            min-width:
              calc(50% - 4px);
          }

          .section-actions {
            width: 100%;
          }

          .toolbar-button {
            flex: 1;
          }
        }

      </style>

      <div class="page">

        <header class="header">

          <div class="header-left">

            <div class="header-icon">
              <img
                src="/alarm_manager/brand/icon.png"
                class="header-logo"
                alt="Alarm Manager"
              />
            </div>

            <div>

              <div class="title">
                Alarm Manager
              </div>

              <div class="subtitle">
                Industrial Alarm Management
              </div>

            </div>

          </div>

          <div class="status-area">

            ${this._renderStatusCard(
              "CRITICAL",
              critical,
              "status-critical"
            )}

            ${this._renderStatusCard(
              "ALARM",
              alarmCount,
              "status-alarm"
            )}

            ${this._renderStatusCard(
              "WARNING",
              warning,
              "status-warning"
            )}

            ${this._renderStatusCard(
              "INFO",
              info,
              "status-info"
            )}

            ${this._renderStatusCard(
              "CURRENT",
              currentAlarms.length
            )}

            ${this._renderStatusCard(
              "ACK",
              acknowledged.length
            )}

          </div>

        </header>

        <main class="content">

          <section class="section">

            <div class="section-header">

              <div class="section-title">
                CURRENT ALARMS
              </div>

              <div class="section-actions">

                <div class="section-count">
                  ${currentAlarms.length}
                  current /
                  ${unacknowledged.length}
                  unacknowledged /
                  ${inactiveAlarms.length}
                  inactive
                </div>

                <button
                  class="
                    toolbar-button
                    primary
                  "
                  id="ack-all-button"
                  ${
                    unacknowledged.length ===
                    0
                      ? "disabled"
                      : ""
                  }
                >
                  ACK ALL
                </button>

              </div>

            </div>

            ${
              currentAlarms.length === 0
                ? `
                    <div class="system-normal">

                      <div class="normal-icon">
                        ✓
                      </div>

                      <div>

                        <div class="normal-title">
                          SYSTEM NORMAL
                        </div>

                        <div class="normal-text">
                          No current alarms.
                        </div>

                      </div>

                    </div>
                  `
                : `
                    <div class="alarm-table">

                      <div class="
                        alarm-table-header
                      ">

                        <div>
                          SEVERITY
                        </div>

                        <div>
                          ALARM
                        </div>

                        <div>
                          VALUE / LIMIT
                        </div>

                        <div>
                          TRIGGER
                        </div>

                        <div>
                          STATE
                        </div>

                        <div>
                          DURATION
                        </div>

                        <div>
                          ACTIVATED
                        </div>

                        <div>
                          ACTION
                        </div>

                      </div>

                      ${currentAlarms
                        .map((alarm) =>
                          this._renderAlarmRow(
                            alarm
                          )
                        )
                        .join("")}

                    </div>
                  `
            }

          </section>

          <section class="section">

            <div class="section-header">

              <div class="section-title">
                ALARM HISTORY
              </div>

              <div class="section-actions">

                <div class="section-count">
                  ${history.length}
                  occurrences
                </div>

                <button
                  class="
                    toolbar-button
                    danger
                  "
                  id="clear-history-button"
                  ${
                    history.length === 0
                      ? "disabled"
                      : ""
                  }
                >
                  CLEAR HISTORY
                </button>

              </div>

            </div>

            ${
              history.length === 0
                ? `
                    <div class="no-history">
                      No completed alarm
                      occurrences.
                    </div>
                  `
                : `
                    <div class="history-table">

                      <div class="
                        history-header
                      ">

                        <div></div>

                        <div>
                          ALARM
                        </div>

                        <div>
                          TRIGGER
                        </div>

                        <div>
                          DURATION
                        </div>

                        <div>
                          ACTIVATED
                        </div>

                        <div>
                          CLEARED
                        </div>

                        <div>
                          ACKNOWLEDGEMENT
                        </div>

                      </div>

                      ${history
                        .map((record) =>
                          this._renderHistoryRow(
                            record
                          )
                        )
                        .join("")}

                    </div>
                  `
            }

          </section>

        </main>

      </div>
    `;
  }
}

if (
  !customElements.get(
    "alarm-manager-panel-v2"
  )
) {
  customElements.define(
    "alarm-manager-panel-v2",
    AlarmManagerPanel
  );
}