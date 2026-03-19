/* app.js — meta-vengine dashboard client */

(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Config
  // ---------------------------------------------------------------------------

  var REFRESH_INTERVAL = 60; // seconds
  var refreshTimer = null;
  var countdown = REFRESH_INTERVAL;

  // ---------------------------------------------------------------------------
  // DOM helpers
  // ---------------------------------------------------------------------------

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return document.querySelectorAll(sel); }

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

  // ---------------------------------------------------------------------------
  // Tab switching
  // ---------------------------------------------------------------------------

  function initTabs() {
    var btns = $$(".tab-btn");
    btns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        btns.forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        $$(".tab-panel").forEach(function (p) { p.classList.remove("active"); });
        var target = btn.getAttribute("data-tab");
        var panel = $("#panel-" + target);
        if (panel) panel.classList.add("active");
        // Lazy-load tabs on first visit
        if (target === "weights" && !weightsLoaded) {
          loadWeightsTab();
        }
        if (target === "clusters" && !clustersLoaded) {
          loadClusters();
        }
        if (target === "timeline" && !timelineLoaded) {
          loadTimeline();
        }
      });
    });
  }

  // ---------------------------------------------------------------------------
  // API fetch
  // ---------------------------------------------------------------------------

  function fetchJSON(url) {
    return fetch(url).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }

  // ---------------------------------------------------------------------------
  // Overview rendering
  // ---------------------------------------------------------------------------

  function statusColor(status) {
    if (status === "healthy" || status === true) return "green";
    if (status === "no_data") return "yellow";
    return "red";
  }

  function renderOverview(health) {
    var container = $("#overview-content");
    container.innerHTML = "";

    // -- Metric cards --
    var grid = el("div", { className: "card-grid" });

    // Bandit enabled
    var banditVal = health.banditEnabled ? "ENABLED" : "DISABLED";
    var banditColor = health.banditEnabled ? "green" : "red";
    grid.appendChild(makeCard("Bandit Engine", banditVal, banditColor));

    // Param count
    grid.appendChild(makeCard("Learnable Params", String(health.paramCount), "accent"));

    // Total decisions
    grid.appendChild(makeCard("Total Decisions", String(health.totalDecisions), "accent"));

    // Avg reward
    var rewardStr = health.avgRewardLast100 !== null && health.avgRewardLast100 !== undefined
      ? String(health.avgRewardLast100)
      : "n/a";
    grid.appendChild(makeCard("Avg Reward (last 100)", rewardStr, "accent"));

    // Exploration floor — fetch from params
    fetchJSON("/api/params").then(function (params) {
      var floor = "n/a";
      if (params && params.parameters) {
        for (var i = 0; i < params.parameters.length; i++) {
          if (params.parameters[i].id === "explorationFloorGlobal") {
            floor = String(params.parameters[i].value);
            break;
          }
        }
      }
      grid.appendChild(makeCard("Exploration Floor", floor, "accent"));
    }).catch(function () {
      grid.appendChild(makeCard("Exploration Floor", "error", "red"));
    });

    // Last snapshot age
    var snapshotAge = "n/a";
    if (health.daemonHealth && health.daemonHealth.daemons) {
      for (var i = 0; i < health.daemonHealth.daemons.length; i++) {
        var d = health.daemonHealth.daemons[i];
        if (d.daemon === "weight-snapshot" && d.age_hours !== null) {
          snapshotAge = d.age_hours + "h";
          break;
        }
      }
    }
    grid.appendChild(makeCard("Last Snapshot Age", snapshotAge, "accent"));

    container.appendChild(grid);

    // -- Header status dot --
    var dot = $("#header-status");
    dot.className = "status-dot " + (health.banditEnabled ? "green" : "red");

    // -- Daemon health section --
    var daemons = (health.daemonHealth && health.daemonHealth.daemons) || [];
    if (daemons.length > 0) {
      container.appendChild(el("div", { className: "section-title", textContent: "Daemon Health" }));
      var dg = el("div", { className: "daemon-grid" });
      daemons.forEach(function (d) {
        var color = statusColor(d.status);
        var detail = d.details || (d.age_hours !== null ? "age: " + d.age_hours + "h / max: " + d.max_age_hours + "h" : "awaiting first run");
        var card = el("div", { className: "daemon-card" }, [
          el("span", { className: "status-dot " + color }),
          el("div", null, [
            el("div", { className: "daemon-name", textContent: d.daemon }),
            el("div", { className: "daemon-detail" }, [
              el("span", { className: "badge " + color, textContent: d.status }),
            ]),
            el("div", { className: "daemon-detail", textContent: detail }),
          ]),
        ]);
        dg.appendChild(card);
      });
      container.appendChild(dg);
    }
  }

  function makeCard(label, value, colorClass) {
    return el("div", { className: "card" }, [
      el("div", { className: "card-label", textContent: label }),
      el("div", { className: "card-value " + (colorClass || ""), textContent: value }),
    ]);
  }

  // ---------------------------------------------------------------------------
  // Weights tab (US-302)
  // ---------------------------------------------------------------------------

  var GROUP_META = {
    graph_signal:         { label: "Graph Signal" },
    dq_weights:           { label: "DQ Weights" },
    agent_thresholds:     { label: "Agent Thresholds" },
    free_mad:             { label: "Free-MAD" },
    behavioral:           { label: "Behavioral" },
    reward_composition:   { label: "Reward Composition" },
    lrf_topology:         { label: "LRF Topology" },
    exploration_schedule: { label: "Exploration Schedule" },
    session_multipliers:  { label: "Session Multipliers" },
  };

  var weightsLoaded = false;

  function loadWeightsTab() {
    if (weightsLoaded) return;
    weightsLoaded = true;

    var sparkSection = $("#weights-sparkline-section");
    var chartGrid = $("#weights-chart-grid");

    sparkSection.innerHTML = '<div class="loading">Loading weight data...</div>';
    chartGrid.innerHTML = "";

    Promise.all([
      fetchJSON("/api/weight-history"),
      fetchJSON("/api/reward-trend?last=200"),
      fetchJSON("/api/params"),
    ]).then(function (results) {
      var weightHistory = results[0];
      var rewardTrend = results[1];
      var paramsConfig = results[2];

      sparkSection.innerHTML = "";
      chartGrid.innerHTML = "";

      if (!weightHistory || weightHistory.length === 0) {
        sparkSection.innerHTML = '<div class="placeholder"><div>No weight snapshots recorded yet</div>' +
          '<div class="placeholder-tag">Snapshots are created by the bandit engine after each epoch</div></div>';
        return;
      }

      // --- Reward sparkline ---
      if (rewardTrend && rewardTrend.length > 0) {
        sparkSection.appendChild(el("div", { className: "section-title", textContent: "Reward Trend (last " + rewardTrend.length + " decisions)" }));
        var sparkWrap = el("div", { className: "sparkline-wrap" });
        var sparkCanvas = el("canvas", { className: "sparkline-canvas" });
        sparkCanvas.style.width = "100%";
        sparkCanvas.style.height = "48px";
        sparkCanvas.style.display = "block";
        sparkWrap.appendChild(sparkCanvas);
        sparkSection.appendChild(sparkWrap);

        requestAnimationFrame(function () {
          var rewards = rewardTrend.map(function (e) { return e.reward; });
          Charts.drawSparkline(sparkCanvas, rewards, {
            color: "#9ece6a",
            fillColor: "rgba(158, 206, 106, 0.15)",
            height: 48,
          });
        });
      } else {
        sparkSection.appendChild(el("div", { className: "section-title", textContent: "Reward Trend" }));
        sparkSection.appendChild(el("div", { className: "placeholder-tag", textContent: "No bandit history yet" }));
      }

      // --- Build param-to-group mapping ---
      var paramGroups = {};
      if (paramsConfig && paramsConfig.parameters) {
        paramsConfig.parameters.forEach(function (p) {
          paramGroups[p.id] = p.group;
        });
      }

      var allParamIds = {};
      weightHistory.forEach(function (snap) {
        Object.keys(snap.weights).forEach(function (pid) {
          allParamIds[pid] = true;
        });
      });

      var groupedParams = {};
      Object.keys(allParamIds).forEach(function (pid) {
        var group = paramGroups[pid] || "ungrouped";
        if (!groupedParams[group]) groupedParams[group] = [];
        groupedParams[group].push(pid);
      });

      // --- Date-to-numeric for x-axis ---
      var dateToX = {};
      var dates = weightHistory.map(function (s) { return s.date; });
      dates.forEach(function (d, i) { dateToX[d] = i; });

      function xFormatter(v) {
        var idx = Math.round(v);
        if (idx >= 0 && idx < dates.length) {
          return dates[idx].substring(5);
        }
        return String(v);
      }

      // --- Render one chart per group ---
      chartGrid.appendChild(el("div", { className: "section-title", textContent: "Weight Evolution by Group" }));
      var grid = el("div", { className: "weights-grid" });

      var groupOrder = [
        "graph_signal", "dq_weights", "agent_thresholds", "free_mad",
        "behavioral", "reward_composition", "lrf_topology", "exploration_schedule",
        "session_multipliers",
      ];

      Object.keys(groupedParams).forEach(function (g) {
        if (groupOrder.indexOf(g) === -1) groupOrder.push(g);
      });

      groupOrder.forEach(function (groupName) {
        var params = groupedParams[groupName];
        if (!params || params.length === 0) return;

        var meta = GROUP_META[groupName] || { label: groupName };

        var chartCard = el("div", { className: "chart-card" });
        var canvas = el("canvas", { className: "weight-chart-canvas" });
        canvas.style.width = "100%";
        canvas.style.height = "240px";
        canvas.style.display = "block";
        chartCard.appendChild(canvas);
        grid.appendChild(chartCard);

        var datasets = params.map(function (pid, pi) {
          var data = [];
          weightHistory.forEach(function (snap) {
            if (snap.weights[pid] !== undefined) {
              data.push({ x: dateToX[snap.date], y: snap.weights[pid] });
            }
          });
          var shortName = pid.replace(groupName + "_", "").replace("session_", "s:");
          return {
            label: shortName,
            data: data,
            color: Charts.PALETTE[pi % Charts.PALETTE.length],
          };
        });

        requestAnimationFrame(function () {
          Charts.drawLineChart(canvas, datasets, {
            title: meta.label,
            yLabel: "value",
            showGrid: true,
            showLegend: true,
            showTooltip: true,
            xFormatter: xFormatter,
          });
        });
      });

      chartGrid.appendChild(grid);

    }).catch(function (err) {
      sparkSection.innerHTML = "";
      chartGrid.innerHTML = "";
      chartGrid.appendChild(el("div", { className: "error-box" }, [
        el("div", { textContent: "Error loading weight data: " + err.message }),
        el("button", { className: "retry-btn", textContent: "Retry", onClick: function () {
          weightsLoaded = false;
          loadWeightsTab();
        }}),
      ]));
    });
  }

  // ---------------------------------------------------------------------------
  // Clusters tab (US-303)
  // ---------------------------------------------------------------------------

  var clustersLoaded = false;
  var clusterTooltip = null;

  function loadClusters() {
    var container = $("#clusters-content");
    if (!container) return;
    container.innerHTML = '<div class="loading">Loading clusters...</div>';

    Promise.all([
      fetchJSON("/api/cluster-projection"),
      fetchJSON("/api/clusters"),
    ]).then(function (results) {
      var projection = results[0];
      var rawClusters = results[1];
      renderClusters(container, projection, rawClusters);
      clustersLoaded = true;
    }).catch(function (err) {
      container.innerHTML = "";
      container.appendChild(el("div", { className: "error-box" }, [
        el("div", { textContent: "Error loading clusters: " + err.message }),
        el("button", { className: "retry-btn", textContent: "Retry", onClick: loadClusters }),
      ]));
    });
  }

  function renderClusters(container, projection, rawClusters) {
    container.innerHTML = "";

    // Empty state
    if (!projection.clusters || projection.clusters.length === 0) {
      container.appendChild(el("div", { className: "placeholder" }, [
        el("div", { textContent: "No cluster data available. Run the learning loop to generate clusters." }),
      ]));
      return;
    }

    // Silhouette badge
    var badgeRow = el("div", { className: "cluster-badge-row" });
    if (window.ClusterViz && projection.silhouette != null) {
      window.ClusterViz.renderSilhouetteBadge(badgeRow, projection.silhouette);
    }
    // k and updated info
    if (projection.k) {
      var infoSpan = el("span", {
        className: "cluster-info-tag",
        textContent: "k=" + projection.k + (projection.updated ? " | updated " + projection.updated.split("T")[0] : ""),
      });
      badgeRow.appendChild(infoSpan);
    }
    container.appendChild(badgeRow);

    // Canvas scatter plot
    var canvasWrap = el("div", { className: "cluster-canvas-wrap" });
    var canvas = el("canvas", { width: "600", height: "400" });
    canvasWrap.appendChild(canvas);
    container.appendChild(canvasWrap);

    if (window.ClusterViz) {
      window.ClusterViz.drawClusterScatter(canvas, projection.clusters);
      clusterTooltip = window.ClusterViz.initClusterTooltip(canvas);
    }

    // Cluster details table
    container.appendChild(el("div", { className: "section-title", textContent: "Cluster Details" }));

    var table = el("table", { className: "cluster-table" });
    var thead = el("thead", null, [
      el("tr", null, [
        el("th", { textContent: "ID" }),
        el("th", { textContent: "Size" }),
        el("th", { textContent: "Avg Reward" }),
        el("th", { textContent: "Decisions" }),
        el("th", { textContent: "Exploration" }),
        el("th", { textContent: "Maturity" }),
      ]),
    ]);
    table.appendChild(thead);

    var tbody = el("tbody");
    projection.clusters.forEach(function (c) {
      var matLabel = "young";
      var matColor = "#f7768e";
      if (c.decisionCount > 200) { matLabel = "mature"; matColor = "#9ece6a"; }
      else if (c.decisionCount >= 50) { matLabel = "moderate"; matColor = "#e0af68"; }

      tbody.appendChild(el("tr", null, [
        el("td", { textContent: "C" + c.clusterId }),
        el("td", { textContent: String(c.size) }),
        el("td", { textContent: c.avgReward != null ? c.avgReward.toFixed(4) : "n/a" }),
        el("td", { textContent: String(c.decisionCount) }),
        el("td", { textContent: c.explorationRate != null ? (c.explorationRate * 100).toFixed(1) + "%" : "n/a" }),
        el("td", { innerHTML: '<span style="color:' + matColor + '">' + matLabel + '</span>' }),
      ]));
    });
    table.appendChild(tbody);
    container.appendChild(table);
  }

  // ---------------------------------------------------------------------------
  // Timeline tab (US-304)
  // ---------------------------------------------------------------------------

  var timelineLoaded = false;

  function loadTimeline() {
    var panel = $("#panel-timeline");
    if (!panel) return;
    panel.innerHTML = '<div class="loading">Loading timeline...</div>';

    fetchJSON("/api/timeline")
      .then(function (events) {
        panel.innerHTML = "";
        if (!events || events.length === 0) {
          panel.appendChild(el("div", { className: "placeholder" }, [
            el("div", { textContent: "No rollback or A/B test events recorded yet" }),
          ]));
          return;
        }
        var summaryContainer = el("div");
        var timelineContainer = el("div");
        if (window.Timeline) {
          window.Timeline.renderTimelineSummary(summaryContainer, events);
          window.Timeline.renderTimeline(timelineContainer, events);
        }
        panel.appendChild(summaryContainer);
        panel.appendChild(timelineContainer);
        timelineLoaded = true;
      })
      .catch(function (err) {
        panel.innerHTML = "";
        panel.appendChild(el("div", { className: "error-box" }, [
          el("div", { textContent: "Error loading timeline: " + err.message }),
          el("button", { className: "retry-btn", textContent: "Retry", onClick: loadTimeline }),
        ]));
      });
  }

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------

  function loadDashboard() {
    var container = $("#overview-content");
    container.innerHTML = '<div class="loading">Loading...</div>';

    fetchJSON("/api/health")
      .then(function (data) {
        renderOverview(data);
        updateRefreshTimestamp();
      })
      .catch(function (err) {
        container.innerHTML = "";
        var box = el("div", { className: "error-box" }, [
          el("div", { textContent: "Error loading data: " + err.message }),
          el("button", { className: "retry-btn", textContent: "Retry", onClick: loadDashboard }),
        ]);
        container.appendChild(box);
      });
  }

  // ---------------------------------------------------------------------------
  // Auto-refresh
  // ---------------------------------------------------------------------------

  function updateRefreshTimestamp() {
    var ts = $("#last-refresh");
    if (ts) ts.textContent = "Last refresh: " + new Date().toLocaleTimeString();
  }

  function tickCountdown() {
    countdown--;
    if (countdown <= 0) {
      countdown = REFRESH_INTERVAL;
      loadDashboard();
    }
    var cd = $("#countdown");
    if (cd) cd.textContent = "Next refresh: " + countdown + "s";
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------

  function init() {
    initTabs();
    loadDashboard();
    refreshTimer = setInterval(tickCountdown, 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
