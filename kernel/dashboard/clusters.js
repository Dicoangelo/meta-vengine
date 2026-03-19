/* clusters.js — LRF cluster scatter plot and visualization */

(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Maturity color mapping
  // ---------------------------------------------------------------------------

  function maturityColor(decisionCount) {
    if (decisionCount > 200) return "#9ece6a"; // green — mature
    if (decisionCount >= 50) return "#e0af68"; // yellow — moderate
    return "#f7768e"; // red — young
  }

  function maturityLabel(decisionCount) {
    if (decisionCount > 200) return "mature";
    if (decisionCount >= 50) return "moderate";
    return "young";
  }

  // ---------------------------------------------------------------------------
  // drawClusterScatter
  // ---------------------------------------------------------------------------

  /**
   * Draw a 2D scatter plot of LRF clusters on a canvas.
   *
   * @param {HTMLCanvasElement} canvas
   * @param {Array<Object>} clusters
   *   [{x, y, size, decisionCount, avgReward, explorationRate, clusterId}]
   * @param {Object} [options]
   *   - padding {number} — canvas padding in px (default 60)
   */
  function drawClusterScatter(canvas, clusters, options) {
    if (!canvas || !canvas.getContext) return;

    var opts = options || {};
    var padding = opts.padding || 60;
    var ctx = canvas.getContext("2d");
    var W = canvas.width;
    var H = canvas.height;
    var dpr = window.devicePixelRatio || 1;

    // Hi-DPI scaling
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    ctx.scale(dpr, dpr);

    // Background
    ctx.fillStyle = "#1a1b26";
    ctx.fillRect(0, 0, W, H);

    if (!clusters || clusters.length === 0) {
      ctx.fillStyle = "#565f89";
      ctx.font = "14px monospace";
      ctx.textAlign = "center";
      ctx.fillText("No cluster data available", W / 2, H / 2);
      return;
    }

    // Compute ranges
    var xs = clusters.map(function (c) { return c.x; });
    var ys = clusters.map(function (c) { return c.y; });
    var xMin = Math.min.apply(null, xs);
    var xMax = Math.max.apply(null, xs);
    var yMin = Math.min.apply(null, ys);
    var yMax = Math.max.apply(null, ys);

    // Pad ranges so points aren't on edges
    var xRange = (xMax - xMin) || 1;
    var yRange = (yMax - yMin) || 1;
    xMin -= xRange * 0.1;
    xMax += xRange * 0.1;
    yMin -= yRange * 0.1;
    yMax += yRange * 0.1;
    xRange = xMax - xMin;
    yRange = yMax - yMin;

    var plotW = W - 2 * padding;
    var plotH = H - 2 * padding;

    function toCanvasX(val) { return padding + ((val - xMin) / xRange) * plotW; }
    function toCanvasY(val) { return padding + plotH - ((val - yMin) / yRange) * plotH; }

    // Draw grid
    ctx.strokeStyle = "#24283b";
    ctx.lineWidth = 1;
    var gridLines = 5;
    for (var i = 0; i <= gridLines; i++) {
      var gx = padding + (i / gridLines) * plotW;
      var gy = padding + (i / gridLines) * plotH;
      ctx.beginPath(); ctx.moveTo(gx, padding); ctx.lineTo(gx, padding + plotH); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(padding, gy); ctx.lineTo(padding + plotW, gy); ctx.stroke();
    }

    // Draw axes
    ctx.strokeStyle = "#414868";
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(padding, padding); ctx.lineTo(padding, padding + plotH); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(padding, padding + plotH); ctx.lineTo(padding + plotW, padding + plotH); ctx.stroke();

    // Axis labels
    ctx.fillStyle = "#565f89";
    ctx.font = "11px monospace";
    ctx.textAlign = "center";
    ctx.fillText("PC1", W / 2, H - 8);
    ctx.save();
    ctx.translate(14, H / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("PC2", 0, 0);
    ctx.restore();

    // Radius scale: proportional to decision count
    var maxDec = Math.max.apply(null, clusters.map(function (c) { return c.decisionCount || 1; }));
    var minDec = Math.min.apply(null, clusters.map(function (c) { return c.decisionCount || 1; }));

    function circleRadius(decisionCount) {
      if (maxDec === minDec) return 30;
      var t = (decisionCount - minDec) / (maxDec - minDec);
      return 15 + t * 45; // min 15px, max 60px
    }

    // Draw cluster circles
    clusters.forEach(function (c) {
      var cx = toCanvasX(c.x);
      var cy = toCanvasY(c.y);
      var r = circleRadius(c.decisionCount || 0);
      var color = maturityColor(c.decisionCount || 0);

      // Filled circle with transparency
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = color + "44"; // alpha
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = "#c0caf5";
      ctx.font = "bold 12px monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("C" + c.clusterId, cx, cy);
    });

    // Store cluster positions for tooltip hit-testing (attach to canvas)
    canvas._clusterHitData = clusters.map(function (c) {
      return {
        cx: toCanvasX(c.x),
        cy: toCanvasY(c.y),
        r: circleRadius(c.decisionCount || 0),
        cluster: c,
      };
    });
  }

  // ---------------------------------------------------------------------------
  // Tooltip
  // ---------------------------------------------------------------------------

  function initClusterTooltip(canvas) {
    var tooltip = document.createElement("div");
    tooltip.className = "cluster-tooltip";
    tooltip.style.display = "none";
    document.body.appendChild(tooltip);

    canvas.addEventListener("mousemove", function (e) {
      var rect = canvas.getBoundingClientRect();
      var mx = e.clientX - rect.left;
      var my = e.clientY - rect.top;
      var hit = null;

      if (canvas._clusterHitData) {
        for (var i = 0; i < canvas._clusterHitData.length; i++) {
          var h = canvas._clusterHitData[i];
          var dx = mx - h.cx;
          var dy = my - h.cy;
          if (Math.sqrt(dx * dx + dy * dy) <= h.r) {
            hit = h.cluster;
            break;
          }
        }
      }

      if (hit) {
        tooltip.innerHTML =
          "<strong>Cluster " + hit.clusterId + "</strong><br>" +
          "Size: " + hit.size + "<br>" +
          "Avg Reward: " + (hit.avgReward != null ? hit.avgReward.toFixed(4) : "n/a") + "<br>" +
          "Decisions: " + hit.decisionCount + "<br>" +
          "Exploration: " + (hit.explorationRate != null ? (hit.explorationRate * 100).toFixed(1) + "%" : "n/a") + "<br>" +
          "Maturity: " + maturityLabel(hit.decisionCount);
        tooltip.style.display = "block";
        tooltip.style.left = (e.clientX + 12) + "px";
        tooltip.style.top = (e.clientY + 12) + "px";
      } else {
        tooltip.style.display = "none";
      }
    });

    canvas.addEventListener("mouseleave", function () {
      tooltip.style.display = "none";
    });

    return tooltip;
  }

  // ---------------------------------------------------------------------------
  // Silhouette badge
  // ---------------------------------------------------------------------------

  function renderSilhouetteBadge(container, score) {
    var color = "#9ece6a";
    var label = "excellent";
    if (score < 0.5) { color = "#f7768e"; label = "poor"; }
    else if (score < 0.7) { color = "#e0af68"; label = "fair"; }
    else if (score < 0.85) { color = "#7aa2f7"; label = "good"; }

    var badge = document.createElement("div");
    badge.className = "silhouette-badge";
    badge.innerHTML =
      '<span class="silhouette-label">Silhouette Score</span>' +
      '<span class="silhouette-value" style="color:' + color + '">' +
      (score != null ? score.toFixed(4) : "n/a") +
      '</span>' +
      '<span class="silhouette-quality" style="color:' + color + '">' + label + '</span>';
    container.appendChild(badge);
  }

  // ---------------------------------------------------------------------------
  // Export
  // ---------------------------------------------------------------------------

  window.ClusterViz = {
    drawClusterScatter: drawClusterScatter,
    initClusterTooltip: initClusterTooltip,
    renderSilhouetteBadge: renderSilhouetteBadge,
    maturityColor: maturityColor,
    maturityLabel: maturityLabel,
  };
})();
