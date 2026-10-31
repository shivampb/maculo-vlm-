// Maculo web app. No framework, no build step.
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const store = {
  get(k, d) {
    try { const v = localStorage.getItem("maculo." + k); return v === null ? d : JSON.parse(v); } catch (_) { return d; }
  },
  set(k, v) {
    try { localStorage.setItem("maculo." + k, JSON.stringify(v)); } catch (_) {}
  },
};

const MAX_SIDE = 1024;
const state = {
  meta: null,
  blob: null, // the downscaled photo we upload
  imageId: null,
  size: { w: 0, h: 0 },
  points: [], // {x, y, include} in 0..1
  box: null, // [x0, y0, x1, y1] in 0..1, dragged around the spot
  mode: "select",
  maskMode: "best",
  view: store.get("view", "outline"), // outline | spotlight | heatmap
  crop: true,
  selected: new Set(),
  custom: [],
  result: null,
  cursor: { x: 0.5, y: 0.5 },
  controller: null,
  seq: 0,
};

/* ---------------- API ---------------- */
class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function api(path, opts = {}) {
  let r;
  try {
    r = await fetch(path, opts);
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError(0, "Can't reach the Maculo server. Check that it's running.");
  }
  if (r.status === 204) return null;
  let body = null;
  try { body = await r.json(); } catch (_) {}
  if (!r.ok) throw new ApiError(r.status, (body && body.detail) || `Request failed (${r.status}).`);
  return body;
}

/* ---------------- Status ---------------- */
function status(msg, isError = false) {
  const el = $("#status");
  el.textContent = msg || "";
  el.classList.toggle("error", isError);
}
function busy(on) {
  $("#stage-busy").hidden = !on;
  $("#stage").setAttribute("aria-busy", on ? "true" : "false");
}

/* ---------------- Models warming up ---------------- */
async function loadMeta() {
  const banner = $("#model-banner");
  try {
    state.meta = await api("/api/v1/meta");
  } catch (e) {
    banner.hidden = false;
    banner.classList.add("error");
    banner.textContent = e.message;
    setTimeout(loadMeta, 4000);
    return;
  }
  $("#foot-meta").textContent = `Version ${state.meta.version}`;
  if (!labelsReady) initLabels();
  if (state.meta.ready) {
    banner.hidden = true;
    if (state.blob && !state.imageId) upload();
    return;
  }
  const r = await fetch("/readyz").then((x) => x.json()).catch(() => ({}));
  banner.hidden = false;
  if (r.status === "error") {
    banner.classList.add("error");
    banner.textContent = "The analysis models failed to load. Check the server window for details.";
    return;
  }
  banner.classList.remove("error");
  banner.innerHTML = '<span class="spinner" aria-hidden="true"></span>';
  banner.append("Getting the models ready. This takes up to a minute the first time.");
  setTimeout(loadMeta, 2500);
}

/* ---------------- Conditions ---------------- */
let labelsReady = false;

function initLabels() {
  labelsReady = true;
  const saved = store.get("labels", null);
  state.custom = store.get("custom", []);
  state.selected = new Set(saved || state.meta.default_selection);
  renderLabels();
}

function saveLabels() {
  store.set("labels", [...state.selected]);
  store.set("custom", state.custom);
}

