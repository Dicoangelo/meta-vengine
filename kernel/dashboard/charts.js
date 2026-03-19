/* charts.js — Reusable Canvas charting module for meta-vengine dashboard.
 * No external libraries. Uses Tokyo Night color palette from CSS vars.
 */

(function (root) {
  "use strict";

  // ---------------------------------------------------------------------------
  // Color palette (Tokyo Night)
  // ---------------------------------------------------------------------------

  var PALETTE = [
    "#7aa2f7", // accent blue
    "#9ece6a", // green
    "#e0af68", // yellow
    "#f7768e", // red
    "#bb9af7", // purple
    "#7dcfff", // cyan
    "#ff9e64", // orange
    "#c0caf5", // light text
    "#3d59a1", // dim blue
    "#73daca", // teal
  ];

  var GRID_COLOR = "rgba(86, 95, 137, 0.25)";    // --text-secondary @ 25%
  var AXIS_COLOR = "rgba(86, 95, 137, 0.6)";
  var TEXT_COLOR = "#565f89";
  var LABEL_COLOR = "#c0caf5";
  var BG_TOOLTIP = "rgba(31, 35, 53, 0.95)";
  var FONT_MONO = "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace";
  var FONT_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function computeScale(data, accessor, padding) {
    if (!data || data.length === 0) return { min: 0, max: 1 };
    var values = data.map(accessor);
    var min = Math.min.apply(null, values);
    var max = Math.max.apply(null, values);
    if (min === max) {
      min -= 0.5;
      max += 0.5;
    }
    var range = max - min;
    var pad = range * (padding || 0.08);
    return { min: min - pad, max: max + pad };
  }

  function niceSteps(min, max, targetSteps) {
    var range = max - min;
    if (range === 0) return [min];
    var rough = range / (targetSteps || 5);
    var mag = Math.pow(10, Math.floor(Math.log10(rough)));
    var norm = rough / mag;
    var step;
    if (norm <= 1.5) step = 1 * mag;
    else if (norm <= 3) step = 2 * mag;
    else if (norm <= 7) step = 5 * mag;
    else step = 10 * mag;

    var start = Math.ceil(min / step) * step;
    var steps = [];
    for (var v = start; v <= max + step * 0.001; v += step) {
      steps.push(Math.round(v * 1e10) / 1e10);
    }
    return steps;
  }

  function formatNum(v) {
    if (Math.abs(v) >= 1000) return v.toFixed(0);
    if (Math.abs(v) >= 10) return v.toFixed(1);
    if (Math.abs(v) >= 1) return v.toFixed(2);
    return v.toFixed(3);
  }

  function nearestPoint(datasets, mx, my, plotArea) {
    var best = null;
    var bestDist = Infinity;
    for (var di = 0; di < datasets.length; di++) {
      var ds = datasets[di];
      for (var pi = 0; pi < ds._screenPoints.length; pi++) {
        var sp = ds._screenPoints[pi];
        var dx = sp.sx - mx;
        var dy = sp.sy - my;
        var dist = dx * dx + dy * dy;
        if (dist < bestDist) {
          bestDist = dist;
          best = { dataset: di, index: pi, sx: sp.sx, sy: sp.sy, x: sp.x, y: sp.y, label: ds.label };
        }
      }
    }
    if (best && bestDist > 900) return null; // max 30px distance
    return best;
  }

  // ---------------------------------------------------------------------------
  // drawLineChart
  // ---------------------------------------------------------------------------

  function drawLineChart(canvas, datasets, options) {
    if (!canvas || !canvas.getContext) return;
    options = options || {};

    var dpr = window.devicePixelRatio || 1;
    var displayW = canvas.clientWidth || canvas.width;
    var displayH = canvas.clientHeight || canvas.height;
    canvas.width = displayW * dpr;
    canvas.height = displayH * dpr;
    var ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);

    // Margins
    var margin = { top: 36, right: 16, bottom: 40, left: 56 };
    if (options.showLegend !== false && datasets.length > 1) margin.bottom += 24;
    if (options.title) margin.top += 4;

    var plotW = displayW - margin.left - margin.right;
    var plotH = displayH - margin.top - margin.bottom;
    if (plotW < 20 || plotH < 20) return;

    // Flatten all data for scale computation
    var allPoints = [];
    datasets.forEach(function (ds) { allPoints = allPoints.concat(ds.data); });
    if (allPoints.length === 0) return;

    var xScale = computeScale(allPoints, function (p) { return p.x; }, 0.02);
    var yScale = computeScale(allPoints, function (p) { return p.y; }, 0.08);

    function toScreenX(v) { return margin.left + ((v - xScale.min) / (xScale.max - xScale.min)) * plotW; }
    function toScreenY(v) { return margin.top + plotH - ((v - yScale.min) / (yScale.max - yScale.min)) * plotH; }

    // Background
    ctx.fillStyle = "transparent";
    ctx.fillRect(0, 0, displayW, displayH);

    // Grid lines
    if (options.showGrid !== false) {
      ctx.strokeStyle = GRID_COLOR;
      ctx.lineWidth = 0.5;
      var ySteps = niceSteps(yScale.min, yScale.max, 5);
      ySteps.forEach(function (v) {
        var sy = toScreenY(v);
        ctx.beginPath();
        ctx.moveTo(margin.left, sy);
        ctx.lineTo(margin.left + plotW, sy);
        ctx.stroke();
      });
    }

    // Axes
    ctx.strokeStyle = AXIS_COLOR;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margin.left, margin.top);
    ctx.lineTo(margin.left, margin.top + plotH);
    ctx.lineTo(margin.left + plotW, margin.top + plotH);
    ctx.stroke();

    // Y-axis labels
    ctx.fillStyle = TEXT_COLOR;
    ctx.font = "11px " + FONT_MONO;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    var ySteps2 = niceSteps(yScale.min, yScale.max, 5);
    ySteps2.forEach(function (v) {
      var sy = toScreenY(v);
      ctx.fillText(formatNum(v), margin.left - 6, sy);
    });

    // X-axis labels
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    // For date-based x-axes, show a subset of labels
    var xAllValues = allPoints.map(function (p) { return p.x; });
    xAllValues.sort(function (a, b) { return a - b; });
    var uniqueX = [];
    xAllValues.forEach(function (v) {
      if (uniqueX.length === 0 || uniqueX[uniqueX.length - 1] !== v) uniqueX.push(v);
    });
    var xLabelInterval = Math.max(1, Math.floor(uniqueX.length / 8));
    for (var xi = 0; xi < uniqueX.length; xi += xLabelInterval) {
      var xv = uniqueX[xi];
      var sx = toScreenX(xv);
      var label;
      if (options.xFormatter) {
        label = options.xFormatter(xv);
      } else {
        label = formatNum(xv);
      }
      ctx.fillText(label, sx, margin.top + plotH + 6);
    }

    // Axis titles
    if (options.yLabel) {
      ctx.save();
      ctx.fillStyle = TEXT_COLOR;
      ctx.font = "11px " + FONT_SANS;
      ctx.translate(14, margin.top + plotH / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ctx.fillText(options.yLabel, 0, 0);
      ctx.restore();
    }

    // Title
    if (options.title) {
      ctx.fillStyle = LABEL_COLOR;
      ctx.font = "bold 13px " + FONT_SANS;
      ctx.textAlign = "left";
      ctx.textBaseline = "top";
      ctx.fillText(options.title, margin.left, 10);
    }

    // Draw lines
    datasets.forEach(function (ds, di) {
      var color = ds.color || PALETTE[di % PALETTE.length];
      var sorted = ds.data.slice().sort(function (a, b) { return a.x - b.x; });

      // Cache screen points for tooltip
      ds._screenPoints = sorted.map(function (p) {
        return { sx: toScreenX(p.x), sy: toScreenY(p.y), x: p.x, y: p.y };
      });

      ctx.strokeStyle = color;
      ctx.lineWidth = 1.8;
      ctx.lineJoin = "round";
      ctx.beginPath();
      sorted.forEach(function (p, i) {
        var sx = toScreenX(p.x);
        var sy = toScreenY(p.y);
        if (i === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
      });
      ctx.stroke();

      // Draw dots
      ctx.fillStyle = color;
      ds._screenPoints.forEach(function (sp) {
        ctx.beginPath();
        ctx.arc(sp.sx, sp.sy, 3, 0, Math.PI * 2);
        ctx.fill();
      });
    });

    // Legend
    if (options.showLegend !== false && datasets.length > 1) {
      var legendY = displayH - 16;
      ctx.font = "11px " + FONT_SANS;
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";
      var lx = margin.left;
      datasets.forEach(function (ds, di) {
        var color = ds.color || PALETTE[di % PALETTE.length];
        ctx.fillStyle = color;
        ctx.fillRect(lx, legendY - 4, 12, 8);
        lx += 16;
        ctx.fillStyle = TEXT_COLOR;
        var name = ds.label || "series " + di;
        // Shorten long names
        if (name.length > 20) name = name.substring(0, 18) + "..";
        ctx.fillText(name, lx, legendY);
        lx += ctx.measureText(name).width + 16;
      });
    }

    // Tooltip on hover
    if (options.showTooltip !== false) {
      var plotArea = { left: margin.left, top: margin.top, right: margin.left + plotW, bottom: margin.top + plotH };
      var tooltip = null;

      canvas.addEventListener("mousemove", function (e) {
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var hit = nearestPoint(datasets, mx, my, plotArea);

        // Redraw (simple: re-call). Instead we overlay a tooltip div
        var existingTip = canvas.parentNode.querySelector(".chart-tooltip");
        if (!hit) {
          if (existingTip) existingTip.style.display = "none";
          return;
        }

        if (!existingTip) {
          existingTip = document.createElement("div");
          existingTip.className = "chart-tooltip";
          existingTip.style.cssText = "position:absolute;pointer-events:none;background:" + BG_TOOLTIP +
            ";border:1px solid rgba(86,95,137,0.5);border-radius:4px;padding:6px 10px;font-size:11px;" +
            "font-family:" + FONT_MONO + ";color:#c0caf5;white-space:nowrap;z-index:10;";
          canvas.parentNode.style.position = "relative";
          canvas.parentNode.appendChild(existingTip);
        }

        var xLabel = options.xFormatter ? options.xFormatter(hit.x) : formatNum(hit.x);
        existingTip.innerHTML = "<strong>" + hit.label + "</strong><br>" + xLabel + ": " + formatNum(hit.y);
        existingTip.style.display = "block";

        // Position tooltip
        var tipLeft = hit.sx + 12;
        var tipTop = hit.sy - 30;
        if (tipLeft + 150 > canvas.clientWidth) tipLeft = hit.sx - 150;
        if (tipTop < 0) tipTop = hit.sy + 12;
        existingTip.style.left = tipLeft + "px";
        existingTip.style.top = tipTop + "px";
      });

      canvas.addEventListener("mouseleave", function () {
        var tip = canvas.parentNode.querySelector(".chart-tooltip");
        if (tip) tip.style.display = "none";
      });
    }
  }

  // ---------------------------------------------------------------------------
  // drawSparkline
  // ---------------------------------------------------------------------------

  function drawSparkline(canvas, data, options) {
    if (!canvas || !canvas.getContext || !data || data.length === 0) return;
    options = options || {};

    var dpr = window.devicePixelRatio || 1;
    var displayW = canvas.clientWidth || canvas.width;
    var displayH = canvas.clientHeight || (options.height || 40);
    canvas.width = displayW * dpr;
    canvas.height = displayH * dpr;
    var ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);

    var color = options.color || PALETTE[0];
    var fillColor = options.fillColor || (color + "33"); // 20% opacity

    var pad = 2;
    var w = displayW - pad * 2;
    var h = displayH - pad * 2;

    var yMin = Math.min.apply(null, data);
    var yMax = Math.max.apply(null, data);
    if (yMin === yMax) { yMin -= 0.5; yMax += 0.5; }

    function sx(i) { return pad + (i / (data.length - 1)) * w; }
    function sy(v) { return pad + h - ((v - yMin) / (yMax - yMin)) * h; }

    // Fill
    ctx.beginPath();
    ctx.moveTo(sx(0), sy(data[0]));
    for (var i = 1; i < data.length; i++) {
      ctx.lineTo(sx(i), sy(data[i]));
    }
    ctx.lineTo(sx(data.length - 1), pad + h);
    ctx.lineTo(sx(0), pad + h);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.moveTo(sx(0), sy(data[0]));
    for (var j = 1; j < data.length; j++) {
      ctx.lineTo(sx(j), sy(data[j]));
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.stroke();

    // End dot
    ctx.beginPath();
    ctx.arc(sx(data.length - 1), sy(data[data.length - 1]), 2.5, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }

  // ---------------------------------------------------------------------------
  // Exports
  // ---------------------------------------------------------------------------

  root.Charts = {
    drawLineChart: drawLineChart,
    drawSparkline: drawSparkline,
    PALETTE: PALETTE,
  };

})(window);
