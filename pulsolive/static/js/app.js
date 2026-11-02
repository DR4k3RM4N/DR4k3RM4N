// Utilidades de gráficas de PulsoLive (Chart.js)
(function () {
  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function money(v) { return "$" + Math.round(v).toLocaleString("es-MX"); }

  function baseOptions() {
    const grid = css("--border"), text = css("--muted");
    return {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { color: text, boxWidth: 12 } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: text, maxRotation: 0, autoSkipPadding: 12 } },
        y: { grid: { color: grid }, ticks: { color: text }, beginAtZero: true },
      },
    };
  }

  window.PulsoCharts = {
    daily(canvasId, data) {
      const el = document.getElementById(canvasId);
      if (!el || !window.Chart) return;
      const opts = baseOptions();
      opts.plugins.legend.display = false;
      opts.scales.y.ticks.callback = money;
      opts.plugins.tooltip = { callbacks: { label: (c) => " Ventas: " + money(c.parsed.y) } };
      new Chart(el, {
        type: "bar",
        data: { labels: data.labels, datasets: [{ data: data.values, backgroundColor: css("--accent"), borderRadius: 4 }] },
        options: opts,
      });
    },

    live(canvasId, data) {
      const el = document.getElementById(canvasId);
      if (!el || !window.Chart) return;
      const opts = baseOptions();
      opts.scales.y1 = { position: "right", grid: { display: false }, ticks: { color: css("--muted") }, beginAtZero: true };
      opts.scales.x.title = { display: true, text: "Minuto", color: css("--muted") };
      const eventsByMinute = {};
      data.events.forEach((e) => { (eventsByMinute[e.minute] = eventsByMinute[e.minute] || []).push(e.label); });
      opts.plugins.tooltip = { callbacks: { afterBody: (items) => {
        const m = data.labels[items[0].dataIndex];
        return eventsByMinute[m] ? ["", "Momento: " + eventsByMinute[m].join(", ")] : [];
      } } };
      const markers = data.labels.map((m) => (eventsByMinute[m] ? Math.max(...data.orders) * 1.05 : null));
      new Chart(el, {
        data: {
          labels: data.labels,
          datasets: [
            { type: "bar", label: "Pedidos", data: data.orders, backgroundColor: css("--accent"), borderRadius: 3, yAxisID: "y" },
            { type: "line", label: "Espectadores", data: data.viewers, borderColor: css("--accent-2"), pointRadius: 0, tension: .3, yAxisID: "y1" },
            { type: "line", label: "Momentos", data: markers, showLine: false, pointStyle: "triangle", pointRadius: 7, backgroundColor: css("--warn"), borderColor: css("--warn"), yAxisID: "y" },
          ],
        },
        options: opts,
      });
    },

    heatmap(containerId, heat) {
      const el = document.getElementById(containerId);
      if (!el) return;
      let max = 0;
      heat.values.forEach((row) => row.forEach((v) => { if (v !== null && v > max) max = v; }));
      let html = '<div class="lbl"></div>';
      for (let h = 0; h < 24; h++) html += '<div class="lbl" style="justify-content:center">' + (h % 3 === 0 ? h : "") + "</div>";
      heat.weekdays.forEach((day, d) => {
        html += '<div class="lbl">' + day.slice(0, 3) + "</div>";
        for (let h = 0; h < 24; h++) {
          const v = heat.values[d][h], n = heat.counts[d][h];
          const alpha = v === null ? 0 : 0.12 + 0.88 * (v / (max || 1));
          const style = v === null ? "" : "background: rgba(225,29,116," + alpha.toFixed(2) + ")";
          const title = v === null ? day + " " + h + ":00 · sin lives" : day + " " + h + ":00 · " + money(v) + "/h · " + n + " lives";
          html += '<div class="cell" style="' + style + '" title="' + title + '"></div>';
        }
      });
      el.innerHTML = html;
    },
  };
})();