function renderLabels() {
  const wrap = $("#groups");
  const open = new Set($$("details.group[open]").map((d) => d.dataset.group));
  wrap.textContent = "";
  const groups = { ...state.meta.label_groups };
  if (state.custom.length) groups["Your conditions"] = state.custom;
  const first = !open.size;
  for (const [name, labels] of Object.entries(groups)) {
    const d = document.createElement("details");
    d.className = "group";
    d.dataset.group = name;
    const on = labels.filter((l) => state.selected.has(l)).length;
    if (open.has(name) || (first && (name === "Your conditions" || on > 0 && name === Object.keys(groups)[0]))) d.open = true;
    const s = document.createElement("summary");
    s.textContent = name;
    const n = document.createElement("span");
    n.className = "n";
    n.textContent = `${on}/${labels.length}`;
    s.append(n);
    const chips = document.createElement("div");
    chips.className = "chips";
    for (const label of labels) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "lchip";
      b.textContent = label;
      b.setAttribute("aria-pressed", state.selected.has(label) ? "true" : "false");
      b.addEventListener("click", () => toggleLabel(label));
      if (name === "Your conditions") {
        const x = document.createElement("span");
        x.className = "x";
        x.textContent = "×";
        x.setAttribute("aria-hidden", "true");
        b.append(x);
        b.title = "Click to turn on or off. Double-click to remove.";
        b.addEventListener("dblclick", () => removeCustom(label));
      }
      chips.append(b);
    }
    d.append(s, chips);
    wrap.append(d);
  }
  const count = state.selected.size;
  $("#label-count").textContent = `${count} selected`;
}

function toggleLabel(label) {
  state.selected.has(label) ? state.selected.delete(label) : state.selected.add(label);
  saveLabels();
  renderLabels();
  scheduleAnalyze();
}

function removeCustom(label) {
  state.custom = state.custom.filter((l) => l !== label);
  state.selected.delete(label);
  saveLabels();
  renderLabels();
  scheduleAnalyze();
}

$("#add-label").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const input = $("#custom-label");
  const label = input.value.trim().replace(/\s+/g, " ").toLowerCase();
  if (!label) return;
  const known = Object.values(state.meta.label_groups).flat();
  if (!known.includes(label) && !state.custom.includes(label)) state.custom.push(label);
  state.selected.add(label);
  input.value = "";
  saveLabels();
  renderLabels();
  scheduleAnalyze();
});
$("#reset-labels").addEventListener("click", () => {
  state.selected = new Set(state.meta.default_selection);
  saveLabels();
  renderLabels();
  scheduleAnalyze();
});
$("#clear-labels").addEventListener("click", () => {
  state.selected.clear();
  saveLabels();
  renderLabels();
  showResult(null);
  status("Choose at least two conditions to compare.");
});

/* ---------------- Settings ---------------- */
function bindSeg(container, attr, onChange) {
  container.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      container.querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", x === b ? "true" : "false"));
      onChange(b.dataset[attr]);
    }),
  );
}
function setMode(mode) {
  state.mode = mode;
  $$(".toolbar .seg button").forEach((b) => b.setAttribute("aria-checked", b.dataset.mode === mode ? "true" : "false"));
}
bindSeg($(".toolbar .seg"), "mode", (m) => (state.mode = m));
bindSeg($("#mask-mode"), "value", (v) => { state.maskMode = v; analyze(); });
$("#crop").addEventListener("change", (e) => { state.crop = e.target.checked; analyze(); });

/* ---------------- Photo intake ---------------- */
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

async function downscale(file) {
  // Resize in the browser so uploads are small and fast. Falls back to the original file.
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    const k = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
    const w = Math.round(bmp.width * k), h = Math.round(bmp.height * k);
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    c.getContext("2d").drawImage(bmp, 0, 0, w, h);
    bmp.close && bmp.close();
    const blob = await new Promise((res) => c.toBlob(res, "image/jpeg", 0.92));
    return blob || file;
  } catch (_) {
    return file;
  }
}

async function takeFile(file) {
  if (!file) return;
  if (!ACCEPTED.includes(file.type) && !file.type.startsWith("image/")) {
    status("That isn't a photo. Use a JPG, PNG or WEBP image.", true);
    return;
  }
  const limit = (state.meta?.limits.max_upload_mb || 15) * 1024 * 1024;
  if (file.size > limit * 3) {
    status(`That photo is too large. Use one under ${state.meta?.limits.max_upload_mb || 15} MB.`, true);
    return;
  }
  await forgetImage();
  state.blob = await downscale(file);
  state.points = [{ x: 0.5, y: 0.5, include: true }];
  state.box = null;
  state.cursor = { x: 0.5, y: 0.5 };
  state.result = null;
  const img = $("#photo");
  if (img.src) URL.revokeObjectURL(img.src);
  img.src = URL.createObjectURL(state.blob);
  await img.decode().catch(() => {});
  state.size = { w: img.naturalWidth, h: img.naturalHeight };
  $("#drop").hidden = true;
  $("#editor").hidden = false;
  $("#ws-sub").textContent = "We started with the center of the photo. Click the spot, or drag a box around it, to outline it more precisely.";
  setMode("select");
  showResult(null);
  drawOverlay();
  $("#stage").focus({ preventScroll: true });
  upload();
}

