/* global L, axios */
let map, layerGroup;

const levelStyles = {
  "熱帶性低氣壓": { color: "#8da0cb", weight: 2 },
  "輕度颱風":     { color: "#66c2a5", weight: 3 },
  "中度颱風":     { color: "#fc8d62", weight: 3.5 },
  "強烈颱風":     { color: "#e78ac3", weight: 4 }
};

function initMap() {
  // 世界視角
  map = L.map('map', { worldCopyJump: true }).setView([10, 140], 3);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 9,
    attribution: '&copy; OpenStreetMap'
  }).addTo(map);
  layerGroup = L.layerGroup().addTo(map);
}

function levelsSelected() {
  return Array.from(document.querySelectorAll('.level:checked')).map(el => el.value);
}
function basinsSelected() {
  return Array.from(document.querySelectorAll('.basin:checked')).map(el => el.value);
}

function buildTooltip(props) {
  const lines = [
    `<strong>${props.name}</strong>（${props.sid}）`,
    `盆地：${props.basin ?? "-"}`,
    `季節：${props.season}`,
    `期間：${new Date(props.time_start).toLocaleString()} ~ ${new Date(props.time_end).toLocaleString()}`,
    `等級：${props.category ?? "未知"}`,
    `最大風速：${props.max_wind_ms != null ? props.max_wind_ms + " m/s" : "—"}`
  ];
  return lines.join("<br/>");
}

function addTyphoonFeature(ft) {
  const coords = ft.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
  const cat = ft.properties.category || "熱帶性低氣壓";
  const style = levelStyles[cat] || { color: "#555", weight: 2 };

  const poly = L.polyline(coords, {
    color: style.color,
    weight: style.weight,
    opacity: 0.85
  }).addTo(layerGroup);

  const tooltip = L.tooltip({ sticky: true, direction: "top", className:"ty-name" })
    .setContent(buildTooltip(ft.properties));

  poly.on("mouseover", (e) => {
    poly.setStyle({ weight: style.weight + 1.5, opacity: 1.0 });
    tooltip.setLatLng(e.latlng);
    tooltip.addTo(map);
  });
  poly.on("mousemove", (e) => tooltip.setLatLng(e.latlng));
  poly.on("mouseout", () => {
    poly.setStyle({ weight: style.weight, opacity: 0.85 });
    map.removeLayer(tooltip);
  });
}

function clearMap() {
  if (layerGroup) layerGroup.clearLayers();
}

async function loadData() {
  const year = parseInt(document.getElementById("yearInput").value, 10);
  const levels = levelsSelected();
  const basins = basinsSelected();

  if (!year) { alert("請輸入西元年，例如 2015"); return; }
  if (basins.length === 0) {
    clearMap(); // ★ 關鍵：清掉之前畫的線
    alert("請至少勾選一個『盆地』再載入。");
    return;
  }

  clearMap(); // 每次載入前先清空，避免舊資料混在一起

  try {
    const params = new URLSearchParams();
    params.append("year", String(year));
    levels.forEach(lv => params.append("levels", lv));
    basins.forEach(b => params.append("basins", b));

    const res = await axios.get(`/api/typhoons?${params.toString()}`);
    const geo = res.data;

    if (!geo.features || geo.features.length === 0) {
      // 即便沒有資料，也讓底圖維持
      console.warn("No features for selection");
      return;
    }

    geo.features.forEach(addTyphoonFeature);

    // fit bounds
    const all = [];
    geo.features.forEach(ft => {
      ft.geometry.coordinates.forEach(([lon, lat]) => all.push([lat, lon]));
    });
    if (all.length) map.fitBounds(L.latLngBounds(all).pad(0.1));
  } catch (err) {
    console.error(err);
    alert("載入資料發生錯誤，請按 F12 檢查 Console。");
  }
}

function bindUI() {
  document.getElementById("btnLoad").addEventListener("click", loadData);
  document.querySelectorAll('#yearInput, .level, .basin').forEach(el => {
    el.addEventListener('change', loadData);
  });
}

window.addEventListener('DOMContentLoaded', () => {
  initMap();
  bindUI();
});
