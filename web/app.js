// eu-power-map: colour the 15-country layer by hourly day-ahead price.
// Everything static, no build step. Loads polygons + the latest snapshot.

const VIRIDIS = [
  '#440154', '#482878', '#3e4a89', '#31688e', '#26828e',
  '#1f9e89', '#35b779', '#6dcd59', '#b4de2c', '#fde725',
];

const DATA_URL = '../data/prices_latest.json';
const POLYGONS_URL = 'countries.json';

const PRICE_PROP = 'price';

const map = new maplibregl.Map({
  container: 'map',
  // No basemap: Carto now requires an API key and tile services add noise
  // we don't need for a 15-polygon zone map. Solid dark background, done.
  style: {
    version: 8,
    sources: {},
    layers: [{
      id: 'background',
      type: 'background',
      paint: { 'background-color': '#0b0d10' },
    }],
  },
  center: [10, 51],
  zoom: 3,
  attributionControl: { compact: true },
  // Lets screenshot tools capture the canvas; cost is minor.
  preserveDrawingBuffer: true,
});

const $ = (id) => document.getElementById(id);
const slider = $('hour');
const hourLabel = $('hour-label');
const legendMin = $('legend-min');
const legendMax = $('legend-max');
const dateSub = $('date-sub');
const tooltip = $('tooltip');

let polygons = null;
let snapshot = null;
let hourIdx = 0;
let priceRange = [0, 100];

function colorStops(min, max) {
  const stops = [];
  for (let i = 0; i < VIRIDIS.length; i++) {
    stops.push(min + ((max - min) * i) / (VIRIDIS.length - 1), VIRIDIS[i]);
  }
  return stops;
}

function setHourPrices() {
  const hour = snapshot.hours[hourIdx];
  hourLabel.textContent = hour ? hour.slice(11, 16) : '—';
  const feats = polygons.features.map((f) => {
    const c = snapshot.countries[f.properties.iso];
    const price = c ? c.prices[hourIdx] : null;
    return { ...f, properties: { ...f.properties, [PRICE_PROP]: price } };
  });
  const src = map.getSource('zones');
  src.setData({ type: 'FeatureCollection', features: feats });
}

function computeRange() {
  const vals = [];
  for (const c of Object.values(snapshot.countries)) {
    for (const v of c.prices) if (v != null) vals.push(v);
  }
  if (!vals.length) return [0, 100];
  vals.sort((a, b) => a - b);
  // Trim extremes a bit so one spiky zone doesn't flatten the ramp.
  const p = (q) => vals[Math.max(0, Math.min(vals.length - 1, Math.floor(q * (vals.length - 1))))];
  return [p(0.02), p(0.98)];
}

async function init() {
  [polygons, snapshot] = await Promise.all([
    fetch(POLYGONS_URL).then((r) => r.json()),
    fetch(DATA_URL).then((r) => r.json()),
  ]);
  slider.max = String(snapshot.hours.length - 1);
  const now = new Date();
  hourIdx = Math.min(now.getHours(), snapshot.hours.length - 1);
  slider.value = String(hourIdx);
  dateSub.textContent = `${snapshot.date} · ${Object.keys(snapshot.countries).length} zones`;
  priceRange = computeRange();
  legendMin.textContent = priceRange[0].toFixed(0);
  legendMax.textContent = priceRange[1].toFixed(0);

  await new Promise((res) => (map.loaded() ? res() : map.once('load', res)));

  map.addSource('zones', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({
    id: 'zone-fill',
    type: 'fill',
    source: 'zones',
    paint: {
      'fill-color': [
        'case',
        ['==', ['get', PRICE_PROP], null], '#222',
        ['interpolate', ['linear'], ['get', PRICE_PROP], ...colorStops(priceRange[0], priceRange[1])],
      ],
      'fill-opacity': 0.78,
    },
  });
  map.addLayer({
    id: 'zone-outline',
    type: 'line',
    source: 'zones',
    paint: { 'line-color': '#111', 'line-width': 0.6 },
  });

  setHourPrices();
  fitToZones();
  wireInteraction();
}

function fitToZones() {
  let minX = 180, minY = 90, maxX = -180, maxY = -90;
  for (const f of polygons.features) {
    const walk = (c) => {
      if (typeof c[0] === 'number') {
        if (c[0] < minX) minX = c[0];
        if (c[0] > maxX) maxX = c[0];
        if (c[1] < minY) minY = c[1];
        if (c[1] > maxY) maxY = c[1];
      } else {
        for (const n of c) walk(n);
      }
    };
    walk(f.geometry.coordinates);
  }
  map.fitBounds([[minX, minY], [maxX, maxY]], { padding: { top: 160, left: 20, right: 20, bottom: 40 } });
}

function wireInteraction() {
  slider.addEventListener('input', () => {
    hourIdx = Number(slider.value);
    setHourPrices();
  });

  map.on('mousemove', 'zone-fill', (e) => {
    if (!e.features.length) return;
    const f = e.features[0];
    const p = f.properties[PRICE_PROP];
    tooltip.innerHTML = `<div class="n">${f.properties.name}</div>
      <div class="p">${p == null ? 'no data' : Number(p).toFixed(1) + ' EUR/MWh'}</div>`;
    showTooltip(e.originalEvent.clientX, e.originalEvent.clientY);
  });
  map.on('mouseleave', 'zone-fill', () => { tooltip.style.display = 'none'; });
}

function showTooltip(x, y) {
  tooltip.style.display = 'block';
  // Measure then flip so the tooltip never crosses a viewport edge.
  const w = tooltip.offsetWidth, h = tooltip.offsetHeight;
  const flipX = x + 14 + w > window.innerWidth;
  const flipY = y + 14 + h > window.innerHeight;
  tooltip.style.left = (flipX ? x - w - 14 : x + 14) + 'px';
  tooltip.style.top  = (flipY ? y - h - 14 : y + 14) + 'px';
}

init().catch((err) => {
  dateSub.textContent = 'failed to load — see console';
  console.error(err);
});