async function upload() {
  if (!state.meta?.ready) {
    status("Waiting for the models to finish loading…");
    return;
  }
  busy(true);
  status("Preparing the photo…");
  const fd = new FormData();
  fd.append("image", state.blob, "photo.jpg");
  try {
    const d = await api("/api/v1/images", { method: "POST", body: fd });
    state.imageId = d.image_id;
    await analyze();
  } catch (e) {
    busy(false);
    if (e.status === 503) return waitForModels();
    status(e.message, true);
  }
}

// The server is (re)starting: show the loading banner and carry on once it's ready.
function waitForModels() {
  state.imageId = null; // a restarted server has forgotten the photo
  if (state.meta) state.meta.ready = false;
  status("Getting the models ready. Your photo will be analyzed as soon as they are.");
  clearTimeout(waitForModels.timer);
  waitForModels.timer = setTimeout(loadMeta, 1500);
}

async function forgetImage() {
  if (state.imageId) {
    const id = state.imageId;
    state.imageId = null;
    fetch(`/api/v1/images/${encodeURIComponent(id)}`, { method: "DELETE", keepalive: true }).catch(() => {});
  }
}

$("#pick").addEventListener("change", (e) => { takeFile(e.target.files[0]); e.target.value = ""; });
$("#camera").addEventListener("change", (e) => { takeFile(e.target.files[0]); e.target.value = ""; });
$("#sample-btn").addEventListener("click", async () => {
  const r = await fetch("/static/samples/sample.jpg");
  const b = await r.blob();
  takeFile(new File([b], "sample.jpg", { type: "image/jpeg" }));
});

// Drag and drop anywhere on the page
let dragDepth = 0;
window.addEventListener("dragenter", (e) => {
  if (![...(e.dataTransfer?.types || [])].includes("Files")) return;
  dragDepth++;
  document.body.classList.add("dragging");
});
window.addEventListener("dragleave", () => {
  if (--dragDepth <= 0) { dragDepth = 0; document.body.classList.remove("dragging"); }
});
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => {
  e.preventDefault();
  dragDepth = 0;
  document.body.classList.remove("dragging");
  takeFile(e.dataTransfer?.files?.[0]);
});
window.addEventListener("paste", (e) => {
  const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
  if (item) takeFile(item.getAsFile());
});
window.addEventListener("pagehide", forgetImage);

/* ---------------- Points ---------------- */
function addPoint(x, y) {
  x = Math.min(Math.max(x, 0), 1);
  y = Math.min(Math.max(y, 0), 1);
  const max = state.meta?.limits.max_points || 24;
  if (state.mode === "select") { state.points = [{ x, y, include: true }]; state.box = null; }
  else if (state.points.length >= max) {
    status(`You can place up to ${max} points. Undo some, or start over with Select spot.`, true);
    return;
  } else state.points.push({ x, y, include: state.mode === "add" });
  state.cursor = { x, y };
  drawOverlay();
  analyze();
}

