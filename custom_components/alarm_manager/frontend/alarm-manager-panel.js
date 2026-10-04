class AlarmManagerPanel extends HTMLElement {
  constructor() {
    super();

    this.attachShadow({ mode: "open" });

    this._hass = null;
    this._panel = null;
    this._unsubscribeStateChanges = null;
    this._builder = null;
    this._historySeverityFilter = "all";

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
          if (button.id === "mobile-menu-button") {
            this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
            return;
          }

          if (button.classList.contains("clear-alarm-button")) {
            const alarmId = button.dataset.alarmId;

            if (alarmId) {
              await this._clearInactiveAlarm(alarmId);
            }

            return;
          }

          if (button.classList.contains("ack-button")) {
            const alarmId = button.dataset.alarmId;

            if (alarmId) {
              await this._acknowledge(alarmId);
            }

            return;
          }

          if (button.id === "add-alarm-button") {
            this._openBuilder();
            return;
          }

          if (button.classList.contains("edit-alarm-button")) {
            const alarmId = button.dataset.alarmId;
            const alarm = this._getAlarms().find(
              (item) => item.attributes?.alarm_id === alarmId
            );
            if (alarm) {
              this._openBuilder(alarm);
            }
            return;
          }

          if (button.id === "add-target-button") { this._openTargetEditor(); return; }
          if (button.id === "save-default-notification-button") {
            if (!this._notificationSettings) { this._openDefaultNotificationEditor(); }
            else { await this._saveDefaultNotification(); }
            return;
          }
          if (button.id === "delete-alarm-button") { await this._deleteBuilderAlarm(); return; }
          if (button.classList.contains("notification-edit-button")) { const i=Number(button.dataset.targetIndex); const cfg=this._getNotificationConfig(); if(cfg.targets[i]) this._openTargetEditor(cfg.targets[i], i); return; }
          if (button.id === "save-target-button") { await this._saveTargetEditor(); return; }
          if (button.id === "delete-target-button") { await this._deleteTargetEditor(); return; }
          if (button.classList.contains("builder-close") && this._targetEditor) { this._targetEditor=null; this._render(); return; }

          if (button.classList.contains("builder-add-condition")) {
            this._builder?.conditions.push(this._defaultCondition());
            this._render();
            return;
          }

          if (button.classList.contains("builder-remove-condition")) {
            const index = Number(button.dataset.index);
            if (this._builder && this._builder.conditions.length > 0) {
              this._builder.conditions.splice(index, 1);
              this._render();
            }
            return;
          }

          if (button.id === "builder-cancel-button" || button.classList.contains("builder-close")) {
            this._builder = null;
            this._render();
            return;
          }

          if (button.id === "builder-save-button") {
            await this._saveBuilder();
            return;
          }

          if (button.classList.contains("builder-trigger-now")) {
            const alarmId = this._builder?.alarmId;
            if (alarmId) {
              await this._hass.callService("alarm_manager", "trigger_alarm", { alarm_id: alarmId });
              this._builder = null;
              this._render();
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

    this.shadowRoot.addEventListener("change", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) {
        return;
      }

      if (target.dataset.targetField && this._targetEditor) { this._targetEditor[target.dataset.targetField] = target.value; return; }
      if (target.dataset.targetSeverity && this._targetEditor) { this._targetEditor.routing[target.dataset.targetSeverity] = target.checked; return; }
      if (target.dataset.defaultNotification && this._notificationSettings) { this._notificationSettings.defaultService = target.value; return; }

      if (target.id === "history-severity-filter") {
        this._historySeverityFilter = target.value || "all";
        // Do not rebuild the whole panel while a native select is open.
        // Replacing the host DOM here causes the dropdown to close
        // immediately, especially on mobile. Update only the history section.
        this._updateHistorySection();
        return;
      }

      const primaryField = target.dataset.primaryField;
      if (primaryField && this._builder) {
        this._builder.primaryCondition = this._builder.primaryCondition || this._defaultPrimaryCondition();
        this._builder.primaryCondition[primaryField] = target.value;
        return;
      }

      const index = target.dataset.conditionIndex;
      const field = target.dataset.conditionField;

      if (index !== undefined && field && this._builder) {
        const condition = this._builder.conditions[Number(index)];
        if (condition) {
          condition[field] = target.value;
          if (field === "type") {
            this._builder.conditions[Number(index)] =
              target.value === "time"
                ? { type: "time", condition: "after", start_time: "21:00" }
                : { type: "entity", entity_id: "", condition: "above", threshold: 0 };
            this._render();
          } else if (field === "condition" && condition.type === "time") {
            this._render();
          }
        }
        return;
      }

      const generalField = target.dataset.builderField;
      if (generalField && this._builder) {
        this._builder[generalField] = target.value;
        // Only logic changes affect the visual connectors. Ordinary fields
        // deliberately do not re-render, so text entry never loses focus.
        if (generalField === "logic") this._render();
      }
    });

    this.shadowRoot.addEventListener("input", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement) || !this._builder) return;
      const primaryField = target.dataset.primaryField;
      if (primaryField) {
        this._builder.primaryCondition = this._builder.primaryCondition || this._defaultPrimaryCondition();
        this._builder.primaryCondition[primaryField] = target.value;
        return;
      }
      const index = target.dataset.conditionIndex;
      const field = target.dataset.conditionField;
      if (index !== undefined && field) {
        const condition = this._builder.conditions[Number(index)];
        if (condition) condition[field] = target.value;
        return;
      }
      const generalField = target.dataset.builderField;
      if (generalField) this._builder[generalField] = target.value;
    });
  }

  _isHistoryFilterFocused() {
    return this.shadowRoot?.activeElement?.id === "history-severity-filter";
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

    // Do not rebuild the DOM while the visual editor is open.
    // Home Assistant pushes a new `hass` object for many state changes;
    // rebuilding here steals focus from text fields and makes typing feel
    // like the editor is pressing Enter.
    if (!this._builder && !this._targetEditor && !this._isHistoryFilterFocused()) {
      this._render();
    }
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
            if (!this._builder && !this._targetEditor && !this._isHistoryFilterFocused()) {
              this._render();
            }
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

    const history = historyEntity.attributes?.history;
    return Array.isArray(history) ? history : [];
  }

  _getFilteredHistory() {
    const history = this._getHistory();
    const filter = String(this._historySeverityFilter || "all").toLowerCase();
    if (filter === "all") {
      return history;
    }
    return history.filter((record) =>
      String(record?.severity || "warning").toLowerCase() === filter
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
    threshold,
    conditions = [],
    logic = "all"
  ) {
    if (Array.isArray(conditions) && conditions.length > 1) {
      return `${String(logic).toUpperCase()} • ${conditions.length} conditions`;
    }
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

  _escape(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  _defaultCondition() {
    return {
      type: "entity",
      entity_id: "",
      condition: "above",
      threshold: 0,
      delay: 0,
      hysteresis: 0,
    };
  }

  _defaultPrimaryCondition() {
    return {
      type: "entity",
      entity_id: "",
      condition: "on",
      threshold: 0,
      delay: 0,
      hysteresis: 0,
    };
  }

  _openBuilder(alarm = null) {
    const attributes = alarm?.attributes || {};
    let sourceConditions = [];
    if (Array.isArray(attributes.conditions)) {
      sourceConditions = attributes.conditions.map((item) => ({ ...item }));
    }
    if (!sourceConditions.length && attributes.entity_id) {
      sourceConditions = [{
        type: "entity",
        entity_id: attributes.entity_id,
        condition: attributes.condition || "on",
        threshold: attributes.threshold ?? 0,
        delay: 0,
        hysteresis: 0,
      }];
    }

    const primaryIndex = sourceConditions.findIndex((item) => item.type === "entity");
    const primaryCondition = primaryIndex >= 0
      ? { ...sourceConditions[primaryIndex] }
      : this._defaultPrimaryCondition();
    const additionalConditions = primaryIndex >= 0
      ? sourceConditions.filter((_, index) => index !== primaryIndex).map((item) => ({ ...item }))
      : sourceConditions.map((item) => ({ ...item }));

    this._builder = {
      alarmId: attributes.alarm_id || null,
      name: attributes.name || "",
      entityId: attributes.entity_id || primaryCondition.entity_id || "",
      severity: attributes.severity || "warning",
      logic: attributes.logic || "all",
      delay: attributes.delay ?? 0,
      hysteresis: attributes.hysteresis ?? 0,
      primaryCondition,
      conditions: additionalConditions,
    };

    this._render();
  }

  _entityOptionsHtml(selected = "") {
    if (!this._hass) {
      return "";
    }

    const entities = Object.values(this._hass.states || {})
      .filter((state) => !state.attributes?.alarm_id)
      .sort((a, b) => a.entity_id.localeCompare(b.entity_id));

    return entities.map((state) => {
      const label = state.attributes?.friendly_name
        ? `${state.entity_id} — ${state.attributes.friendly_name}`
        : state.entity_id;
      const value = this._escape(state.entity_id);
      return `<option value="${value}">${this._escape(label)}</option>`;
    }).join("");
  }

  _conditionLabel(condition) {
    const labels = {
      above: "is above",
      below: "is below",
      equal: "equals",
      not_equal: "is not equal to",
      on: "is ON",
      off: "is OFF",
      unavailable: "is unavailable",
      after: "is after",
      before: "is before",
      between: "is between",
    };
    return labels[condition] || condition || "condition";
  }

  _renderConditionFields(condition, index, prefix = "condition") {
    const isTime = condition.type === "time";
    const needsThreshold = !isTime && ["above", "below", "equal", "not_equal"].includes(condition.condition);
    const fieldAttrs = (field) => prefix === "primary"
      ? `data-primary-field="${field}"`
      : `data-condition-index="${index}" data-condition-field="${field}"`;
    return `
      <div class="automation-fields">
        <label class="automation-wide">
          <span>ENTITY</span>
          <input list="alarm-entity-list" value="${this._escape(condition.entity_id || "")}" placeholder="sensor.temperature or binary_sensor.door" ${fieldAttrs("entity_id")} autocomplete="off">
        </label>
        <label>
          <span>STATE / CONDITION</span>
          <select ${fieldAttrs("condition")}>
            <option value="above" ${condition.condition === "above" ? "selected" : ""}>is above</option>
            <option value="below" ${condition.condition === "below" ? "selected" : ""}>is below</option>
            <option value="equal" ${condition.condition === "equal" ? "selected" : ""}>equals</option>
            <option value="not_equal" ${condition.condition === "not_equal" ? "selected" : ""}>is not equal to</option>
            <option value="on" ${condition.condition === "on" ? "selected" : ""}>is ON</option>
            <option value="off" ${condition.condition === "off" ? "selected" : ""}>is OFF</option>
            <option value="unavailable" ${condition.condition === "unavailable" ? "selected" : ""}>is unavailable</option>
          </select>
        </label>
        ${needsThreshold ? `<label><span>VALUE / THRESHOLD</span><input type="number" step="0.1" value="${this._escape(condition.threshold ?? 0)}" ${fieldAttrs("threshold")} inputmode="decimal"></label>` : ""}
        <label><span>CONDITION DELAY (SECONDS)</span><input type="number" min="0" step="1" value="${this._escape(condition.delay ?? 0)}" ${fieldAttrs("delay")} inputmode="numeric"></label>
        ${needsThreshold ? `<label><span>CONDITION HYSTERESIS</span><input type="number" min="0" step="0.1" value="${this._escape(condition.hysteresis ?? 0)}" ${fieldAttrs("hysteresis")} inputmode="decimal"></label>` : ""}
      </div>
      ${!isTime && needsThreshold && condition.entity_id && this._hass?.states?.[condition.entity_id] ? `<div class="condition-live-status">Current value: <strong>${this._escape(this._hass.states[condition.entity_id].state)}</strong> &nbsp;•&nbsp; Limit: <strong>${this._escape(condition.threshold ?? 0)}</strong> &nbsp;•&nbsp; ${this._escape(this._conditionLabel(condition.condition))}</div>` : ""}`;
  }

  _renderTimeConditionFields(condition, index) {
    return `
      <div class="automation-fields">
        <label>
          <span>CONDITION</span>
          <select data-condition-index="${index}" data-condition-field="condition">
            <option value="after" ${condition.condition === "after" ? "selected" : ""}>is after</option>
            <option value="before" ${condition.condition === "before" ? "selected" : ""}>is before</option>
            <option value="between" ${condition.condition === "between" ? "selected" : ""}>is between</option>
          </select>
        </label>
        <label><span>START</span><input type="time" value="${this._escape(condition.start_time || "21:00")}" data-condition-index="${index}" data-condition-field="start_time"></label>
        ${condition.condition === "between" ? `<label><span>END</span><input type="time" value="${this._escape(condition.end_time || "06:00")}" data-condition-index="${index}" data-condition-field="end_time"></label>` : ""}
        <label><span>CONDITION DELAY (SECONDS)</span><input type="number" min="0" step="1" value="${this._escape(condition.delay ?? 0)}" data-condition-index="${index}" data-condition-field="delay" inputmode="numeric"></label>
      </div>`;
  }

  _renderBuilderCondition(condition, index) {
    const isTime = condition.type === "time";
    const entityState = condition.entity_id && this._hass?.states?.[condition.entity_id];
    const friendly = entityState?.attributes?.friendly_name || condition.entity_id || "Select an entity";
    return `
      ${index > 0 ? `<div class="automation-connector"><span>${this._builder.logic === "any" ? "OR" : "AND"}</span></div>` : ""}
      <article class="automation-block condition-block">
        <div class="automation-block-top">
          <div class="automation-block-title">
            <div class="automation-block-icon">${isTime ? "🕐" : "◉"}</div>
            <div>
              <div class="automation-block-kicker">${isTime ? "TIME CONDITION" : "ADDITIONAL CONDITION"}</div>
              <div class="automation-block-name">${isTime ? "Time" : this._escape(friendly)}</div>
            </div>
          </div>
          <button type="button" class="automation-delete builder-remove-condition" data-index="${index}" title="Remove condition">🗑</button>
        </div>
        <div class="automation-fields">
          <label>
            <span>TYPE</span>
            <select data-condition-index="${index}" data-condition-field="type">
              <option value="entity" ${!isTime ? "selected" : ""}>Entity state</option>
              <option value="time" ${isTime ? "selected" : ""}>Time</option>
            </select>
          </label>
        </div>
        ${isTime ? this._renderTimeConditionFields(condition, index) : this._renderConditionFields(condition, index)}
      </article>`;
  }

  _renderBuilder() {
    if (!this._builder) return "";
    const entityOptions = this._entityOptionsHtml();
    const conditions = this._builder.conditions || [];
    const primary = this._builder.primaryCondition || this._defaultPrimaryCondition();
    const hasPrimaryEntity = Boolean(String(primary.entity_id || "").trim());
    const logicAny = this._builder.logic === "any";
    const summary = conditions.length
      ? `${conditions.length + (hasPrimaryEntity ? 1 : 0)} condition${conditions.length + (hasPrimaryEntity ? 1 : 0) === 1 ? "" : "s"} · ${logicAny ? "Any condition" : "All conditions"}`
      : (hasPrimaryEntity ? "1 alarm entity condition" : "Manual trigger");

    return `
      <div class="builder-overlay">
        <div class="automation-editor">
          <div class="automation-editor-header">
            <button type="button" id="builder-cancel-button" class="automation-back">←</button>
            <div class="automation-editor-heading">
              <div class="automation-editor-title">${this._builder.alarmId ? "Edit alarm" : "New alarm"}</div>
              <div class="automation-editor-subtitle">Configure the alarm in one place, like a Home Assistant automation.</div>
            </div>
            <div class="automation-header-actions">
              <button type="button" id="builder-cancel-button" class="toolbar-button">CANCEL</button>
              ${this._builder.alarmId ? '<button type="button" id="delete-alarm-button" class="toolbar-button danger">DELETE</button>' : ""}
              <button type="button" id="builder-save-button" class="toolbar-button primary">${this._builder.alarmId ? "SAVE" : "CREATE"}</button>
            </div>
          </div>

          <div class="automation-editor-body">
            <section class="automation-section">
              <h2>Alarm</h2>
              <p>Start with the alarm name and the entity/state that represents the alarm. Additional logic is optional.</p>
              <div class="automation-card alarm-settings-card">
                <label class="automation-name-field"><span>ALARM NAME</span><input type="text" value="${this._escape(this._builder.name)}" data-builder-field="name" placeholder="Garage Door Open" autocomplete="off"></label>
                <label><span>SEVERITY</span><select data-builder-field="severity">
                  <option value="info" ${this._builder.severity === "info" ? "selected" : ""}>Info</option>
                  <option value="warning" ${this._builder.severity === "warning" ? "selected" : ""}>Warning</option>
                  <option value="alarm" ${this._builder.severity === "alarm" ? "selected" : ""}>Alarm</option>
                  <option value="critical" ${this._builder.severity === "critical" ? "selected" : ""}>Critical</option>
                </select></label>
                <label><span>ACTIVATION DELAY</span><input type="number" min="0" step="1" value="${this._escape(this._builder.delay)}" data-builder-field="delay" inputmode="numeric"></label>
                <label><span>HYSTERESIS</span><input type="number" min="0" step="0.1" value="${this._escape(this._builder.hysteresis)}" data-builder-field="hysteresis" inputmode="decimal"></label>
              </div>
            </section>

            <section class="automation-section">
              <h2>When</h2>
              <p>The alarm entity is the primary condition. Add more conditions only when you need extra logic.</p>
              <article class="automation-block primary-condition-block">
                <div class="automation-block-top">
                  <div class="automation-block-title">
                    <div class="automation-block-icon">◉</div>
                    <div>
                      <div class="automation-block-kicker">ALARM ENTITY</div>
                      <div class="automation-block-name">${this._escape(this._hass?.states?.[primary.entity_id]?.attributes?.friendly_name || primary.entity_id || "Choose the alarm entity")}</div>
                    </div>
                  </div>
                </div>
                ${this._renderConditionFields(primary, -1, "primary")}
              </article>

              ${conditions.length ? `<div class="automation-additional-heading">Additional conditions</div><div class="automation-flow">${conditions.map((c,i)=>this._renderBuilderCondition(c,i)).join("")}</div>` : ""}
              <div class="automation-add-row">
                <button type="button" class="automation-add builder-add-condition">＋ Add condition</button>
                ${conditions.length ? `<label class="logic-picker"><span>COMBINE ADDITIONAL CONDITIONS</span><select data-builder-field="logic"><option value="all" ${!logicAny ? "selected" : ""}>AND — all must be true</option><option value="any" ${logicAny ? "selected" : ""}>OR — any can be true</option></select></label>` : ""}
              </div>
            </section>

            <section class="automation-section">
              <h2>Then do</h2>
              <p>When the primary alarm entity and optional logic are satisfied, Alarm Manager activates the alarm lifecycle.</p>
              <div class="automation-card action-block">
                <div class="action-icon">🚨</div>
                <div class="action-main"><div class="action-title">Activate alarm</div><div class="action-description">${this._escape(this._builder.name || "Alarm")} · ${this._escape(String(this._builder.severity).toUpperCase())}</div></div>
                ${!hasPrimaryEntity && this._builder.alarmId ? `<button type="button" class="builder-trigger-now action-trigger">TRIGGER NOW</button>` : ""}
              </div>
            </section>

            <div class="automation-summary"><span>${summary}</span><span>${conditions.length ? (logicAny ? "OR" : "AND") : (hasPrimaryEntity ? "PRIMARY" : "MANUAL")}</span></div>
          </div>
        </div>
        <datalist id="alarm-entity-list">${entityOptions}</datalist>
      </div>
    `;
  }

  async _saveTargetEditor() {
    if (!this._hass || !this._targetEditor) return;
    const cfg=this._getNotificationConfig(); const t=this._targetEditor;
    const name=String(t.name||"").trim(); const service=String(t.service||"").trim();
    if(!name || !service){ window.alert("Please select a name and notification service."); return; }
    const targets=cfg.targets.map(x=>({...x}));
    const duplicate=targets.findIndex((x,i)=>i!==t.index && x.name.toLowerCase()===name.toLowerCase());
    if(duplicate>=0){ window.alert("A notification target with that name already exists."); return; }
    if(t.index>=0) targets[t.index]={name,service}; else targets.push({name,service});
    const routing={critical:[...(cfg.routing.critical||targets.map(x=>x.name))],alarm:[...(cfg.routing.alarm||targets.map(x=>x.name))],warning:[...(cfg.routing.warning||targets.map(x=>x.name))],info:[...(cfg.routing.info||targets.map(x=>x.name))]};
    // Remove renamed/deleted old name from routing, then apply this target's selections.
    Object.keys(routing).forEach(s=>{routing[s]=routing[s].filter(n=>targets.some(x=>x.name===n)); if(t.index>=0){ const old=cfg.targets[t.index]?.name; if(old && old!==name) routing[s]=routing[s].filter(n=>n!==old); }});
    Object.keys(t.routing).forEach(s=>{routing[s]=routing[s].filter(n=>n!==name); if(t.routing[s]) routing[s].push(name);});
    await this._hass.callService("alarm_manager","set_notification_targets",{targets,routing});
    this._targetEditor=null; this._render();
  }

  async _deleteTargetEditor() {
    if(!this._hass || !this._targetEditor || this._targetEditor.index<0) return;
    const cfg=this._getNotificationConfig(); const removed=cfg.targets[this._targetEditor.index];
    if(!window.confirm(`Delete notification target "${removed?.name || ""}"?`)) return;
    const targets=cfg.targets.filter((_,i)=>i!==this._targetEditor.index);
    const routing={}; Object.keys(cfg.routing).forEach(s=>routing[s]=(cfg.routing[s]||[]).filter(n=>n!==removed?.name));
    await this._hass.callService("alarm_manager","set_notification_targets",{targets,routing});
    this._targetEditor=null; this._render();
  }

  async _saveBuilder() {
    if (!this._hass || !this._builder) return;

    const builder = this._builder;
    const name = String(builder.name || "").trim();
    const primary = { ...(builder.primaryCondition || this._defaultPrimaryCondition()) };
    primary.entity_id = String(primary.entity_id || builder.entityId || "").trim();

    const additional = (builder.conditions || []).filter((condition) => {
      if (condition.type === "time") return Boolean(condition.start_time);
      return Boolean(String(condition.entity_id || "").trim());
    }).map((condition) => ({
      ...condition,
      entity_id: condition.type === "entity" ? String(condition.entity_id).trim() : undefined,
      threshold: condition.type === "entity" && ["above", "below", "equal", "not_equal"].includes(condition.condition)
        ? Number(condition.threshold ?? 0)
        : undefined,
      delay: Math.max(0, Number(condition.delay || 0)),
      hysteresis: condition.type === "entity" && ["above", "below", "equal", "not_equal"].includes(condition.condition)
        ? Math.max(0, Number(condition.hysteresis || 0))
        : 0,
    }));

    if (!name) { window.alert("Please enter an alarm name."); return; }
    primary.delay = Math.max(0, Number(primary.delay || 0));
    primary.hysteresis = ["above", "below", "equal", "not_equal"].includes(primary.condition)
      ? Math.max(0, Number(primary.hysteresis || 0))
      : 0;
    if (primary.entity_id && ["above", "below", "equal", "not_equal"].includes(primary.condition)) {
      primary.threshold = Number(primary.threshold ?? 0);
    }
    if (additional.some((condition) => condition.type === "time" && condition.condition === "between" && !condition.end_time)) {
      window.alert("A 'Between' time condition needs an end time."); return;
    }

    const conditions = [];
    if (primary.entity_id) conditions.push(primary);
    conditions.push(...additional);

    const data = {
      name,
      entity_id: primary.entity_id,
      conditions,
      logic: conditions.length > 1 && builder.logic === "any" ? "any" : "all",
      severity: builder.severity,
      delay: Math.max(0, Number(builder.delay || 0)),
      hysteresis: Math.max(0, Number(builder.hysteresis || 0)),
    };

    if (builder.alarmId) {
      data.alarm_id = builder.alarmId;
      await this._hass.callService("alarm_manager", "update_alarm", data);
    } else {
      await this._hass.callService("alarm_manager", "create_alarm", data);
    }

    this._builder = null;
    this._render();
  }

  async _deleteBuilderAlarm() {
    if (!this._hass || !this._builder?.alarmId) return;
    const name = this._builder.name || "this alarm";
    if (!window.confirm(`Delete alarm "${name}"? This removes the alarm configuration but does not erase its existing history.`)) {
      return;
    }
    await this._hass.callService("alarm_manager", "remove_alarm", {
      alarm_id: this._builder.alarmId,
    });
    this._builder = null;
    this._render();
  }

  async _saveDefaultNotification() {
    if (!this._hass || !this._notificationSettings) return;
    await this._hass.callService("alarm_manager", "set_default_notification", {
      notification_service: this._notificationSettings.defaultService || "disabled",
    });
    this._notificationSettings = null;
    this._render();
  }

  async _clearInactiveAlarm(alarmId) {
    if (!this._hass || !alarmId) {
      return;
    }

    await this._hass.callService(
      "alarm_manager",
      "clear_alarm",
      {
        alarm_id: alarmId,
      }
    );
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

    const history = this._getHistory();

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

  _getNotificationConfig() {
    const state = this._hass?.states?.["sensor.alarm_notification_targets"];
    return {
      targets: Array.isArray(state?.attributes?.targets) ? state.attributes.targets : [],
      routing: state?.attributes?.routing && typeof state.attributes.routing === "object" ? state.attributes.routing : {},
      defaultService: state?.attributes?.default_service || "disabled",
    };
  }

  _openDefaultNotificationEditor() {
    const config = this._getNotificationConfig();
    this._notificationSettings = { defaultService: config.defaultService || "disabled" };
    this._render();
  }

  _renderNotificationsView() {
    const config = this._getNotificationConfig();
    const services = Object.keys(this._hass?.services?.notify || {});
    const editingDefault = Boolean(this._notificationSettings);
    const defaultService = this._notificationSettings?.defaultService ?? config.defaultService ?? "disabled";
    return `
      <div class="page">
        <header class="header">
          <button type="button" class="mobile-menu-button" id="mobile-menu-button" aria-label="Open sidebar">☰</button>
          <div class="header-left">
            <div class="header-icon"><img src="/alarm_manager/brand/icon.png" class="header-logo" alt="Alarm Manager" /></div>
            <div><div class="title">Alarm Manager</div><div class="subtitle">Notification settings</div></div>
          </div>
        </header>
        <main class="content">
          <section class="section">
            <div class="section-header"><div><div class="section-title">DEFAULT NOTIFICATION</div><div class="notification-subtitle">The fallback Home Assistant notify service used when no named target routing is configured.</div></div><div class="section-actions"><button class="toolbar-button primary" id="save-default-notification-button">${editingDefault ? "SAVE" : "EDIT"}</button></div></div>
            <div class="automation-card target-form default-notification-card">
              <label><span>NOTIFY SERVICE</span><select data-default-notification="true" ${editingDefault ? "" : "disabled"}><option value="disabled">Disabled</option>${services.sort().map(s => `<option value="${this._escape(s)}" ${s===defaultService?"selected":""}>notify.${this._escape(s)}</option>`).join("")}</select></label>
              <div class="default-notification-status"><span class="status-dot"></span><strong>${defaultService === "disabled" ? "Disabled" : this._escape(`notify.${defaultService}`)}</strong></div>
            </div>
          </section>
          ${this._renderNotificationTargetsSection()}
          <section class="section"><div class="section-header"><div><div class="section-title">NOTIFICATION ROUTING</div><div class="notification-subtitle">Choose which people or devices receive each alarm severity. Routing is edited from each target.</div></div></div>
            <div class="notification-routing-summary">${["critical","alarm","warning","info"].map(s => { const names=(config.routing?.[s]||[]); return `<div class="routing-summary-card"><div class="routing-summary-severity">${s.toUpperCase()}</div><div class="routing-summary-names">${names.length ? names.map(n=>this._escape(n)).join(", ") : "No targets"}</div></div>`; }).join("")}</div>
          </section>
        </main>
        ${this._renderTargetEditor()}
      </div>`;
  }

  _renderNotificationTargetsSection() {
    const config = this._getNotificationConfig();
    const targets = config.targets;
    return `
      <section class="section notification-section">
        <div class="section-header">
          <div><div class="section-title">NOTIFICATION TARGETS</div><div class="notification-subtitle">People and devices that receive Alarm Manager notifications.</div></div>
          <div class="section-actions"><button class="toolbar-button primary" id="add-target-button">+ ADD TARGET</button></div>
        </div>
        <div class="notification-grid">
          ${targets.length ? targets.map((target,index) => {
            const severities = ["critical","alarm","warning","info"].filter(s => (config.routing?.[s] || targets.map(t=>t.name)).includes(target.name));
            return `<article class="notification-card">
              <div class="notification-card-icon">📱</div>
              <div class="notification-card-main"><div class="notification-card-name">${this._escape(target.name)}</div><div class="notification-card-service">${this._escape(target.service)}</div><div class="notification-card-severities">${severities.length ? severities.map(s=>`<span>${s.toUpperCase()}</span>`).join("") : "No severities"}</div></div>
              <button class="notification-edit-button" data-target-index="${index}">EDIT</button>
            </article>`;
          }).join("") : `<div class="notification-empty"><strong>No notification targets</strong><span>Add a mobile/device notification target to receive alarm alerts.</span></div>`}
        </div>
      </section>`;
  }

  _openTargetEditor(target = null, index = -1) {
    const config = this._getNotificationConfig();
    this._targetEditor = { index, name: target?.name || "", service: target?.service || "", routing: {} };
    ["critical","alarm","warning","info"].forEach(s => { this._targetEditor.routing[s] = (config.routing?.[s] || config.targets.map(t=>t.name)).includes(target?.name); });
    this._render();
  }

  _renderTargetEditor() {
    if (!this._targetEditor) return "";
    const t=this._targetEditor;
    const services=Object.keys(this._hass?.services?.notify || {});
    return `<div class="builder-overlay"><div class="target-editor">
      <div class="automation-editor-header"><button class="automation-back builder-close">←</button><div class="automation-editor-heading"><div class="automation-editor-title">${t.index >= 0 ? "Edit notification target" : "New notification target"}</div><div class="automation-editor-subtitle">Choose where Alarm Manager sends notifications and which severities this target receives.</div></div><div class="automation-header-actions"><button class="toolbar-button builder-close">CANCEL</button><button class="toolbar-button primary" id="save-target-button">SAVE</button></div></div>
      <div class="target-editor-body">
        <section class="automation-section"><h2>Notification target</h2><p>A target can be a Home Assistant mobile app, phone, tablet, or any other notify service.</p><div class="automation-card target-form">
          <label><span>NAME</span><input type="text" value="${this._escape(t.name)}" data-target-field="name" placeholder="Kristofer"></label>
          <label><span>NOTIFY SERVICE</span><select data-target-field="service"><option value="">Select notify service</option>${services.map(s=>`<option value="${this._escape(s)}" ${s===t.service?"selected":""}>notify.${this._escape(s)}</option>`).join("")}</select></label>
        </div></section>
        <section class="automation-section"><h2>Severity routing</h2><p>Select which alarm severities should be delivered to this target.</p><div class="severity-routing">${["critical","alarm","warning","info"].map(s=>`<label class="severity-check"><input type="checkbox" data-target-severity="${s}" ${t.routing[s]?"checked":""}><span>${s.toUpperCase()}</span></label>`).join("")}</div></section>
        ${t.index >= 0 ? `<button class="toolbar-button danger" id="delete-target-button">DELETE TARGET</button>` : ""}
      </div></div></div>`;
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

  _primaryConditionForAlarm(attributes) {
    const conditions = Array.isArray(attributes?.conditions) ? attributes.conditions : [];
    const primaryEntityId = attributes?.entity_id;
    if (primaryEntityId) {
      const primary = conditions.find((item) =>
        item?.type !== "time" && item?.entity_id === primaryEntityId
      );
      if (primary) return primary;
    }
    return conditions.find((item) => item?.type !== "time") || null;
  }

  _alarmLimitText(attributes) {
    const primary = this._primaryConditionForAlarm(attributes);
    const condition = primary?.condition || attributes?.condition;
    const threshold = primary?.threshold ?? attributes?.threshold;
    return this._conditionText(condition, threshold);
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

    const threshold = this._alarmLimitText(attributes);

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

        <div class="alarm-ack-by-cell">
          ${
            acknowledged
              ? (attributes.acknowledged_by || "—")
              : "—"
          }
        </div>

        <div class="alarm-action-cell">

          <button
            class="edit-alarm-button"
            data-alarm-id="${alarmId}"
            ${alarmId ? "" : "disabled"}
          >
            EDIT
          </button>

          ${
            inactive
              ? `
                  <button
                    class="clear-alarm-button"
                    data-alarm-id="${alarmId}"
                    ${
                      alarmId
                        ? ""
                        : "disabled"
                    }
                  >
                    CLEAR
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

  _renderHistorySection() {
    const history = this._getHistory();
    const filteredHistory = this._getFilteredHistory();
    const shownCount = filteredHistory.length;
    const totalCount = history.length;
    return `
      <section class="section" id="alarm-history-section">
        <div class="section-header">
          <div class="section-title">ALARM HISTORY</div>
          <div class="section-actions">
            <div class="section-count">${this._historySeverityFilter === "all" ? totalCount : `${shownCount} of ${totalCount}`} occurrence${(this._historySeverityFilter === "all" ? totalCount : shownCount) === 1 ? "" : "s"}</div>
            <select id="history-severity-filter" class="history-filter">
              <option value="all" ${this._historySeverityFilter === "all" ? "selected" : ""}>All severities</option>
              <option value="critical" ${this._historySeverityFilter === "critical" ? "selected" : ""}>Critical</option>
              <option value="alarm" ${this._historySeverityFilter === "alarm" ? "selected" : ""}>Alarm</option>
              <option value="warning" ${this._historySeverityFilter === "warning" ? "selected" : ""}>Warning</option>
              <option value="info" ${this._historySeverityFilter === "info" ? "selected" : ""}>Info</option>
            </select>
            <button class="toolbar-button danger" id="clear-history-button" ${totalCount === 0 ? "disabled" : ""}>CLEAR HISTORY</button>
          </div>
        </div>
        ${filteredHistory.length === 0
          ? `<div class="no-history">${totalCount === 0 ? "No completed alarm occurrences." : "No history matches this severity."}</div>`
          : `<div class="history-table">
              <div class="history-header">
                <div></div><div>ALARM</div><div>TRIGGER</div><div>DURATION</div><div>ACTIVATED</div><div>CLEARED</div><div>ACKNOWLEDGEMENT</div>
              </div>
              ${filteredHistory.map((record) => this._renderHistoryRow(record)).join("")}
            </div>`}
      </section>`;
  }

  _updateHistorySection() {
    const section = this.shadowRoot?.querySelector("#alarm-history-section");
    if (!section) {
      this._render();
      return;
    }
    section.outerHTML = this._renderHistorySection();
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

                  <div class="
                    history-ack-user
                  ">
                    By:
                    ${
                      record.acknowledged_by ||
                      "—"
                    }
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

    if (window.location.pathname.includes("alarm-manager-notifications")) {
      this.shadowRoot.innerHTML = `<style>
        :host { display:block; width:100%; min-height:100%; font-family:var(--primary-font-family,sans-serif); color:var(--primary-text-color); }
        * { box-sizing:border-box; }
        .page { min-height:100vh; background:var(--primary-background-color); }
        .mobile-menu-button { display:none; width:44px; height:44px; margin:0; padding:0; border:0; border-radius:50%; background:transparent; color:var(--primary-text-color); font-size:28px; line-height:1; cursor:pointer; flex:0 0 auto; }
        .header { display:flex; align-items:center; padding:18px 24px; border-bottom:1px solid var(--divider-color); background:var(--card-background-color); }
        .header-left { display:flex; align-items:center; gap:14px; }
        .header-icon { width:46px; height:46px; display:flex; align-items:center; justify-content:center; overflow:hidden; border-radius:8px; background:var(--secondary-background-color); }
        .header-logo { width:100%; height:100%; object-fit:contain; }
        .title { font-size:20px; font-weight:600; } .subtitle { margin-top:3px; font-size:11px; color:var(--secondary-text-color); }
        .content { padding:22px 24px 40px; } .section { margin-bottom:28px; } .section-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:9px; } .section-title { font-size:11px; font-weight:700; letter-spacing:.12em; color:var(--secondary-text-color); } .section-actions { display:flex; align-items:center; gap:8px; }
        .toolbar-button { padding:7px 12px; border:1px solid var(--divider-color); border-radius:5px; cursor:pointer; background:var(--secondary-background-color); color:var(--primary-text-color); font-size:9px; font-weight:700; letter-spacing:.05em; } .toolbar-button.primary { background:var(--primary-color); border-color:var(--primary-color); color:white; } .toolbar-button.danger { color:#c62828; }
        .automation-card { border:1px solid var(--divider-color); border-radius:8px; background:var(--card-background-color); box-shadow:0 1px 2px rgba(0,0,0,.06); } .target-form { display:grid; grid-template-columns:1fr 1fr; gap:14px; padding:18px; } .automation-card label { display:flex; flex-direction:column; gap:6px; } .automation-card label span { font-size:9px; font-weight:700; letter-spacing:.07em; color:var(--secondary-text-color); } .automation-card input,.automation-card select { width:100%; min-height:40px; padding:8px 10px; border:1px solid var(--divider-color); border-radius:5px; background:var(--primary-background-color); color:var(--primary-text-color); font:inherit; font-size:12px; }
        .notification-subtitle { margin-top:3px; font-size:10px; color:var(--secondary-text-color); } .notification-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; } .notification-card { display:flex; align-items:center; gap:12px; padding:14px; border:1px solid var(--divider-color); border-radius:8px; background:var(--card-background-color); } .notification-card-icon { width:34px; height:34px; display:grid; place-items:center; border-radius:7px; background:var(--secondary-background-color); } .notification-card-main { flex:1; min-width:0; } .notification-card-name { font-size:12px; font-weight:600; } .notification-card-service { margin-top:3px; font-size:9px; color:var(--secondary-text-color); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } .notification-card-severities { display:flex; gap:4px; margin-top:7px; flex-wrap:wrap; } .notification-card-severities span { padding:3px 5px; border-radius:4px; background:var(--secondary-background-color); font-size:7px; font-weight:800; } .notification-edit-button { padding:6px 8px; border:1px solid var(--divider-color); border-radius:4px; background:transparent; color:var(--secondary-text-color); font-size:8px; font-weight:800; cursor:pointer; } .notification-empty { padding:20px; border:1px dashed var(--divider-color); border-radius:8px; background:var(--card-background-color); } .notification-empty strong { display:block; font-size:12px; } .notification-empty span { display:block; margin-top:4px; font-size:10px; color:var(--secondary-text-color); }
        .target-editor { position:fixed; inset:0; z-index:1000; min-height:100%; background:var(--primary-background-color); overflow:auto; } .automation-editor-header { position:sticky; top:0; z-index:2; display:flex; align-items:center; gap:16px; min-height:64px; padding:10px 24px; background:var(--card-background-color); border-bottom:1px solid var(--divider-color); } .automation-back { width:38px; height:38px; border:0; border-radius:50%; background:transparent; color:var(--primary-text-color); font-size:25px; cursor:pointer; } .automation-editor-heading { flex:1; min-width:0; } .automation-editor-title { font-size:20px; font-weight:600; } .automation-editor-subtitle { margin-top:2px; font-size:11px; color:var(--secondary-text-color); } .automation-header-actions { display:flex; gap:8px; } .target-editor-body { width:min(820px,calc(100vw - 40px)); margin:0 auto; padding:30px 0 70px; } .severity-routing { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; } .severity-check { display:flex; align-items:center; gap:9px; padding:14px; border:1px solid var(--divider-color); border-radius:7px; background:var(--card-background-color); font-size:10px; font-weight:700; cursor:pointer; } .severity-check input { accent-color:var(--primary-color); } .notification-routing-summary { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; } .routing-summary-card { padding:14px; border:1px solid var(--divider-color); border-radius:8px; background:var(--card-background-color); } .routing-summary-severity { font-size:9px; font-weight:800; letter-spacing:.08em; } .routing-summary-names { margin-top:6px; font-size:11px; color:var(--secondary-text-color); } .default-notification-status { display:flex; align-items:center; gap:8px; padding:10px 0; font-size:11px; } .status-dot { width:8px; height:8px; border-radius:50%; background:var(--primary-color); } @media(max-width:700px){.mobile-menu-button{display:inline-grid;place-items:center}.content{padding:16px}.notification-grid,.target-form,.notification-routing-summary{grid-template-columns:1fr}.severity-routing{grid-template-columns:1fr 1fr}.automation-editor-header{padding:8px 12px}.automation-editor-subtitle{display:none}.target-editor-body{width:calc(100vw - 24px);padding-top:20px}}
      </style>${this._renderNotificationsView()}`;
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
    const filteredHistory = this._getFilteredHistory()
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

        .mobile-menu-button {
          display: none;
          width: 44px;
          height: 44px;
          margin: 0;
          padding: 0;
          border: 0;
          border-radius: 50%;
          background: transparent;
          color: var(--primary-text-color);
          font-size: 28px;
          line-height: 1;
          cursor: pointer;
          flex: 0 0 auto;
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
            110px
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

        .clear-alarm-button {
          padding:
            6px
            10px;

          border:
            1px solid
            var(
              --warning-color,
              var(--primary-color)
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

        .clear-alarm-button:hover {
          background:
            var(
              --warning-color,
              var(--primary-color)
            );

          color:
            white;
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

        .history-ack-user {
          margin-top: 3px;
          font-size: 9px;
          color: var(--secondary-text-color);
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

        .history-ack-by {
          margin-top: 2px;
          font-size: 9px;
          color: var(
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
              110px
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



        .condition-live-status { padding:0 16px 14px; font-size:11px; color:var(--secondary-text-color); } .condition-live-status strong { color:var(--primary-text-color); } .history-filter { min-height:32px; padding:6px 10px; border:1px solid var(--divider-color); border-radius:5px; background:var(--secondary-background-color); color:var(--primary-text-color); font:inherit; font-size:9px; }
        /* Automation-style alarm editor */
        .builder-overlay { position: fixed; inset: 0; z-index: 1000; background: var(--primary-background-color); overflow: auto; box-sizing: border-box; padding-top: max(var(--safe-area-inset-top, 0px), env(safe-area-inset-top, 0px)); padding-bottom: max(var(--safe-area-inset-bottom, 0px), env(safe-area-inset-bottom, 0px)); }
        .automation-editor { min-height: 100%; display: flex; flex-direction: column; }
        .automation-editor-header { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; gap: 16px; min-height: 64px; padding: 10px 24px; background: var(--card-background-color); border-bottom: 1px solid var(--divider-color); }
        .automation-back { width: 38px; height: 38px; border: 0; border-radius: 50%; background: transparent; color: var(--primary-text-color); font-size: 25px; cursor: pointer; }
        .automation-back:hover { background: var(--secondary-background-color); }
        .automation-editor-heading { flex: 1; min-width: 0; }
        .automation-editor-title { font-size: 20px; font-weight: 600; }
        .automation-editor-subtitle { margin-top: 2px; font-size: 11px; color: var(--secondary-text-color); }
        .automation-header-actions { display: flex; gap: 8px; }
        .automation-editor-body { width: min(920px, calc(100vw - 40px)); margin: 0 auto; padding: 30px 0 70px; }
        .automation-section { margin-bottom: 34px; }
        .automation-section h2 { margin: 0 0 4px; font-size: 18px; font-weight: 500; }
        .automation-section > p { max-width: 820px; margin: 0 0 14px; font-size: 11px; line-height: 1.5; color: var(--secondary-text-color); }
        .automation-card, .automation-block { border: 1px solid var(--divider-color); border-radius: 8px; background: var(--card-background-color); box-shadow: 0 1px 2px rgba(0,0,0,.06); }
        .alarm-settings-card { display: grid; grid-template-columns: minmax(240px,1.5fr) minmax(240px,1.5fr) repeat(3,minmax(120px,1fr)); gap: 14px; padding: 18px; }
        .automation-card label, .automation-fields label, .logic-picker { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
        .automation-card label span, .automation-fields label span, .logic-picker span { font-size: 9px; font-weight: 700; letter-spacing: .07em; color: var(--secondary-text-color); }
        .automation-card input, .automation-card select, .automation-fields input, .automation-fields select, .logic-picker select { width: 100%; min-height: 40px; padding: 8px 10px; border: 1px solid var(--divider-color); border-radius: 5px; background: var(--primary-background-color); color: var(--primary-text-color); font: inherit; font-size: 12px; }
        .automation-flow { display: flex; flex-direction: column; }
        .automation-block { padding: 0; overflow: hidden; }
        .automation-block-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 13px 16px; border-bottom: 1px solid var(--divider-color); background: var(--secondary-background-color); }
        .automation-block-title { display: flex; align-items: center; gap: 12px; min-width: 0; }
        .automation-block-icon { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 6px; background: var(--primary-background-color); font-size: 15px; }
        .automation-block-kicker { font-size: 8px; font-weight: 800; letter-spacing: .09em; color: var(--secondary-text-color); }
        .automation-block-name { margin-top: 2px; font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .automation-delete { border: 0; background: transparent; color: var(--secondary-text-color); cursor: pointer; padding: 7px; border-radius: 5px; }
        .automation-delete:hover { color: #c62828; background: var(--primary-background-color); }
        .automation-fields { display: grid; grid-template-columns: minmax(170px,1.35fr) minmax(170px,1.15fr) minmax(130px,1fr) minmax(145px,1fr) minmax(145px,1fr); gap: 12px; padding: 16px; }
        .automation-wide { grid-column: span 1; }
        .automation-connector { height: 42px; display: flex; align-items: center; justify-content: center; position: relative; }
        .automation-connector::before { content: ""; position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: var(--divider-color); }
        .automation-connector span { position: relative; z-index: 1; padding: 5px 12px; border: 1px solid var(--divider-color); border-radius: 999px; background: var(--primary-background-color); color: var(--secondary-text-color); font-size: 9px; font-weight: 800; }
        .automation-add-row { display: flex; align-items: end; justify-content: space-between; gap: 18px; margin-top: 12px; }
        .automation-add { padding: 10px 15px; border: 1px solid var(--primary-color); border-radius: 5px; background: transparent; color: var(--primary-color); font-size: 11px; cursor: pointer; }
        .automation-add:hover { background: var(--secondary-background-color); }
        .logic-picker { width: 290px; }
        .automation-empty { display: flex; flex-direction: column; gap: 5px; padding: 20px; border: 1px dashed var(--divider-color); border-radius: 8px; background: var(--card-background-color); }
        .automation-empty strong { font-size: 13px; font-weight: 600; }
        .automation-empty span { font-size: 11px; color: var(--secondary-text-color); line-height: 1.5; }
        .automation-empty code { font-family: var(--code-font-family, monospace); }
        .action-block { display: flex; align-items: center; gap: 14px; padding: 15px 16px; }
        .action-icon { font-size: 22px; }
        .action-main { flex: 1; min-width: 0; }
        .action-title { font-size: 13px; font-weight: 600; }
        .action-description { margin-top: 3px; font-size: 10px; color: var(--secondary-text-color); }
        .action-trigger { margin-left: auto; padding: 7px 10px; border: 1px solid var(--primary-color); border-radius: 5px; background: transparent; color: var(--primary-color); cursor: pointer; font-size: 9px; font-weight: 700; }
        .automation-summary { display: flex; justify-content: space-between; padding: 12px 14px; border-top: 1px solid var(--divider-color); font-size: 10px; color: var(--secondary-text-color); }

        .notification-subtitle { margin-top: 3px; font-size: 10px; color: var(--secondary-text-color); }
        .notification-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 10px; }
        .notification-card { display:flex; align-items:center; gap:12px; padding:14px; border:1px solid var(--divider-color); border-radius:8px; background:var(--card-background-color); }
        .notification-card-icon { width:34px; height:34px; display:grid; place-items:center; border-radius:7px; background:var(--secondary-background-color); }
        .notification-card-main { flex:1; min-width:0; }
        .notification-card-name { font-size:12px; font-weight:600; }
        .notification-card-service { margin-top:3px; font-size:9px; color:var(--secondary-text-color); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .notification-card-severities { display:flex; gap:4px; margin-top:7px; flex-wrap:wrap; }
        .notification-card-severities span { padding:3px 5px; border-radius:4px; background:var(--secondary-background-color); font-size:7px; font-weight:800; }
        .notification-edit-button { padding:6px 8px; border:1px solid var(--divider-color); border-radius:4px; background:transparent; color:var(--secondary-text-color); font-size:8px; font-weight:800; cursor:pointer; }
        .notification-empty { padding:20px; border:1px dashed var(--divider-color); border-radius:8px; background:var(--card-background-color); }
        .notification-empty strong { display:block; font-size:12px; } .notification-empty span { display:block; margin-top:4px; font-size:10px; color:var(--secondary-text-color); }
        .target-editor { min-height:100%; background:var(--primary-background-color); }
        .target-editor-body { width:min(820px,calc(100vw - 40px)); margin:0 auto; padding:30px 0 70px; }
        .target-form { display:grid; grid-template-columns:1fr 1fr; gap:14px; padding:18px; }
        .severity-routing { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
        .severity-check { display:flex; align-items:center; gap:9px; padding:14px; border:1px solid var(--divider-color); border-radius:7px; background:var(--card-background-color); font-size:10px; font-weight:700; cursor:pointer; }
        .severity-check input { accent-color:var(--primary-color); }

        .edit-alarm-button {
          padding: 5px 7px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: transparent;
          color: var(--secondary-text-color);
          font-size: 8px;
          font-weight: 800;
          cursor: pointer;
        }

        .edit-alarm-button:hover:not(:disabled) {
          color: var(--primary-text-color);
          background: var(--secondary-background-color);
        }

        .edit-alarm-button:disabled {
          opacity: 0.35;
          cursor: default;
        }

        @media (max-width: 900px) {
          .alarm-settings-card, .target-form { grid-template-columns: 1fr 1fr; }
          .automation-fields { grid-template-columns: 1fr 1fr; }
          .notification-grid { grid-template-columns: 1fr; }
          .severity-routing { grid-template-columns: 1fr 1fr; }
          .general-grid,
          .builder-grid {
            grid-template-columns: 1fr 1fr;
          }
        }

        @media (max-width: 620px) {
          .mobile-menu-button { display: inline-grid; place-items: center; }
          .automation-editor-header { padding: 8px 12px; }
          .automation-editor-body, .target-editor-body { width: calc(100vw - 24px); padding-top:20px; }
          .automation-editor-subtitle { display:none; }
          .automation-header-actions .toolbar-button:first-child { display:none; }
          .alarm-settings-card, .target-form, .automation-fields { grid-template-columns: 1fr; }
          .automation-wide { grid-column:auto; }
          .automation-add-row { align-items:stretch; flex-direction:column; }
          .logic-picker { width:100%; }
          .severity-routing { grid-template-columns:1fr 1fr; }
        }

      </style>

      <div class="page">

        <header class="header">

          <button type="button" class="mobile-menu-button" id="mobile-menu-button" aria-label="Open sidebar">☰</button>

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
                  class="toolbar-button primary"
                  id="add-alarm-button"
                >
                  + ADD ALARM
                </button>

                <button
                  class="toolbar-button primary"
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

          ${this._renderNotificationTargetsSection()}

          <section class="section" id="alarm-history-section">

            <div class="section-header">

              <div class="section-title">
                ALARM HISTORY
              </div>

              <div class="section-actions">

                <div class="section-count">
                  ${this._historySeverityFilter === "all" ? history.length : `${filteredHistory.length} of ${history.length}`}
                  occurrence${(this._historySeverityFilter === "all" ? history.length : filteredHistory.length) === 1 ? "" : "s"}
                </div>

                <select id="history-severity-filter" class="history-filter">
                  <option value="all" ${this._historySeverityFilter === "all" ? "selected" : ""}>All severities</option>
                  <option value="critical" ${this._historySeverityFilter === "critical" ? "selected" : ""}>Critical</option>
                  <option value="alarm" ${this._historySeverityFilter === "alarm" ? "selected" : ""}>Alarm</option>
                  <option value="warning" ${this._historySeverityFilter === "warning" ? "selected" : ""}>Warning</option>
                  <option value="info" ${this._historySeverityFilter === "info" ? "selected" : ""}>Info</option>
                </select>

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
              filteredHistory.length === 0
                ? `
                    <div class="no-history">
                      ${history.length === 0 ? "No completed alarm occurrences." : "No history matches this severity."}
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

                      ${filteredHistory
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

        ${this._renderBuilder()}
        ${this._renderTargetEditor()}

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