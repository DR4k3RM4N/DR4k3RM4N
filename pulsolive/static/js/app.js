// PulsoLive: gráficas sobre charts.js (taste-skill, MIT). Una pregunta por gráfica, una serie con
// el color de la marca, rejilla discreta, cifras tabulares en es-MX.
(function () {
  if (!window.Charts) return;
  var money = function (v) { return "$" + Math.round(v).toLocaleString("es-MX"); };
  var compactMoney = function (v) {
    if (Math.abs(v) >= 1000) return "$" + (v / 1000).toLocaleString("es-MX", { maximumFractionDigits: 0 }) + " mil";
    return money(v);
  };

  window.PulsoCharts = {
    daily: function (id, data) {
      var el = document.getElementById(id);
      if (!el) return;
      var opts = { labels: data.labels, values: data.values, format: money, tickFormat: compactMoney, height: 220 };
      if (data.best !== null && data.best !== undefined) {
        opts.annotations = [{ at: data.best, label: "Mejor día: " + money(data.values[data.best]), short: "Mejor día" }];
      }
      Charts.bars(el, opts);
    },

    // Pedidos por minuto (la serie principal) con los momentos del live marcados en el eje.
    liveOrders: function (id, data) {
      var el = document.getElementById(id);
      if (!el) return;
      var seen = {};
      var notes = [];
      data.events.forEach(function (e) {
        var i = data.labels.indexOf(e.minute);
        if (i < 0 || seen[i]) return;
        seen[i] = true;
        notes.push({ at: i, label: "Min " + e.minute + ": " + e.label, short: e.short || e.label });
      });
      Charts.bars(el, {
        labels: data.labels.map(function (m) { return "min " + m; }),
        values: data.orders,
        format: function (v) { return v + (v === 1 ? " pedido" : " pedidos"); },
        tickFormat: function (v) { return String(v); },
        height: 240,
        annotations: notes.slice(0, 12),
        xAt: data.labels.map(function (_, i) { return i; }).filter(function (i) { return i % 15 === 0; })
      });
    },

    liveViewers: function (id, data) {
      var el = document.getElementById(id);
      if (!el) return;
      Charts.line(el, {
        labels: data.labels.map(function (m) { return "min " + m; }),
        series: [{ name: "Espectadores", values: data.viewers }],
        format: function (v) { return Math.round(v).toLocaleString("es-MX") + " espectadores"; },
        tickFormat: function (v) { return Math.round(v).toLocaleString("es-MX"); },
        height: 140,
        xAt: data.labels.map(function (_, i) { return i; }).filter(function (i) { return i % 15 === 0; })
      });
    },

    heatmap: function (id, heat) {
      var el = document.getElementById(id);
      if (!el) return;
      var max = 0;
      heat.values.forEach(function (row) { row.forEach(function (v) { if (v !== null && v > max) max = v; }); });
      var html = '<div class="lbl"></div>';
      for (var h = 0; h < 24; h++) html += '<div class="lbl" style="justify-content:center">' + (h % 3 === 0 ? h : "") + "</div>";
      heat.weekdays.forEach(function (day, d) {
        html += '<div class="lbl">' + day.slice(0, 3) + "</div>";
        for (var h = 0; h < 24; h++) {
          var v = heat.values[d][h], n = heat.counts[d][h];
          var a = v === null ? 0 : 0.1 + 0.9 * (v / (max || 1));
          var style = v === null ? "" : "background: rgba(225,29,116," + a.toFixed(2) + ")";
          var title = v === null ? day + " " + h + ":00, sin lives" : day + " " + h + ":00 · " + money(v) + " por hora · " + n + (n === 1 ? " live" : " lives");
          html += '<div class="cell" style="' + style + '" title="' + title + '" aria-label="' + title + '"></div>';
        }
      });
      el.innerHTML = html;
    }
  };
})();