// Click places a point; dragging draws a box around the spot.
let drag = null;
function rel(e) {
  const r = $("#photo").getBoundingClientRect();
  return { x: Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1), y: Math.min(Math.max((e.clientY - r.top) / r.height, 0), 1), px: e.clientX, py: e.clientY };
}
const stage = $("#stage");
stage.addEventListener("pointerdown", (e) => {
  // Ignore clicks before the photo has a size on screen (it is still loading).
  if (!state.blob || e.button !== 0 || !$("#photo").getBoundingClientRect().width) return;
  drag = { start: rel(e), moved: false };
  stage.setPointerCapture(e.pointerId);
});
stage.addEventListener("pointermove", (e) => {
  if (!drag) return;
  const p = rel(e);
  if (!drag.moved && Math.hypot(p.px - drag.start.px, p.py - drag.start.py) < 6) return;
  drag.moved = true;
  drag.box = [Math.min(drag.start.x, p.x), Math.min(drag.start.y, p.y), Math.max(drag.start.x, p.x), Math.max(drag.start.y, p.y)];
  drawOverlay(drag.box);
});
stage.addEventListener("pointerup", (e) => {
  if (!drag) return;
  const d = drag;
  drag = null;
  if (!d.moved) return addPoint(d.start.x, d.start.y);
  state.box = d.box;
  if (state.mode === "select") state.points = [];
  state.cursor = { x: (d.box[0] + d.box[2]) / 2, y: (d.box[1] + d.box[3]) / 2 };
  drawOverlay();
  analyze();
});
stage.addEventListener("pointercancel", () => { drag = null; drawOverlay(); });

$("#stage").addEventListener("keydown", (e) => {
  const step = e.shiftKey ? 0.05 : 0.01;
  const c = state.cursor;
  const moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
  if (moves[e.key]) {
    e.preventDefault();
    c.x = Math.min(Math.max(c.x + moves[e.key][0], 0), 1);
    c.y = Math.min(Math.max(c.y + moves[e.key][1], 0), 1);
    drawOverlay();
  } else if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    addPoint(c.x, c.y);
  } else if (e.key === "Backspace" || e.key === "Delete") {
    e.preventDefault();
    undo();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.target.closest?.("input, textarea, dialog") || e.ctrlKey || e.metaKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (k === "s") setMode("select");
  if (k === "a") setMode("add");
  if (k === "r") setMode("remove");
});

function undo() {
  if (state.points.length + (state.box ? 1 : 0) <= 1) return;
  if (state.points.length) state.points.pop();
  else state.box = null;
  drawOverlay();
  analyze();
}
$("#undo-btn").addEventListener("click", undo);
$("#new-btn").addEventListener("click", async () => {
  await forgetImage();
  state.blob = null;
  state.points = [];
  state.box = null;
  state.result = null;
  $("#editor").hidden = true;
  $("#drop").hidden = false;
  $("#ws-sub").textContent = "Add a photo, point at the spot, and see how it compares with the conditions you choose.";
  showResult(null);
  status("");
});

/* ---------------- Analyze ---------------- */
let debounce;
function scheduleAnalyze() {
  clearTimeout(debounce);
  debounce = setTimeout(analyze, 350);
}

async function analyze(retried = false) {
  if (!state.imageId || (!state.points.length && !state.box)) return;
  const labels = [...state.selected];
  if (labels.length < 2) {
    status("Choose at least two conditions to compare.", true);
    return;
  }
  if (state.controller) state.controller.abort();
  const controller = (state.controller = new AbortController());
  const seq = ++state.seq;
  busy(true);
  status("Outlining and comparing…");
  try {
    const d = await api("/api/v1/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        image_id: state.imageId,
        points: state.points,
        box: state.box,
        labels,
        mask_mode: state.maskMode,
        crop: state.crop,
        top_k: 6,
      }),
    });
    if (seq !== state.seq) return;
    await paintHeat(d.outline.heatmap).catch(() => {});
    if (seq !== state.seq) return;
    state.result = d;
    drawOverlay();
    showResult(d);
    status("");
  } catch (e) {
    if (e.name === "AbortError" || seq !== state.seq) return;
    if (e.status === 503) return waitForModels();
    if (e.status === 404 && !retried && state.blob) {
      // The server forgot the photo (it expired or restarted). Send it again.
      state.imageId = null;
      return upload();
    }
    status(e.message, true);
  } finally {
    if (seq === state.seq) busy(false);
  }
}

/* ---------------- Drawing ---------------- */
const SVGNS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}
function pathFrom(polys) {
  return polys.map((p) => "M" + p.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join("L") + "Z").join("");
}

