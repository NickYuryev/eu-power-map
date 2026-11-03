// eu-power-map: colour the 15-country layer by hourly day-ahead price.
// Everything static, no build step. Loads polygons + the latest snapshot.

const VIRIDIS = [
  '#440154', '#482878', '#3e4a89', '#31688e', '#26828e',
  '#1f9e89', '#35b779', '#6dcd59', '#b4de2c', '#fde725',
];

// RdBu diverging, 11 stops. Red = negative margin (losing money),
// white at 0, blue = positive margin (making money).
const RDBU = [
  '#67001f', '#b2182b', '#d6604d', '#f4a582', '#fddbc7',
  '#f7f7f7',
  '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061',
];

const DATA_URL = '../data/prices_latest.json';
const FLOWS_URL = '../data/flows_latest.json';
const SPARK_URL = '../data/spark_latest.json';
const POLYGONS_URL = 'countries.json';

// Hard-coded reasonable visual centers; shoelace centroids of Norway or Denmark
// land in a fjord or in Sweden, which looks wrong on the arrow layer.
const CENTROIDS = {
  AT: [14.5, 47.5], BE: [4.5, 50.6], CH: [8.2, 46.9], CZ: [15.5, 49.7],
  DE: [10.4, 51.1], DK: [10.0, 56.0], ES: [-3.7, 40.4], FR: [2.5, 46.6],
  GB: [-1.5, 52.5], IT: [12.5, 42.8], NL: [5.4, 52.2], NO: [10.0, 61.5],
  PL: [19.1, 52.0], PT: [-8.5, 39.5], SE: [15.0, 60.0],
};

const FLOW_POSITIVE = '#ffb400'; // amber: flow follows A->B (ISO alphabetical)
const FLOW_NEGATIVE = '#4fc3f7'; // cyan:  flow goes B->A
const FLOW_MIN_MW = 50;          // hide noise below this

const VALUE_PROP = 'value';

const MODES = {
  price: {
    label: 'EUR/MWh',
    palette: VIRIDIS,
    stops: (vals) => {
      const [lo, hi] = percentile(vals, 0.02, 0.98);
      return linearStops(VIRIDIS, lo, hi, false);
    },
    pick: (snap, spark, iso, hour) => {
      const c = snap.countries[iso];
      return c ? c.prices[hour] : null;
    },
    rangeLabels: (snap, spark) => {
      const vals = flat(snap, (c) => c.prices);
      const [lo, hi] = percentile(vals, 0.02, 0.98);
      return [lo.toFixed(0), hi.toFixed(0)];
    },
  },
  spark: {
    label: 'EUR/MWh gross margin',
    palette: RDBU,
    stops: (vals) => {
      const [lo, hi] = percentile(vals, 0.02, 0.98);
      const half = Math.max(Math.abs(lo), Math.abs(hi), 1);
      return linearStops(RDBU, -half, half, true);
    },
    pick: (snap, spark, iso, hour) => {
      const c = spark && spark.countries[iso];
      return c ? c.spread[hour] : null;
    },
    rangeLabels: (snap, spark) => {
      if (!spark) return ['—', '—'];
      const vals = flat(spark, (c) => c.spread);
      const half = Math.max(...vals.map(Math.abs), 1);
      return [(-half).toFixed(0), (+half).toFixed(0)];
    },
  },
};

function flat(obj, pick) {
  const out = [];
  for (const c of Object.values(obj.countries)) {
    for (const v of pick(c)) if (v != null) out.push(v);
  }
  return out;
}

function percentile(vals, qlo, qhi) {
  if (!vals.length) return [0, 100];
  const s = [...vals].sort((a, b) => a - b);
  const p = (q) => s[Math.max(0, Math.min(s.length - 1, Math.floor(q * (s.length - 1))))];
  return [p(qlo), p(qhi)];
}

function linearStops(palette, lo, hi, symmetric) {
  const stops = [];
  for (let i = 0; i < palette.length; i++) {
    stops.push(lo + ((hi - lo) * i) / (palette.length - 1), palette[i]);
  }
  return stops;
}

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
const legendUnit = $('legend-unit');
const legendBar = document.querySelector('#legend .bar');
const dateSub = $('date-sub');
const tooltip = $('tooltip');
const toggleBtns = document.querySelectorAll('[data-mode]');

let polygons = null;
let snapshot = null;
let spark = null;
let flows = null;
let hourIdx = 0;
let mode = 'price';

function setHour() {
  const hour = snapshot.hours[hourIdx];
  hourLabel.textContent = hour ? hour.slice(11, 16) : '—';
  const m = MODES[mode];
  const zoneFeats = polygons.features.map((f) => {
    const v = m.pick(snapshot, spark, f.properties.iso, hourIdx);
    return { ...f, properties: { ...f.properties, [VALUE_PROP]: v } };
  });
  map.getSource('zones').setData({ type: 'FeatureCollection', features: zoneFeats });
  if (flows) map.getSource('flows').setData(flowFeatures(hourIdx));
}

