/* timeline.js — Rollback & A/B report timeline for US-304 */

(function (window) {
  "use strict";

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "className") node.className = attrs[k];
      else if (k === "textContent") node.textContent = attrs[k];
      else if (k === "innerHTML") node.innerHTML = attrs[k];
      else if (k.startsWith("on")) node.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
      else node.setAttribute(k, attrs[k]);
    });
    if (children) children.forEach(function (c) {
      if (typeof c === "string") node.appendChild(document.createTextNode(c));
      else if (c) node.appendChild(c);
    });
    return node;
  }

  function formatTimestamp(ts) {
    try {
      var d = new Date(ts);
      return d.toLocaleDateString() + " " + d.toLocaleTimeString();
    } catch (e) {
      return ts;
    }
  }

  function daysAgo(ts, days) {
    try {
      var d = new Date(ts);
      var cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - days);
      return d >= cutoff;
    } catch (e) {
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Rollback card helpers
  // ---------------------------------------------------------------------------

  function rollbackBorderClass(severity) {
    if (severity === "critical") return "tl-border-red";
    return "tl-border-yellow";
  }

  function rollbackIcon() {
    return "\u26A0";  // warning triangle
  }

  function renderRollbackBody(data) {
    var parts = [];
    parts.push(el("div", { className: "tl-field" }, [
      el("span", { className: "tl-field-label", textContent: "Trigger: " }),
      el("span", { textContent: data.trigger || "unknown" }),
    ]));
    parts.push(el("div", { className: "tl-field" }, [
      el("span", { className: "tl-field-label", textContent: "Severity: " }),
      el("span", {
        className: "badge " + (data.severity === "critical" ? "red" : "yellow"),
        textContent: data.severity || "unknown",
      }),
    ]));
    var paramCount = (data.affected_params && data.affected_params.length) || 0;
    parts.push(el("div", { className: "tl-field" }, [
      el("span", { className: "tl-field-label", textContent: "Affected Params: " }),
      el("span", { textContent: String(paramCount) }),
    ]));
    var action = "none";
    if (data.recovery_action) {
      action = data.recovery_action.action || JSON.stringify(data.recovery_action);
    }
    parts.push(el("div", { className: "tl-field" }, [
      el("span", { className: "tl-field-label", textContent: "Recovery: " }),
      el("span", { textContent: action }),
    ]));
    return parts;
  }

  // ---------------------------------------------------------------------------
  // A/B test card helpers
  // ---------------------------------------------------------------------------

  function abBorderClass(verdict) {
    if (verdict === "candidate_wins") return "tl-border-green";
    if (verdict === "baseline_wins") return "tl-border-blue";
    return "tl-border-gray";
  }

  function abIcon() {
    return "\u2697";  // alembic / flask
  }

  function renderABBody(data) {
    var parts = [];
    parts.push(el("div", { className: "tl-field" }, [
      el("span", { className: "tl-field-label", textContent: "Verdict: " }),
      el("span", {
        className: "badge " + verdictBadgeColor(data.verdict),
        textContent: data.verdict || "unknown",
      }),
    ]));

    var pVal = data.p_value !== undefined && data.p_value !== null
      ? (data.p_value < 0.001 ? data.p_value.toExponential(2) : data.p_value.toFixed(4))
      : "n/a";
    parts.push(el("div", { className: "tl-field" }, [
      el("span", { className: "tl-field-label", textContent: "p-value: " }),
      el("span", { className: "tl-mono", textContent: pVal }),
    ]));

    var cd = data.cohens_d !== undefined && data.cohens_d !== null
      ? data.cohens_d.toFixed(4)
      : "n/a";
    parts.push(el("div", { className: "tl-field" }, [
      el("span", { className: "tl-field-label", textContent: "Cohen's d: " }),
      el("span", { className: "tl-mono", textContent: cd }),
    ]));

    if (data.early_stopped) {
      parts.push(el("span", { className: "badge yellow tl-early-badge", textContent: "EARLY STOPPED" }));
    }
    return parts;
  }

  function verdictBadgeColor(verdict) {
    if (verdict === "candidate_wins") return "green";
    if (verdict === "baseline_wins") return "blue";
    return "gray";
  }

  // ---------------------------------------------------------------------------
  // renderTimeline
  // ---------------------------------------------------------------------------

  function renderTimeline(container, events) {
    if (!events || events.length === 0) {
      container.appendChild(el("div", { className: "placeholder" }, [
        el("div", { textContent: "No rollback or A/B test events recorded yet" }),
      ]));
      return;
    }

    var timeline = el("div", { className: "tl-timeline" });

    // Connector line is CSS pseudo-element on .tl-timeline

    events.forEach(function (evt, idx) {
      var isLeft = idx % 2 === 0;
      var isRollback = evt.type === "rollback";
      var data = evt.data || {};

      var borderClass = isRollback
        ? rollbackBorderClass(data.severity)
        : abBorderClass(data.verdict);

      var icon = isRollback ? rollbackIcon() : abIcon();
      var typeLabel = isRollback ? "Rollback" : "A/B Test";
      var bodyParts = isRollback ? renderRollbackBody(data) : renderABBody(data);

      // Detail toggle
      var detailPre = el("pre", { className: "tl-json-detail tl-collapsed", textContent: JSON.stringify(data, null, 2) });

      var card = el("div", { className: "tl-card " + borderClass + (isLeft ? " tl-left" : " tl-right") }, [
        el("div", { className: "tl-card-header" }, [
          el("span", { className: "tl-icon", textContent: icon }),
          el("span", { className: "tl-type-label", textContent: typeLabel }),
        ]),
        el("div", { className: "tl-card-body" }, bodyParts),
        el("button", {
          className: "tl-expand-btn",
          textContent: "Show details",
          onClick: function () {
            var collapsed = detailPre.classList.contains("tl-collapsed");
            detailPre.classList.toggle("tl-collapsed");
            this.textContent = collapsed ? "Hide details" : "Show details";
          },
        }),
        detailPre,
      ]);

      // Timestamp node on the connector
      var tsNode = el("div", { className: "tl-timestamp" + (isLeft ? " tl-ts-right" : " tl-ts-left") }, [
        el("span", { textContent: formatTimestamp(evt.timestamp) }),
      ]);

      var row = el("div", { className: "tl-row" }, [
        isLeft ? card : tsNode,
        el("div", { className: "tl-dot" }),
        isLeft ? tsNode : card,
      ]);

      timeline.appendChild(row);
    });

    container.appendChild(timeline);
  }

  // ---------------------------------------------------------------------------
  // renderTimelineSummary
  // ---------------------------------------------------------------------------

  function renderTimelineSummary(container, events) {
    var rollbacks7d = 0;
    var rollbacks30d = 0;
    var abTotal = 0;
    var abWins = 0;

    events.forEach(function (evt) {
      if (evt.type === "rollback") {
        if (daysAgo(evt.timestamp, 30)) rollbacks30d++;
        if (daysAgo(evt.timestamp, 7)) rollbacks7d++;
      } else if (evt.type === "ab_test") {
        abTotal++;
        if (evt.data && evt.data.verdict === "candidate_wins") abWins++;
      }
    });

    var winRate = abTotal > 0 ? Math.round((abWins / abTotal) * 100) : 0;

    var bar = el("div", { className: "tl-summary-bar" }, [
      el("div", { className: "tl-summary-item" }, [
        el("span", { className: "tl-summary-value red", textContent: String(rollbacks7d) }),
        el("span", { className: "tl-summary-label", textContent: "Rollbacks (7d)" }),
      ]),
      el("div", { className: "tl-summary-item" }, [
        el("span", { className: "tl-summary-value yellow", textContent: String(rollbacks30d) }),
        el("span", { className: "tl-summary-label", textContent: "Rollbacks (30d)" }),
      ]),
      el("div", { className: "tl-summary-item" }, [
        el("span", { className: "tl-summary-value accent", textContent: String(abTotal) }),
        el("span", { className: "tl-summary-label", textContent: "A/B Tests" }),
      ]),
      el("div", { className: "tl-summary-item" }, [
        el("span", { className: "tl-summary-value green", textContent: winRate + "%" }),
        el("span", { className: "tl-summary-label", textContent: "A/B Win Rate" }),
      ]),
    ]);

    container.appendChild(bar);
  }

  // ---------------------------------------------------------------------------
  // Export
  // ---------------------------------------------------------------------------

  window.Timeline = {
    renderTimeline: renderTimeline,
    renderTimelineSummary: renderTimelineSummary,
  };

})(window);