function drawOverlay(draft = null) {
  const svg = $("#overlay");
  const { w, h } = state.size;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.textContent = "";
  const o = state.result?.outline;
  const heatOn = state.view === "heatmap" && !!o?.heatmap;
  $("#heat").hidden = !heatOn;
  $("#heat-legend").hidden = $("#heat-note").hidden = state.view !== "heatmap";
  if (o && o.polygons.length) {
    const d = pathFrom(o.polygons);
    // Outline: lime tint. Spotlight: true colors inside, everything else dimmed.
    // Heatmap: the colored confidence layer (a canvas under this SVG), lines only.
    if (state.view === "spotlight") svg.append(svgEl("path", { d: `M0 0H${w}V${h}H0Z` + d, class: "ol-dim" }));
    else if (!heatOn) svg.append(svgEl("path", { d, class: "ol-fill" }));
    svg.append(svgEl("path", { d, class: "ol-line" }));
    svg.append(svgEl("path", { d, class: "ol-line2" }));
  }
  if (o && o.box) {
    // Corner brackets around the spot, echoing the logo.
    const pad = Math.max(w, h) * 0.015;
    const x0 = o.box[0] * w - pad, y0 = o.box[1] * h - pad, x1 = o.box[2] * w + pad, y1 = o.box[3] * h + pad;
    const L = Math.min(x1 - x0, y1 - y0) * 0.22;
    const c = [
      `M${x0} ${y0 + L}V${y0}H${x0 + L}`, `M${x1 - L} ${y0}H${x1}V${y0 + L}`,
      `M${x1} ${y1 - L}V${y1}H${x1 - L}`, `M${x0 + L} ${y1}H${x0}V${y1 - L}`,
    ].join("");
    svg.append(svgEl("path", { d: c, class: "ol-corner" }));
  }
  const pb = draft || state.box;
  if (pb) {
    svg.append(svgEl("rect", { x: pb[0] * w, y: pb[1] * h, width: (pb[2] - pb[0]) * w, height: (pb[3] - pb[1]) * h, class: "prompt-box" }));
  }
  const r = Math.max(w, h) / 90;
  for (const p of state.points) {
    const cx = p.x * w, cy = p.y * h;
    svg.append(svgEl("circle", { cx, cy, r, class: p.include ? "pt-in" : "pt-out" }));
    const s = r * 0.45;
    let d = `M${cx - s} ${cy}H${cx + s}`;
    if (p.include && state.points.length > 1) d += `M${cx} ${cy - s}V${cy + s}`;
    if (!p.include || state.points.length > 1) svg.append(svgEl("path", { d, class: "pt-sign" }));
  }
  svg.append(svgEl("circle", { cx: state.cursor.x * w, cy: state.cursor.y * h, r: r * 1.8, class: "kb-cursor" }));
  $("#undo-btn").disabled = state.points.length + (state.box ? 1 : 0) <= 1;
}

/* ---------------- Heatmap ---------------- */
// Classic heatmap colors ("Turbo": blue → cyan → green → yellow → red), shown
// only inside the outline. The server's confidence value v maps SAM's mask logit
// from -4..7 onto 0..1, so the outline's edge (logit 0) sits at v = 4/11.
const EDGE = 4 / 11;
function turbo(x) {
  const c = [
    0.13572138 + x * (4.6153926 + x * (-42.66032258 + x * (132.13108234 + x * (-152.94239396 + x * 59.28637943)))),
    0.09140261 + x * (2.19418839 + x * (4.84296658 + x * (-14.18503333 + x * (4.27729857 + x * 2.82956604)))),
    0.1066733 + x * (12.64194608 + x * (-60.58204836 + x * (110.36276771 + x * (-89.90310912 + x * 27.34824973)))),
  ];
  return c.map((v) => Math.round(Math.min(Math.max(v, 0), 1) * 255));
}
const HEAT_LUT = (() => {
  const lut = new Uint8ClampedArray(256 * 4);
  for (let i = 0; i < 256; i++) {
    const v = i / 255;
    const t = Math.min(Math.max((v - EDGE) / (1 - EDGE), 0), 1); // 0 at the outline, 1 at the firmest core
    const [r, g, b] = turbo(0.15 + 0.8 * t); // skip Turbo's near-black ends
    // Fade in over a thin band at the edge; nothing at all outside the outline.
    const alpha = v < EDGE - 0.04 ? 0 : Math.min((v - (EDGE - 0.04)) / 0.06, 1) * 0.5;
    lut.set([r, g, b, Math.round(alpha * 255)], i * 4);
  }
  return lut;
})();