function applyMode() {
  const m = MODES[mode];
  const [lo, hi] = m.rangeLabels(snapshot, spark);
  legendMin.textContent = lo;
  legendMax.textContent = hi;
  legendUnit.textContent = m.label;
  legendBar.style.background =
    'linear-gradient(to right, ' + m.palette.join(', ') + ')';
  const vals = flat(mode === 'spark' ? spark : snapshot,
                    (c) => mode === 'spark' ? c.spread : c.prices);
  const paint = [
    'case',
    ['==', ['get', VALUE_PROP], null], '#222',
    ['interpolate', ['linear'], ['get', VALUE_PROP], ...m.stops(vals)],
  ];
  // Style may not be fully loaded on the first call; retry on idle.
  const trySet = () => {
    try { map.setPaintProperty('zone-fill', 'fill-color', paint); setHour(); }
    catch { map.once('idle', trySet); }
  };
  trySet();
}

function flowFeatures(hour) {
  const feats = [];
  for (const [key, vals] of Object.entries(flows.pairs)) {
    const v = vals[hour];
    if (v == null || Math.abs(v) < FLOW_MIN_MW) continue;
    const [a, b] = key.split('-');
    const ca = CENTROIDS[a], cb = CENTROIDS[b];
    if (!ca || !cb) continue;
    feats.push({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [ca, cb] },
      properties: { pair: key, from: v > 0 ? a : b, to: v > 0 ? b : a,
                    flow: v, mag: Math.abs(v) },
    });
  }
  return { type: 'FeatureCollection', features: feats };
}

async function init() {
  [polygons, snapshot, flows, spark] = await Promise.all([
    fetch(POLYGONS_URL).then((r) => r.json()),
    fetch(DATA_URL).then((r) => r.json()),
    fetch(FLOWS_URL).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    fetch(SPARK_URL).then((r) => (r.ok ? r.json() : null)).catch(() => null),
  ]);
  slider.max = String(snapshot.hours.length - 1);
  const now = new Date();
  hourIdx = Math.min(now.getHours(), snapshot.hours.length - 1);
  slider.value = String(hourIdx);
  dateSub.textContent = `${snapshot.date} · ${Object.keys(snapshot.countries).length} zones`;

  await new Promise((res) => (map.loaded() ? res() : map.once('load', res)));

  map.addSource('zones', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({
    id: 'zone-fill',
    type: 'fill',
    source: 'zones',
    paint: { 'fill-color': '#222', 'fill-opacity': 0.78 },
  });
  map.addLayer({
    id: 'zone-outline',
    type: 'line',
    source: 'zones',
    paint: { 'line-color': '#111', 'line-width': 0.6 },
  });

  map.addSource('flows', { type: 'geojson',
    data: flows ? flowFeatures(hourIdx) : { type: 'FeatureCollection', features: [] } });
  map.addLayer({
    id: 'flow-line',
    type: 'line',
    source: 'flows',
    layout: { 'line-cap': 'round' },
    paint: {
      'line-color': ['case', ['>', ['get', 'flow'], 0], FLOW_POSITIVE, FLOW_NEGATIVE],
      'line-opacity': 0.8,
      // sqrt-scaled width: 500 MW -> 2px, 2000 -> 4px, 5000 -> 6px
      'line-width': ['*', 0.09, ['sqrt', ['get', 'mag']]],
    },
  });

  applyMode();
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
    setHour();
  });

  toggleBtns.forEach((b) => b.addEventListener('click', () => {
    const next = b.dataset.mode;
    if (next === mode) return;
    if (next === 'spark' && !spark) return;  // nothing to show yet
    mode = next;
    toggleBtns.forEach((x) => x.classList.toggle('on', x.dataset.mode === mode));
    applyMode();
  }));

  map.on('mousemove', 'zone-fill', (e) => {
    if (!e.features.length) return;
    const f = e.features[0];
    const v = f.properties[VALUE_PROP];
    const unit = MODES[mode].label;
    tooltip.innerHTML = `<div class="n">${f.properties.name}</div>
      <div class="p">${v == null ? 'no data' : Number(v).toFixed(1) + ' ' + unit}</div>`;
    showTooltip(e.originalEvent.clientX, e.originalEvent.clientY);
  });
  map.on('mouseleave', 'zone-fill', () => { tooltip.style.display = 'none'; });

  map.on('mousemove', 'flow-line', (e) => {
    if (!e.features.length) return;
    const f = e.features[0];
    const mw = Math.round(f.properties.mag);
    tooltip.innerHTML = `<div class="n">${f.properties.from} &rarr; ${f.properties.to}</div>
      <div class="p">${mw.toLocaleString()} MW</div>`;
    showTooltip(e.originalEvent.clientX, e.originalEvent.clientY);
  });
  map.on('mouseleave', 'flow-line', () => { tooltip.style.display = 'none'; });
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