async function paintHeat(dataUrl) {
  const canvas = $("#heat");
  if (!dataUrl) return;
  const img = new Image();
  img.src = dataUrl;
  await img.decode();
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const g = canvas.getContext("2d", { willReadFrequently: true });
  // A light blur hides SAM's internal 64×64 grid, which otherwise shows as a mesh.
  g.filter = `blur(${Math.max(1.5, canvas.width / 160)}px)`;
  g.drawImage(img, 0, 0);
  g.filter = "none";
  const px = g.getImageData(0, 0, canvas.width, canvas.height);
  const a = px.data;
  for (let i = 0; i < a.length; i += 4) {
    const v = a[i] * 4; // grayscale: R = G = B = confidence
    a[i] = HEAT_LUT[v]; a[i + 1] = HEAT_LUT[v + 1]; a[i + 2] = HEAT_LUT[v + 2]; a[i + 3] = HEAT_LUT[v + 3];
  }
  g.putImageData(px, 0, 0);
}

function setView(v) {
  state.view = v;
  store.set("view", v);
  $$("#view-mode button").forEach((b) => b.setAttribute("aria-checked", b.dataset.value === v ? "true" : "false"));
  drawOverlay();
}
bindSeg($("#view-mode"), "value", setView);

/* ---------------- Results ---------------- */
const pct = (v) => (v < 0.001 ? "<0.1" : (v * 100).toFixed(v >= 0.995 || v < 0.1 ? 1 : 0)) + "%";
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const CONF = { high: "High confidence", moderate: "Moderate confidence", low: "Low confidence" };

function showResult(d) {
  $("#result").hidden = !d;
  $("#result-empty").hidden = !!d;
  $("#download-btn").disabled = !d;
  if (!d) return;
  const [top, ...rest] = d.predictions;
  $("#top-name").textContent = cap(top.label);
  $("#top-score").textContent = pct(top.score);
  const chip = $("#confidence");
  chip.className = "chip " + d.confidence;
  chip.textContent = CONF[d.confidence];

  const notes = $("#notes");
  notes.textContent = "";
  d.notes.forEach((n) => {
    const li = document.createElement("li");
    li.textContent = n;
    notes.append(li);
  });

  const ol = $("#others");
  ol.textContent = "";
  rest.forEach((p) => {
    const li = document.createElement("li");
    const top = document.createElement("div");
    top.className = "bar-top";
    const a = document.createElement("span");
    a.textContent = cap(p.label);
    const b = document.createElement("span");
    b.textContent = pct(p.score);
    top.append(a, b);
    const track = document.createElement("div");
    track.className = "track";
    const fill = document.createElement("div");
    fill.className = "fill";
    fill.style.width = Math.max(p.score * 100, 1) + "%";
    track.append(fill);
    li.append(top, track);
    ol.append(li);
  });

  $("#fact-region").textContent = d.classified_region === "outline" ? "Spot only" : "Whole photo";
  const q = d.outline.score;
  $("#fact-outline").textContent = q >= 0.9 ? "Good" : q >= 0.75 ? "Fair" : "Rough";
  $("#fact-area").textContent = d.outline.box ? pct(d.outline.area) + " of photo" : "None";
}

/* ---------------- Download ---------------- */
$("#download-btn").addEventListener("click", async () => {
  const d = state.result;
  if (!d) return;
  const img = $("#photo");
  const { w, h } = state.size;
  const band = Math.round(Math.max(56, w * 0.075));
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h + band;
  const g = c.getContext("2d");
  g.drawImage(img, 0, 0, w, h);
  if (d.outline.polygons.length) {
    const p = new Path2D(pathFrom(d.outline.polygons));
    if (state.view === "spotlight") {
      const dim = new Path2D(`M0 0H${w}V${h}H0Z` + pathFrom(d.outline.polygons));
      g.fillStyle = "rgba(12,31,25,0.62)";
      g.fill(dim, "evenodd");
    } else if (state.view === "heatmap" && d.outline.heatmap) {
      g.drawImage($("#heat"), 0, 0, w, h);
    } else {
      g.fillStyle = "rgba(145,241,136,0.28)";
      g.fill(p, "evenodd");
    }
    g.lineJoin = "round";
    g.strokeStyle = "#0C1F19";
    g.lineWidth = Math.max(4, w / 260);
    g.stroke(p);
    g.strokeStyle = "#91F188";
    g.lineWidth = Math.max(2, w / 500);
    g.stroke(p);
  }
  g.fillStyle = "#fff";
  g.fillRect(0, h, w, band);
  const top = d.predictions[0];
  const fs = Math.round(band * 0.3);
  g.fillStyle = "#0C1F19";
  g.font = `600 ${fs}px Outfit, system-ui, sans-serif`;
  g.textBaseline = "middle";
  g.fillText(`Closest match on my list: ${top.label} (${pct(top.score)})`, band * 0.3, h + band * 0.38);
  g.fillStyle = "#5C6B66";
  g.font = `400 ${Math.round(fs * 0.78)}px Outfit, system-ui, sans-serif`;
  g.fillText("Maculo research preview · not a diagnosis", band * 0.3, h + band * 0.72);
  c.toBlob((b) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b);
    a.download = `maculo-${new Date().toISOString().slice(0, 10)}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }, "image/png");
});

/* ---------------- Dialogs ---------------- */
$("#how-btn").addEventListener("click", () => $("#how").showModal());
$("#intro").addEventListener("close", () => store.set("introSeen", true));
if (!store.get("introSeen", false)) $("#intro").showModal();

/* ---------------- Smooth open and close ---------------- */
// <details> snaps open and shut on its own, so animate its height and fade its
// content. Covers the side cards and the condition groups (which are re-rendered,
// hence one delegated listener).
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function animateDetails(d, open) {
  const startHeight = d.getBoundingClientRect().height;
  if (d._anim) d._anim.cancel();
  d._target = open;
  d.dataset.state = open ? "open" : "closed"; // turns the arrow right away
  let endHeight;
  if (open) {
    d.open = true;
    endHeight = d.getBoundingClientRect().height;
  } else {
    d.open = false; // measure the closed size, then reopen to animate down to it
    endHeight = d.getBoundingClientRect().height;
    d.open = true;
  }
  const timing = { duration: 280, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" };
  d.style.overflow = "hidden";
  const anim = d.animate({ height: [`${startHeight}px`, `${endHeight}px`] }, timing);
  d.querySelectorAll(":scope > :not(summary)").forEach((el) =>
    el.animate({ opacity: open ? [0, 1] : [1, 0] }, { ...timing, fill: "forwards" }).finished
      .then((a) => a.cancel()).catch(() => {}),
  );
  d._anim = anim;
  anim.onfinish = () => {
    d._anim = null;
    d.open = open;
    d.style.overflow = "";
  };
}

document.addEventListener("click", (e) => {
  const summary = e.target.closest("details.fold > summary, details.group > summary");
  if (!summary || reduceMotion.matches) return;
  e.preventDefault();
  const d = summary.parentElement;
  animateDetails(d, !(d._anim ? d._target : d.open));
});

// Restore the saved view and which side cards are open or closed.
$$("#view-mode button").forEach((b) => b.setAttribute("aria-checked", b.dataset.value === state.view ? "true" : "false"));
const folds = store.get("folds", {});
$$("details.fold").forEach((d) => {
  if (d.dataset.fold in folds) d.open = folds[d.dataset.fold];
  d.addEventListener("toggle", () => {
    folds[d.dataset.fold] = d.open;
    store.set("folds", folds);
  });
});

loadMeta();
