const STORE = "aion-binds-v11";
const STORE_LEGACY = ["aion-binds-v10", "aion-binds-v9", "aion-binds-v8"];
const STATE_API = "http://127.0.0.1:46462/api/state";
const USE_STATE_API = location.hostname === "localhost" || location.hostname === "127.0.0.1";

/*
 * Origin 4.6 HUD is a visual arrangement of keyboard binds, not a second bind table.
 * Lives on the «Панели» tab (state.view === "hud"). Each cell stores {layer, key}
 * and live-reads state.binds for the current class. Slot placements are per-class:
 * switching away snapshots this class's HUD; a class without a snapshot gets empty
 * slots (no leftover {layer,key} caption). A cell is empty when it has no ref or
 * that key is unbound on the current class.
 * Bar III / II sit flush above the main 12-slot bar and
 * never rotate. Extra I/II sit above that stack; one rotate button cycles
 * 4 orientations independently (1×12, 12×1, 2×6, 6×2). The index and
 * rotate tab stay on the right (horizontal) or bottom (vertical) and
 * are not rotated with the cells. Side is a static vertical 12-slot
 * rail on the right of the whole center group.
 */
const QB_SLOT_COUNT = 12;
const QB_LAYERS = ["combat", "shift", "ctrl", "alt"];
const QB_BARS = {
  main: { kind: "main", label: "Главная" },
  bar2: { kind: "stack", label: "Панель II", tag: "II" },
  bar3: { kind: "stack", label: "Панель III", tag: "III" },
  extra1: { kind: "extra", label: "Доп. I", mode: "extra1mode", index: 1 },
  extra2: { kind: "extra", label: "Доп. II", mode: "extra2mode", index: 2 },
  side: { kind: "side", label: "Боковая" },
};

const state = {
  view: "binds",
  layer: "combat",
  class: DEFAULT_CLASS,
  race: DEFAULT_RACE,
  multirace: false,
  stigmas: emptyStigmas(),
  binds: emptyBinds(),
  quickbar: defaultQuickbar(),
  byClass: {},
  shareToken: null,
  pickSkill: null,
  pickKey: null,
  pickSlot: null,
  pickBind: null,
};

function emptyBarSlots() {
  return Array(QB_SLOT_COUNT).fill(null);
}

function extraLayout(mode) {
  const n = Number(mode);
  const m = n === 1 || n === 2 || n === 3 ? n : 0;
  return { mode: m, rot: m % 2 ? 90 : 0, rows: m >= 2 ? 2 : 1 };
}

function extraModeFromRotRows(rot, rows) {
  return extraLayout((rows === 1 ? 0 : 2) + (rot === 90 ? 1 : 0)).mode;
}

function readExtraMode(q, prefix) {
  if (q && typeof q === "object") {
    const n = Number(q[prefix + "mode"]);
    if (n === 0 || n === 1 || n === 2 || n === 3) return n;
    return extraModeFromRotRows(q[prefix + "rot"], q[prefix + "rows"]);
  }
  return extraLayout(0).mode;
}

function setExtraMode(qb, modeKey, mode) {
  if (!qb || !modeKey) return extraLayout(mode);
  const layout = extraLayout(mode);
  qb[modeKey] = layout.mode;
  const prefix = modeKey.endsWith("mode") ? modeKey.slice(0, -4) : modeKey;
  qb[prefix + "rot"] = layout.rot;
  qb[prefix + "rows"] = layout.rows;
  return layout;
}

function defaultQuickbar() {
  const next = {
    extra1mode: 0,
    extra2mode: 0,
    extra1rot: 0,
    extra2rot: 0,
    extra1rows: 1,
    extra2rows: 1,
    siderot: 90,
    siderows: 1,
    bars: {
      main: emptyBarSlots(),
      bar2: emptyBarSlots(),
      bar3: emptyBarSlots(),
      extra1: emptyBarSlots(),
      extra2: emptyBarSlots(),
      side: emptyBarSlots(),
    },
  };
  setExtraMode(next, "extra1mode", 0);
  setExtraMode(next, "extra2mode", 0);
  return next;
}

function unpackPackedRef(item) {
  if (typeof item !== "string") return null;
  const i = item.indexOf(":");
  if (i < 1) return null;
  const layerOf = { c: "combat", s: "shift", t: "ctrl", a: "alt" };
  const layer = layerOf[item[0]] || null;
  const key = item.slice(i + 1);
  if (!QB_LAYERS.includes(layer) || !key || isMove(key)) return null;
  return { layer, key };
}

function bindPlaceForSkill(skillId, binds) {
  if (!skillId || !binds) return null;
  for (const layer of QB_LAYERS) {
    const map = binds[layer] || {};
    for (const [key, sid] of Object.entries(map)) {
      if (sid === skillId && key && !isMove(key)) return { layer, key };
    }
  }
  return null;
}

function liveQbRef(ref, binds) {
  if (!ref || !QB_LAYERS.includes(ref.layer) || typeof ref.key !== "string" || !ref.key || isMove(ref.key)) {
    return null;
  }
  const sid = binds && binds[ref.layer] && binds[ref.layer][ref.key];
  return sid ? { layer: ref.layer, key: ref.key } : null;
}

function cleanQbRef(ref, binds) {
  if (ref == null || ref === "") return null;
  const table = binds || state.binds;
  if (typeof ref === "string") return liveQbRef(unpackPackedRef(ref), table) || bindPlaceForSkill(ref, table);
  if (typeof ref !== "object") return null;
  return liveQbRef(ref, table) || bindPlaceForSkill(ref.skillId || ref.id || ref.skill, table);
}

function padBarSlots(arr, binds) {
  const out = [];
  for (let i = 0; i < QB_SLOT_COUNT; i += 1) out.push(cleanQbRef(arr && arr[i], binds));
  return out;
}

function padQuickbar(q, binds) {
  const next = defaultQuickbar();
  if (!q || typeof q !== "object") return next;
  setExtraMode(next, "extra1mode", readExtraMode(q, "extra1"));
  setExtraMode(next, "extra2mode", readExtraMode(q, "extra2"));
  next.siderot = 90;
  next.siderows = 1;
  const src = q.bars && typeof q.bars === "object" ? q.bars : q;
  for (const id of Object.keys(next.bars)) {
    next.bars[id] = padBarSlots(src[id], binds);
  }
  return next;
}

function normalizeQuickbar(binds) {
  if (!state.quickbar || !state.quickbar.bars) return;
  const table = binds || state.binds;
  for (const id of Object.keys(state.quickbar.bars)) {
    state.quickbar.bars[id] = padBarSlots(state.quickbar.bars[id], table);
  }
}

function qbRef(bar, index) {
  const slots = state.quickbar && state.quickbar.bars && state.quickbar.bars[bar];
  return (slots && slots[index]) || null;
}

function setQbRef(bar, index, ref) {
  if (!QB_BARS[bar] || index < 0 || index >= QB_SLOT_COUNT) return;
  state.quickbar.bars[bar][index] = cleanQbRef(ref);
}

function qbSkill(bar, index) {
  const ref = qbRef(bar, index);
  return ref ? bindAtLayer(ref.layer, ref.key) : null;
}

function formatHudKey(layer, key) {
  const label = prettyKey(key);
  if (key === "Wheel") {
    if (layer === "shift") return "⇧MW";
    if (layer === "ctrl") return "Ctrl+MW";
    if (layer === "alt") return "Alt+MW";
    return "MW";
  }
  if (layer === "shift") return `⇧${label}`;
  if (layer === "ctrl") return `Ctrl+${label}`;
  if (layer === "alt") return `Alt+${label}`;
  return label;
}

function packQbSlots(slots) {
  const codeOf = { combat: "c", shift: "s", ctrl: "t", alt: "a" };
  return (slots || []).map((ref) => (ref && codeOf[ref.layer] ? `${codeOf[ref.layer]}:${ref.key}` : ""));
}

function unpackQbSlots(arr) {
  if (!Array.isArray(arr)) return emptyBarSlots();
  return padBarSlots(arr);
}

function applyQuickbarShare(q) {
  const next = defaultQuickbar();
  if (Array.isArray(q)) {
    setExtraMode(next, "extra1mode", extraModeFromRotRows(q[0] ? 90 : 0, 2));
    setExtraMode(next, "extra2mode", extraModeFromRotRows(q[1] ? 90 : 0, 2));
    return next;
  }
  if (!q || typeof q !== "object") return next;
  const em = Array.isArray(q.em) ? q.em : [];
  const e = Array.isArray(q.e) ? q.e : [];
  if (em.length >= 2) {
    setExtraMode(next, "extra1mode", em[0]);
    setExtraMode(next, "extra2mode", em[1]);
  } else {
    setExtraMode(next, "extra1mode", extraModeFromRotRows(e[0] ? 90 : 0, e[2] === 0 ? 1 : 2));
    setExtraMode(next, "extra2mode", extraModeFromRotRows(e[1] ? 90 : 0, e[3] === 0 ? 1 : 2));
  }
  next.siderot = 90;
  next.siderows = 1;
  next.bars.main = unpackQbSlots(q.m);
  next.bars.bar2 = unpackQbSlots(q.a);
  next.bars.bar3 = unpackQbSlots(q.b);
  next.bars.extra1 = unpackQbSlots(q.x);
  next.bars.extra2 = unpackQbSlots(q.y);
  next.bars.side = unpackQbSlots(q.z);
  return next;
}

function defaultState() {
  return {
    class: DEFAULT_CLASS,
    race: DEFAULT_RACE,
    multirace: false,
    stigmas: emptyStigmas(),
    binds: emptyBinds(),
    quickbar: defaultQuickbar(),
    byClass: {},
  };
}

function cleanClass(id) {
  if (id && typeof CLASSES !== "undefined" && CLASSES.some((c) => c.id === id)) return id;
  return DEFAULT_CLASS;
}

function layoutWeight(binds, stigmas) {
  let n = 0;
  if (binds) {
    for (const layer of ["combat", "shift", "ctrl", "alt"]) n += Object.keys(binds[layer] || {}).length;
  }
  if (stigmas) {
    for (const tier of ["normal", "greater"]) n += (stigmas[tier] || []).filter(Boolean).length;
  }
  return n;
}

function restoreClassSnapshot(cls, snap) {
  if (!snap || !snap.binds) return false;
  state.class = cleanClass(cls);
  state.stigmas = padStigmas(snap.stigmas);
  state.binds = {
    combat: { ...(snap.binds.combat || {}) },
    shift: { ...(snap.binds.shift || {}) },
    ctrl: { ...(snap.binds.ctrl || {}) },
    alt: { ...(snap.binds.alt || {}) },
  };
  applyHudBars(snap.quickbar && snap.quickbar.bars, state.binds);
  pruneStigmas();
  pruneBinds();
  return true;
}

function hydrateFromSnapshots() {
  const live = layoutWeight(state.binds, state.stigmas);
  const here = state.byClass && state.byClass[state.class];
  if (here && layoutWeight(here.binds, here.stigmas) > live) {
    restoreClassSnapshot(state.class, here);
    return;
  }
  if (live > 0) return;
  let bestCls = null;
  let bestSnap = null;
  let bestW = 0;
  for (const [cls, snap] of Object.entries(state.byClass || {})) {
    const w = layoutWeight(snap && snap.binds, snap && snap.stigmas);
    if (w > bestW) {
      bestW = w;
      bestCls = cls;
      bestSnap = snap;
    }
  }
  if (bestSnap && bestW > 0) restoreClassSnapshot(bestCls, bestSnap);
}

function loadState() {
  const fallback = defaultState();
  try {
    const raw = localStorage.getItem(STORE) || STORE_LEGACY.map((k) => localStorage.getItem(k)).find(Boolean);
    if (!raw) {
      applyCore(fallback);
      return;
    }
    const parsed = JSON.parse(raw);
    state.class = cleanClass(parsed.class);
    state.race = parsed.race === "elyos" ? "elyos" : "asmo";
    state.multirace = Boolean(parsed.multirace);
    state.byClass = parsed.byClass && typeof parsed.byClass === "object" ? parsed.byClass : {};
    state.shareToken = typeof parsed.shareToken === "string" ? parsed.shareToken : null;
    state.stigmas = padStigmas(parsed.stigmas);
    pruneStigmas();
    const incoming = parsed.binds || {};
    state.binds = {
      combat: { ...(incoming.combat || {}) },
      shift: { ...(incoming.shift || {}) },
      ctrl: { ...(incoming.ctrl || {}) },
      alt: { ...(incoming.alt || {}) },
    };
    state.quickbar = padQuickbar(parsed.quickbar, state.binds);
    pruneBinds();
    lastRemoteAt = Number(parsed.updatedAt) || 0;
    hydrateFromSnapshots();
  } catch {
    applyCore(fallback);
  }
}

function applyCore(next) {
  state.class = next.class || DEFAULT_CLASS;
  state.race = next.race;
  state.multirace = Boolean(next.multirace);
  state.stigmas = next.stigmas;
  state.binds = next.binds;
  state.quickbar = padQuickbar(next.quickbar, next.binds);
  state.byClass = next.byClass || {};
}

function cloneQbBars(bars) {
  const out = {};
  for (const id of Object.keys(QB_BARS)) {
    const src = bars && bars[id];
    out[id] = [];
    for (let i = 0; i < QB_SLOT_COUNT; i += 1) {
      const ref = src && src[i];
      out[id].push(ref && ref.layer && ref.key ? { layer: ref.layer, key: ref.key } : null);
    }
  }
  return out;
}

function applyHudBars(bars, binds) {
  if (!state.quickbar || !state.quickbar.bars) state.quickbar = defaultQuickbar();
  const table = binds || state.binds;
  if (!bars) {
    for (const id of Object.keys(state.quickbar.bars)) {
      state.quickbar.bars[id] = emptyBarSlots();
    }
    return;
  }
  for (const id of Object.keys(state.quickbar.bars)) {
    state.quickbar.bars[id] = padBarSlots(bars[id], table);
  }
}

function persistClassSnapshot(cls) {
  if (!cls || !state.binds || !state.stigmas) return;
  state.byClass = state.byClass || {};
  state.byClass[cls] = {
    stigmas: {
      normal: state.stigmas.normal.slice(),
      greater: state.stigmas.greater.slice(),
    },
    binds: {
      combat: { ...state.binds.combat },
      shift: { ...state.binds.shift },
      ctrl: { ...state.binds.ctrl },
      alt: { ...state.binds.alt },
    },
    quickbar: { bars: cloneQbBars(state.quickbar && state.quickbar.bars) },
  };
}

function skillName(id) {
  return id && SKILLS[id] ? SKILLS[id].name : null;
}

let lastRemoteAt = 0;
let classPickSync = false;

function snapshot(source) {
  normalizeQuickbar(state.binds);
  persistClassSnapshot(state.class);
  return {
    class: state.class,
    race: state.race,
    multirace: state.multirace,
    stigmas: state.stigmas,
    stigmaNames: {
      normal: state.stigmas.normal.map(skillName),
      greater: state.stigmas.greater.map(skillName),
    },
    binds: state.binds,
    quickbar: state.quickbar,
    byClass: state.byClass,
    shareToken: state.shareToken || null,
    updatedAt: Date.now(),
    source: source || "ui",
  };
}

function applyRemote(data) {
  if (!data || !data.stigmas) return;
  lastRemoteAt = Number(data.updatedAt) || Date.now();
  state.class = cleanClass(data.class);
  state.race = data.race === "elyos" ? "elyos" : "asmo";
  state.multirace = Boolean(data.multirace);
  if (data.byClass && typeof data.byClass === "object") state.byClass = data.byClass;
  state.stigmas = padStigmas(data.stigmas);
  pruneStigmas();
  const incoming = data.binds || {};
  state.binds = {
    combat: { ...(incoming.combat || {}) },
    shift: { ...(incoming.shift || {}) },
    ctrl: { ...(incoming.ctrl || {}) },
    alt: { ...(incoming.alt || {}) },
  };
  if (data.quickbar) {
    const next = padQuickbar(data.quickbar, state.binds);
    const incomingHasSlots = data.quickbar.bars && typeof data.quickbar.bars === "object";
    if (!incomingHasSlots && state.quickbar && state.quickbar.bars) next.bars = state.quickbar.bars;
    state.quickbar = next;
  }
  pruneBinds();
  localStorage.setItem(
    STORE,
    JSON.stringify({ ...snapshot("api"), updatedAt: lastRemoteAt, source: data.source || "api" })
  );
  renderCombos();
  render();
}

function save() {
  const payload = snapshot("ui");
  lastRemoteAt = payload.updatedAt;
  try {
    localStorage.setItem(STORE, JSON.stringify(payload));
  } catch {
    return false;
  }
  if (USE_STATE_API) {
    fetch(STATE_API, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => {});
  }
  return true;
}

function toast(msg, ms) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    t.style.display = "none";
  }, ms || 1600);
}

const SHARE_KEY_SHORT = {
  Digit0: "0",
  Digit1: "1",
  Digit2: "2",
  Digit3: "3",
  Digit4: "4",
  Digit5: "5",
  Digit6: "6",
  Digit7: "7",
  Digit8: "8",
  Digit9: "9",
  KeyA: "A",
  KeyB: "B",
  KeyC: "C",
  KeyD: "D",
  KeyE: "E",
  KeyF: "F",
  KeyG: "G",
  KeyH: "H",
  KeyI: "I",
  KeyJ: "J",
  KeyK: "K",
  KeyL: "L",
  KeyM: "M",
  KeyN: "N",
  KeyO: "O",
  KeyP: "P",
  KeyQ: "Q",
  KeyR: "R",
  KeyS: "S",
  KeyT: "T",
  KeyU: "U",
  KeyV: "V",
  KeyW: "W",
  KeyX: "X",
  KeyY: "Y",
  KeyZ: "Z",
  Mouse4: "m4",
  Mouse5: "m5",
  Wheel: "mw",
  CapsLock: "cl",
  Backquote: "`",
  Minus: "-",
  Equal: "=",
  BracketLeft: "[",
  BracketRight: "]",
  Semicolon: ";",
  Quote: "'",
  Comma: ",",
  Period: ".",
  Slash: "/",
  Escape: "esc",
  Tab: "tab",
  Backspace: "bs",
  Enter: "ent",
  Space: "sp",
  ShiftLeft: "sl",
  ShiftRight: "sr",
  ControlLeft: "ctl",
  ControlRight: "ctr",
  AltLeft: "al",
  AltRight: "ar",
  MetaLeft: "win",
};
const SHARE_KEY_LONG = Object.fromEntries(
  Object.entries(SHARE_KEY_SHORT).map(([long, short]) => [short, long])
);
const SHARE_LAYER_CODE = { combat: "c", shift: "s", ctrl: "t", alt: "a" };
const SHARE_LAYER_NAME = { c: "combat", s: "shift", t: "ctrl", a: "alt" };
const SHARE_QB_BARS = [
  ["m", "main"],
  ["a", "bar2"],
  ["b", "bar3"],
  ["x", "extra1"],
  ["y", "extra2"],
  ["z", "side"],
];

function shortShareKey(key) {
  return SHARE_KEY_SHORT[key] || key;
}

function expandShareKey(short) {
  if (!short) return "";
  if (SHARE_KEY_LONG[short]) return SHARE_KEY_LONG[short];
  if (/^Key[A-Z]$/.test(short) || /^Digit[0-9]$/.test(short)) return short;
  if (/^[A-Z]$/.test(short)) return `Key${short}`;
  if (/^[0-9]$/.test(short)) return `Digit${short}`;
  return short;
}

function packShareNameSlots(list) {
  const out = (list || []).map((id) => id || "");
  while (out.length && !out[out.length - 1]) out.pop();
  return out.length ? out : undefined;
}

function packShareBinds(map) {
  const out = {};
  if (!map) return undefined;
  for (const [key, sid] of Object.entries(map)) {
    if (!sid) continue;
    out[shortShareKey(key)] = sid;
  }
  return Object.keys(out).length ? out : undefined;
}

function packShareHud(slots) {
  const parts = [];
  (slots || []).forEach((ref, i) => {
    const layer = ref && SHARE_LAYER_CODE[ref.layer];
    if (!layer || !ref.key) return;
    parts.push(`${i}${layer}${shortShareKey(ref.key)}`);
  });
  return parts.length ? parts.join(",") : undefined;
}

function sharePayload() {
  const extra1 = extraLayout(state.quickbar.extra1mode);
  const extra2 = extraLayout(state.quickbar.extra2mode);
  const q = {};
  if (extra1.mode || extra2.mode) q.em = [extra1.mode, extra2.mode];
  for (const [code, bar] of SHARE_QB_BARS) {
    const packed = packShareHud(state.quickbar.bars[bar]);
    if (packed) q[code] = packed;
  }
  const payload = {
    k: state.class,
    n: packShareNameSlots(state.stigmas.normal),
    g: packShareNameSlots(state.stigmas.greater),
    c: packShareBinds(state.binds.combat),
    s: packShareBinds(state.binds.shift),
    t: packShareBinds(state.binds.ctrl),
    a: packShareBinds(state.binds.alt),
  };
  if (state.race === "elyos") payload.r = 1;
  if (state.multirace) payload.m = 1;
  if (Object.keys(q).length) payload.q = q;
  return payload;
}

function expandShareSlots(arr, ids) {
  if (!Array.isArray(arr)) return [];
  return arr.map((item) => {
    if (item == null || item === "" || item === -1) return "";
    if (typeof item === "number") return ids[item] || "";
    return item;
  });
}

function expandShareBinds(map, ids) {
  const out = {};
  if (!map || typeof map !== "object") return out;
  for (const [k, v] of Object.entries(map)) {
    const key = expandShareKey(k);
    const sid = typeof v === "number" ? ids[v] : v;
    if (key && sid) out[key] = sid;
  }
  return out;
}

function expandShareHudBar(packed) {
  if (Array.isArray(packed)) {
    return packed.map((item) => {
      if (!item) return "";
      if (typeof item !== "string") return "";
      const colon = item.indexOf(":");
      if (colon < 1) return item;
      const layer = item[0];
      const key = expandShareKey(item.slice(colon + 1));
      return SHARE_LAYER_NAME[layer] ? `${layer}:${key}` : item;
    });
  }
  const slots = Array(QB_SLOT_COUNT).fill("");
  if (typeof packed !== "string" || !packed) return slots;
  for (const part of packed.split(",")) {
    const m = part.match(/^(\d{1,2})([csta])(.+)$/);
    if (!m) continue;
    const i = Number(m[1]);
    if (i < 0 || i >= QB_SLOT_COUNT) continue;
    const key = expandShareKey(m[3]);
    if (key) slots[i] = `${m[2]}:${key}`;
  }
  return slots;
}

function expandShareHud(q) {
  if (!q || typeof q !== "object") return q;
  const next = { ...q };
  for (const [code] of SHARE_QB_BARS) {
    if (q[code] != null) next[code] = expandShareHudBar(q[code]);
  }
  return next;
}

function normalizeShare(data) {
  if (!data || typeof data !== "object") throw new Error("payload");
  const ids = Array.isArray(data.i) ? data.i : [];
  return {
    k: data.k,
    r: data.r,
    m: data.m,
    n: expandShareSlots(data.n, ids),
    g: expandShareSlots(data.g, ids),
    c: expandShareBinds(data.c, ids),
    s: expandShareBinds(data.s, ids),
    t: expandShareBinds(data.t, ids),
    a: expandShareBinds(data.a, ids),
    q: expandShareHud(data.q),
  };
}

const SHARE_KEYS = [
  "Escape",
  "F1",
  "F2",
  "F3",
  "F4",
  "F5",
  "F6",
  "F7",
  "F8",
  "F9",
  "F10",
  "F11",
  "F12",
  "Backquote",
  "Digit1",
  "Digit2",
  "Digit3",
  "Digit4",
  "Digit5",
  "Digit6",
  "Digit7",
  "Digit8",
  "Digit9",
  "Digit0",
  "Minus",
  "Equal",
  "Backspace",
  "Tab",
  "KeyQ",
  "KeyW",
  "KeyE",
  "KeyR",
  "KeyT",
  "KeyY",
  "KeyU",
  "KeyI",
  "KeyO",
  "KeyP",
  "BracketLeft",
  "BracketRight",
  "CapsLock",
  "KeyA",
  "KeyS",
  "KeyD",
  "KeyF",
  "KeyG",
  "KeyH",
  "KeyJ",
  "KeyK",
  "KeyL",
  "Semicolon",
  "Quote",
  "Enter",
  "ShiftLeft",
  "KeyZ",
  "KeyX",
  "KeyC",
  "KeyV",
  "KeyB",
  "KeyN",
  "KeyM",
  "Comma",
  "Period",
  "Slash",
  "ShiftRight",
  "ControlLeft",
  "MetaLeft",
  "AltLeft",
  "Space",
  "AltRight",
  "ControlRight",
  "Mouse4",
  "Mouse5",
  "Wheel",
];
const SHARE_KEY_INDEX = Object.fromEntries(SHARE_KEYS.map((key, i) => [key, i]));
const SHARE_BIN_LAYERS = ["combat", "shift", "ctrl", "alt"];
const SHARE_BIN_BARS = ["main", "bar2", "bar3", "extra1", "extra2", "side"];

function shareClassIndex(id) {
  if (typeof CLASSES === "undefined") return 2;
  const i = CLASSES.findIndex((c) => c.id === id);
  return i >= 0 ? i : 2;
}

function encodeShareBinary() {
  const ids = [];
  const idx = new Map();
  const add = (id) => {
    if (!id) return 255;
    if (idx.has(id)) return idx.get(id);
    const next = ids.length;
    if (next >= 255) throw new Error("skills");
    ids.push(id);
    idx.set(id, next);
    return next;
  };
  const keyId = (key) => {
    const i = SHARE_KEY_INDEX[key];
    if (i == null) throw new Error("key");
    return i;
  };
  for (const id of state.stigmas.normal) add(id);
  for (const id of state.stigmas.greater) add(id);
  for (const layer of SHARE_BIN_LAYERS) {
    for (const sid of Object.values(state.binds[layer] || {})) add(sid);
  }
  const out = [];
  const push = (n) => out.push(n & 255);
  push(1);
  push((state.race === "elyos" ? 1 : 0) | (state.multirace ? 2 : 0) | (shareClassIndex(state.class) << 2));
  const extra1 = extraLayout(state.quickbar.extra1mode).mode;
  const extra2 = extraLayout(state.quickbar.extra2mode).mode;
  push((extra1 & 15) | ((extra2 & 15) << 4));
  push(ids.length);
  const enc = new TextEncoder();
  for (const id of ids) {
    const bytes = enc.encode(id);
    if (bytes.length > 255) throw new Error("id");
    push(bytes.length);
    for (let i = 0; i < bytes.length; i += 1) out.push(bytes[i]);
  }
  for (const tier of ["normal", "greater"]) {
    for (let i = 0; i < 6; i += 1) push(add(state.stigmas[tier][i]));
  }
  for (const layer of SHARE_BIN_LAYERS) {
    const entries = Object.entries(state.binds[layer] || {}).filter(([, sid]) => sid);
    push(entries.length);
    for (const [key, sid] of entries) {
      push(keyId(key));
      push(idx.get(sid));
    }
  }
  for (const bar of SHARE_BIN_BARS) {
    const slots = (state.quickbar.bars && state.quickbar.bars[bar]) || [];
    const filled = [];
    slots.forEach((ref, i) => {
      if (!ref || !ref.layer || !ref.key) return;
      const layer = SHARE_BIN_LAYERS.indexOf(ref.layer);
      if (layer < 0) return;
      filled.push([i, layer, keyId(ref.key)]);
    });
    push(filled.length);
    for (const [slot, layer, key] of filled) {
      push((slot & 15) | ((layer & 3) << 4));
      push(key);
    }
  }
  return new Uint8Array(out);
}

function decodeShareBinary(bytes) {
  let p = 0;
  const need = (n) => {
    if (p + n > bytes.length) throw new Error("truncated");
  };
  const u8 = () => {
    need(1);
    const v = bytes[p];
    p += 1;
    return v;
  };
  if (u8() !== 1) throw new Error("binver");
  const flags = u8();
  const extra = u8();
  const nSkills = u8();
  const ids = [];
  const dec = new TextDecoder();
  for (let i = 0; i < nSkills; i += 1) {
    const n = u8();
    need(n);
    ids.push(dec.decode(bytes.subarray(p, p + n)));
    p += n;
  }
  const slotIds = () => {
    const out = [];
    for (let i = 0; i < 6; i += 1) {
      const ix = u8();
      out.push(ix === 255 ? "" : ids[ix] || "");
    }
    return out;
  };
  const n = slotIds();
  const g = slotIds();
  const binds = {};
  for (const layer of SHARE_BIN_LAYERS) {
    const count = u8();
    const map = {};
    for (let i = 0; i < count; i += 1) {
      const key = SHARE_KEYS[u8()] || "";
      const sid = ids[u8()] || "";
      if (key && sid) map[key] = sid;
    }
    binds[layer] = map;
  }
  const q = { em: [extra & 15, extra >> 4] };
  const codes = ["m", "a", "b", "x", "y", "z"];
  for (let b = 0; b < SHARE_BIN_BARS.length; b += 1) {
    const count = u8();
    const slots = Array(QB_SLOT_COUNT).fill("");
    for (let i = 0; i < count; i += 1) {
      const packed = u8();
      const key = SHARE_KEYS[u8()] || "";
      const slot = packed & 15;
      const layer = SHARE_BIN_LAYERS[(packed >> 4) & 3];
      const code = SHARE_LAYER_CODE[layer];
      if (slot < QB_SLOT_COUNT && code && key) slots[slot] = `${code}:${key}`;
    }
    q[codes[b]] = slots;
  }
  const cls = typeof CLASSES !== "undefined" ? (CLASSES[flags >> 2] || {}).id : "";
  return {
    k: cls || "assassin",
    r: flags & 1 ? 1 : 0,
    m: flags & 2 ? 1 : 0,
    n,
    g,
    c: binds.combat,
    s: binds.shift,
    t: binds.ctrl,
    a: binds.alt,
    q,
  };
}

function parseShareBytes(bytes) {
  if (!bytes || !bytes.length) throw new Error("empty");
  if (bytes[0] === 1) return decodeShareBinary(bytes);
  const data = JSON.parse(new TextDecoder().decode(bytes));
  return normalizeShare(data);
}

function bytesToB64url(bytes) {
  let bin = "";
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  for (let i = 0; i < arr.length; i += 1) bin += String.fromCharCode(arr[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlToBytes(token) {
  const pad = token.length % 4 === 0 ? "" : "=".repeat(4 - (token.length % 4));
  const bin = atob(token.replace(/-/g, "+").replace(/_/g, "/") + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

async function transformBytes(bytes, stream) {
  const writer = stream.writable.getWriter();
  writer.write(bytes);
  writer.close();
  return new Uint8Array(await new Response(stream.readable).arrayBuffer());
}

async function encodeShare(data) {
  const candidates = [];
  const jsonRaw = new TextEncoder().encode(JSON.stringify(data || sharePayload()));
  candidates.push({ prefix: "j", packed: jsonRaw });
  try {
    const binRaw = encodeShareBinary();
    candidates.push({ prefix: "b", packed: binRaw });
  } catch {
    /* fall back to json */
  }
  if (typeof CompressionStream === "function") {
    const sources = candidates.slice();
    for (const src of sources) {
      for (const [name, prefix] of [
        ["deflate-raw", "d"],
        ["gzip", "z"],
      ]) {
        try {
          const packed = await transformBytes(src.packed, new CompressionStream(name));
          if (packed.length < src.packed.length) candidates.push({ prefix, packed });
        } catch {
          /* codec missing */
        }
      }
    }
  }
  candidates.sort((a, b) => a.packed.length - b.packed.length);
  const best = candidates[0];
  return best.prefix + bytesToB64url(best.packed);
}

async function decodeShare(token) {
  if (!token || token.length < 2) throw new Error("empty");
  const kind = token[0];
  const bytes = b64urlToBytes(token.slice(1));
  let raw = bytes;
  if (kind === "d" || kind === "z") {
    const codec = kind === "d" ? "deflate-raw" : "gzip";
    if (typeof DecompressionStream !== "function") throw new Error(codec);
    raw = await transformBytes(bytes, new DecompressionStream(codec));
  } else if (kind !== "j" && kind !== "b") {
    throw new Error("format");
  }
  return parseShareBytes(raw);
}

function cleanSkillId(id) {
  return id && SKILLS[id] ? id : null;
}

function cleanBindMap(map) {
  const out = {};
  if (!map || typeof map !== "object") return out;
  for (const [key, sid] of Object.entries(map)) {
    if (typeof key === "string" && cleanSkillId(sid)) out[key] = sid;
  }
  return out;
}

function applyShare(data) {
  state.class = cleanClass(data.k);
  state.race = data.r === 1 ? "elyos" : "asmo";
  state.multirace = Boolean(data.m);
  state.stigmas = padStigmas({
    normal: (data.n || []).map(cleanSkillId),
    greater: (data.g || []).map(cleanSkillId),
  });
  pruneStigmas();
  state.binds = {
    combat: cleanBindMap(data.c),
    shift: cleanBindMap(data.s),
    ctrl: cleanBindMap(data.t),
    alt: cleanBindMap(data.a),
  };
  state.quickbar = applyQuickbarShare(data.q);
  pruneBinds();
  persistClassSnapshot(state.class);
  state.pickSkill = null;
  state.pickKey = null;
  state.pickSlot = null;
  lastRemoteAt = Date.now();
}

function shareTokenFromLocation() {
  const hash = (location.hash || "").replace(/^#/, "");
  if (hash) {
    const fromHash = new URLSearchParams(hash).get("s");
    if (fromHash) return fromHash;
  }
  return new URLSearchParams(location.search).get("s");
}

function shareUrl(token) {
  return `${location.href.replace(/#.*$/, "")}#s=${token}`;
}

function clearShareFromLocation() {
  try {
    const next = new URL(location.href);
    next.searchParams.delete("s");
    next.hash = "";
    history.replaceState(null, "", next.pathname + next.search);
  } catch {
    /* ignore */
  }
}

async function copyShareLink() {
  const url = shareUrl(await encodeShare(sharePayload()));
  try {
    if (navigator.share && navigator.canShare && navigator.canShare({ url })) {
      await navigator.share({ title: `Раскладка ${classNameOf(state.class)} Aion 4.6`, url });
      return;
    }
  } catch (err) {
    if (err && err.name === "AbortError") return;
  }
  try {
    await navigator.clipboard.writeText(url);
    toast("Ссылка скопирована");
  } catch {
    window.prompt("Скопируйте ссылку:", url);
  }
}

async function openShareFromUrl() {
  const token = shareTokenFromLocation();
  if (!token) return;
  try {
    const data = await decodeShare(token);
    const already = state.shareToken === token;
    if (!already && !window.confirm("Открыть раскладку из ссылки? Текущие бинды и стигмы будут заменены.")) {
      clearShareFromLocation();
      return;
    }
    applyShare(data);
    state.shareToken = token;
    const ok = save();
    if (ok) clearShareFromLocation();
    if (!already) toast("Открыта раскладка по ссылке");
  } catch {
    toast("Ссылка обрезана. Скопируйте её целиком из чата, не из адресной строки.", 4200);
    clearShareFromLocation();
  }
}

async function pullState() {
  if (!USE_STATE_API) return;
  try {
    const res = await fetch(STATE_API, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    const at = Number(data.updatedAt) || 0;
    if (at <= lastRemoteAt) return;
    applyRemote(data);
  } catch {
    /* server down */
  }
}

function stigmaTier(id) {
  return STIGMA_TIER[id] || null;
}

const POTIONS = new Set(["curePotion", "recoverySerum", "manaSerum", "lifeSerum"]);

function isPotion(id) {
  return POTIONS.has(id);
}

function isBasicSkill(id) {
  return typeof BASIC_SKILLS !== "undefined" && BASIC_SKILLS.has(id);
}

function skillRace(id) {
  if (SKILL_RACE[id]) return SKILL_RACE[id];
  if (/Elyos$/i.test(id)) return "elyos";
  if (/Asmo$/i.test(id)) return "asmo";
  return null;
}

function isInstalledStigma(id) {
  return installedStigmaSet(state.stigmas).has(id);
}

function belongsToClass(id) {
  if (isBasicSkill(id) || isPotion(id)) return true;
  if (typeof SKILL_CLASS === "undefined" || !SKILL_CLASS[id]) return true;
  return SKILL_CLASS[id].includes(state.class);
}

function isVisibleSkill(id) {
  if (!SKILLS[id]) return false;
  if (!belongsToClass(id)) return false;
  const race = skillRace(id);
  const tier = stigmaTier(id);
  if (race) {
    if (tier) {
      if (race !== state.race) return false;
    } else if (!state.multirace && race !== state.race) return false;
  }
  if (tier) return isInstalledStigma(id);
  return true;
}

function bindIsStale(sid) {
  if (!SKILLS[sid]) return true;
  if (!belongsToClass(sid)) return true;
  const tier = stigmaTier(sid);
  if (tier) {
    if (!isInstalledStigma(sid)) return true;
    const race = skillRace(sid);
    if (race && race !== state.race) return true;
  }
  return false;
}

function pruneBinds() {
  for (const layer of Object.keys(state.binds)) {
    for (const [key, sid] of Object.entries(state.binds[layer])) {
      if (bindIsStale(sid)) delete state.binds[layer][key];
    }
  }
}

function prettyKey(id) {
  const map = {
    Backquote: "Ё",
    CapsLock: "Caps",
    Digit1: "1",
    Digit2: "2",
    Digit3: "3",
    Digit4: "4",
    Digit5: "5",
    Digit6: "6",
    Digit7: "7",
    Digit8: "8",
    Digit9: "9",
    KeyQ: "Q",
    KeyW: "W",
    KeyE: "E",
    KeyR: "R",
    KeyT: "T",
    KeyY: "Y",
    KeyU: "U",
    KeyI: "I",
    KeyO: "O",
    KeyP: "P",
    KeyA: "A",
    KeyS: "S",
    KeyD: "D",
    KeyF: "F",
    KeyG: "G",
    KeyH: "H",
    KeyJ: "J",
    KeyK: "K",
    KeyL: "L",
    KeyZ: "Z",
    KeyX: "X",
    KeyC: "C",
    KeyV: "V",
    KeyB: "B",
    KeyN: "N",
    KeyM: "M",
    Mouse4: "M4",
    Mouse5: "M5",
    Wheel: "Колесо",
    Minus: "−",
    Equal: "=",
    F1: "F1",
    F2: "F2",
    F3: "F3",
    F4: "F4",
    F5: "F5",
    F6: "F6",
    F7: "F7",
    F8: "F8",
    F9: "F9",
    F10: "F10",
    F11: "F11",
    F12: "F12",
  };
  return map[id] || id.replace(/^Key|^Digit/, "");
}

function isLocked(key) {
  return LOCKED.has(`${state.layer}:${prettyKey(key)}`);
}

function isMove(key) {
  return MOVE.has(key);
}

function bindAt(key) {
  return bindAtLayer(state.layer, key);
}

function bindAtLayer(layer, key) {
  const sid = (state.binds[layer] || {})[key] || null;
  return sid && isVisibleSkill(sid) ? sid : null;
}

function skillIcon(id) {
  return `img/skills/${id}.png?v=43`;
}

function iconTag(id, cls) {
  if (!id || !SKILLS[id]) return "";
  return `<img class="${cls}" src="${skillIcon(id)}" alt="" draggable="false" onerror="this.remove()">`;
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const CLIENT_PARAM_NAMES = new Set(["КД", "Стоимость", "Время каста"]);

function statsTable(caption, rows) {
  if (!rows || !rows.length) return "";
  const body = rows
    .map((r) => `<tr><th scope="row">${esc(r.name)}</th><td>${esc(r.value)}</td></tr>`)
    .join("");
  return `<table class="hidden-stats"><caption>${caption}</caption><tbody>${body}</tbody></table>`;
}

function clientParamRows(s) {
  if (s && Array.isArray(s.params)) return s.params;
  return (s && s.hidden ? s.hidden : []).filter((r) => CLIENT_PARAM_NAMES.has(r.name));
}

function hiddenStatRows(s) {
  const rows = (s && s.hidden) || [];
  if (s && Array.isArray(s.params)) return rows;
  return rows.filter((r) => !CLIENT_PARAM_NAMES.has(r.name));
}

function skillStatTables(s) {
  return (
    statsTable("Параметры", clientParamRows(s)) +
    statsTable("Скрытые статы", hiddenStatRows(s)) +
    statsTable("Ловушка", s && s.trap)
  );
}

function usedMap() {
  const map = {};
  for (const [key, sid] of Object.entries(state.binds[state.layer] || {})) {
    if (isVisibleSkill(sid)) map[sid] = key;
  }
  return map;
}

function bindsBySkill() {
  const map = {};
  for (const layer of QB_LAYERS) {
    for (const [key, sid] of Object.entries(state.binds[layer] || {})) {
      if (!isVisibleSkill(sid)) continue;
      if (!map[sid]) map[sid] = [];
      map[sid].push({ layer, key });
    }
  }
  return map;
}

function formatLayerKey(layer, key) {
  const label = prettyKey(key);
  if (layer === state.layer) return label;
  if (layer === "combat") return `Бой ${label}`;
  if (layer === "shift") return `⇧${label}`;
  if (layer === "ctrl") return `Ctrl+${label}`;
  if (layer === "alt") return `Alt+${label}`;
  return label;
}

function assign(key, skillId) {
  assignOnLayer(state.layer, key, skillId);
}

function assignOnLayer(layer, key, skillId) {
  if (isMove(key)) return;
  if (skillId && !isVisibleSkill(skillId)) return;
  const map = state.binds[layer];
  if (!map) return;
  for (const [k, sid] of Object.entries(map)) {
    if (sid === skillId) delete map[k];
  }
  if (skillId) map[key] = skillId;
  else delete map[key];
  save();
}

function swapOnLayers(fromLayer, fromKey, toLayer, toKey) {
  if (!fromKey || !toKey || isMove(fromKey) || isMove(toKey)) return false;
  if (fromLayer === toLayer && fromKey === toKey) return false;
  const a = state.binds[fromLayer];
  const b = state.binds[toLayer];
  if (!a || !b) return false;
  const fromSkill = a[fromKey];
  if (!fromSkill) return false;
  const toSkill = b[toKey] || null;
  if (toSkill) a[fromKey] = toSkill;
  else delete a[fromKey];
  b[toKey] = fromSkill;
  save();
  return true;
}

function swapOrMove(fromKey, toKey) {
  return swapOnLayers(state.layer, fromKey, state.layer, toKey);
}

function placeSkillOnKey(toKey, skillId) {
  if (!toKey || isMove(toKey) || !skillId || !isVisibleSkill(skillId)) return false;
  const fromKey = Object.keys(state.binds[state.layer]).find((k) => state.binds[state.layer][k] === skillId);
  if (fromKey === toKey) return true;
  if (fromKey) return swapOrMove(fromKey, toKey);
  assign(toKey, skillId);
  return true;
}

function clearBtn(key) {
  if (isMove(key) || !bindAt(key)) return "";
  const onKey = state.pickKey === key;
  const onSkill = Boolean(state.pickSkill && usedMap()[state.pickSkill] === key);
  if (!onKey && !onSkill) return "";
  return `<span class="key-clear" data-clear-key="${key}" title="Снять" role="button" aria-label="Снять умение">×</span>`;
}

function qbCaption(bar, index) {
  const ref = qbRef(bar, index);
  if (!ref || !bindAtLayer(ref.layer, ref.key)) return "";
  return formatHudKey(ref.layer, ref.key);
}

function qbSlotSelected(bar, index) {
  const ref = qbRef(bar, index);
  if (state.pickSlot && state.pickSlot.bar === bar && state.pickSlot.index === index) return true;
  return Boolean(ref && state.pickKey === ref.key && state.layer === ref.layer);
}

function clearBtnSlot(bar, index) {
  const ref = qbRef(bar, index);
  if (!ref) return "";
  const sid = qbSkill(bar, index);
  const onSlot = qbSlotSelected(bar, index);
  const onSkill = Boolean(state.pickSkill && sid === state.pickSkill);
  if (!onSlot && !onSkill) return "";
  return `<span class="key-clear" data-clear-slot="${bar}:${index}" title="Убрать с панели" role="button" aria-label="Убрать с панели">×</span>`;
}

function refForSkill(skillId) {
  if (!skillId) return null;
  const places = bindsBySkill()[skillId];
  if (!places || !places.length) return null;
  return places.find((p) => p.layer === state.layer) || places[0];
}

function placeBindOnSlot(bar, index, layer, key) {
  if (!QB_BARS[bar] || isMove(key) || !bindAtLayer(layer, key)) return false;
  setQbRef(bar, index, { layer, key });
  save();
  return true;
}

function clearHudSlot(bar, index) {
  setQbRef(bar, index, null);
  state.pickSlot = { bar, index };
  state.pickKey = null;
  state.pickSkill = null;
  state.pickBind = null;
  showInspect(null);
  save();
  render();
}

function clearAllBinds() {
  state.binds = emptyBinds();
  state.pickSkill = null;
  state.pickKey = null;
  state.pickBind = null;
  save();
  render();
}

function openResetBindsModal() {
  const modal = document.getElementById("reset-binds-modal");
  modal.hidden = false;
  document.getElementById("reset-binds-cancel").focus();
}

function closeResetBindsModal() {
  document.getElementById("reset-binds-modal").hidden = true;
}

function confirmResetBinds() {
  closeResetBindsModal();
  clearAllBinds();
}

function clearAllStigmas() {
  for (const id of installedStigmaSet(state.stigmas)) removeSkillBinds(id);
  state.stigmas = emptyStigmas();
  pruneBinds();
  save();
  render();
}

function removeSkillBinds(id) {
  if (!state.binds) return;
  for (const layer of Object.keys(state.binds)) {
    for (const [key, sid] of Object.entries(state.binds[layer])) {
      if (sid === id) delete state.binds[layer][key];
    }
  }
}

function setRace(race) {
  if (race !== "elyos" && race !== "asmo") return;
  if (state.race === race) return;
  state.race = race;
  pruneStigmas();
  pruneBinds();
  save();
  render();
}

function setMultirace(on) {
  const next = Boolean(on);
  if (state.multirace === next) return;
  state.multirace = next;
  save();
  render();
}

function setClass(cls) {
  cls = cleanClass(cls);
  if (state.class === cls) return;
  normalizeQuickbar(state.binds);
  persistClassSnapshot(state.class);
  state.class = cls;
  const snap = state.byClass[cls];
  if (snap && snap.binds) {
    state.stigmas = padStigmas(snap.stigmas);
    state.binds = {
      combat: { ...(snap.binds.combat || {}) },
      shift: { ...(snap.binds.shift || {}) },
      ctrl: { ...(snap.binds.ctrl || {}) },
      alt: { ...(snap.binds.alt || {}) },
    };
  } else {
    state.stigmas = emptyStigmas();
    state.binds = emptyBinds();
  }
  applyHudBars(snap && snap.quickbar && snap.quickbar.bars, state.binds);
  pruneStigmas();
  pruneBinds();
  normalizeQuickbar(state.binds);
  state.pickSkill = null;
  state.pickKey = null;
  state.pickSlot = null;
  renderCombos();
  save();
  render();
}

function canPutStigmaInSlot(id, slotTier) {
  const need = stigmaTier(id);
  if (!need) return false;
  const race = skillRace(id);
  if (race && race !== state.race) return false;
  if (need === "greater") return slotTier === "greater";
  return true;
}

function findStigmaSlot(id) {
  for (const slot of STIGMA_BOARD) {
    if (state.stigmas[slot.tier][slot.index] === id) return slot;
  }
  return null;
}

function firstEmptyCompatible(id, board) {
  const src = board || state.stigmas;
  const order = stigmaTier(id) === "greater" ? ["greater"] : ["normal", "greater"];
  for (const tier of order) {
    for (const slot of STIGMA_BOARD) {
      if (slot.tier !== tier) continue;
      if (!canPutStigmaInSlot(id, slot.tier)) continue;
      if (!src[slot.tier][slot.index]) return slot;
    }
  }
  return null;
}

function pruneStigmas() {
  for (const tier of ["normal", "greater"]) {
    state.stigmas[tier] = state.stigmas[tier].map((id) => {
      if (!id || !SKILLS[id] || !stigmaTier(id)) return null;
      const race = skillRace(id);
      if (race && race !== state.race) {
        removeSkillBinds(id);
        return null;
      }
      return id;
    });
  }
}

function putStigma(tier, index, id) {
  if (id) {
    if (!canPutStigmaInSlot(id, tier)) return false;
    for (const t of ["normal", "greater"]) {
      const i = state.stigmas[t].indexOf(id);
      if (i >= 0) state.stigmas[t][i] = null;
    }
  }
  const prev = state.stigmas[tier][index];
  if (prev && prev !== id) removeSkillBinds(prev);
  state.stigmas[tier][index] = id || null;
  return true;
}

function installStigma(tier, index, id) {
  putStigma(tier, index, id);
  pruneBinds();
  state.pickSlot = null;
  save();
}

function prereqIds(id) {
  const en = STIGMA_ID_TO_EN[id];
  if (!en) return [];
  return (STIGMA_REQS[en] || []).map(stigmaIdFromEn).filter(Boolean);
}

function installChain(id) {
  const have = installedStigmaSet(state.stigmas);
  const order = [];
  const walk = (sid, seen = new Set()) => {
    if (!sid || seen.has(sid)) return;
    seen.add(sid);
    for (const p of prereqIds(sid)) walk(p, seen);
    order.push(sid);
  };
  walk(id);
  const pending = order.filter((sid) => !have.has(sid));
  const board = {
    normal: state.stigmas.normal.slice(),
    greater: state.stigmas.greater.slice(),
  };
  const placements = [];
  for (const sid of pending) {
    const slot = firstEmptyCompatible(sid, board);
    if (!slot) return false;
    board[slot.tier][slot.index] = sid;
    placements.push([slot, sid]);
  }
  for (const [slot, sid] of placements) putStigma(slot.tier, slot.index, sid);
  pruneBinds();
  save();
  return true;
}

function removeCascade(id) {
  const have = [...installedStigmaSet(state.stigmas)];
  const drop = new Set([id]);
  let again = true;
  while (again) {
    again = false;
    for (const sid of have) {
      if (drop.has(sid)) continue;
      if (prereqIds(sid).some((p) => drop.has(p))) {
        drop.add(sid);
        again = true;
      }
    }
  }
  for (const sid of drop) {
    const slot = findStigmaSlot(sid);
    if (slot) {
      const prev = state.stigmas[slot.tier][slot.index];
      if (prev) removeSkillBinds(prev);
      state.stigmas[slot.tier][slot.index] = null;
    }
  }
  pruneBinds();
  save();
}

function skillHoverCard(id, meta, extra) {
  if (!id || !SKILLS[id]) return "";
  const s = SKILLS[id];
  return `<span class="skill-hover-card">
    <span class="hover-title">${s.name}</span>
    <span class="hover-meta">${meta}</span>
    <span class="hover-description">${s.desc}</span>
    ${skillStatTables(s)}
    ${extra || ""}
  </span>`;
}

function skillListHover(id) {
  const s = SKILLS[id];
  return skillHoverCard(id, s ? `КД ${s.cd}` : "");
}

function stigmaHover(id, missing) {
  if (!id || !SKILLS[id]) return "";
  const en = STIGMA_ID_TO_EN[id] || "";
  const tier = stigmaTier(id) === "greater" ? "Greater Stigma" : "Normal Stigma";
  const reqs =
    missing && missing.length
      ? `<span class="hover-requirements">Нужно: ${missing.join(", ")}</span>`
      : "";
  return skillHoverCard(id, `${en ? en + " · " : ""}${tier} · КД ${SKILLS[id].cd}`, reqs);
}

function stigmaFrame(id, greater) {
  const g = greater || (id && stigmaTier(id) === "greater");
  const frame = g ? "stigma-icon-greater" : "stigma-icon-normal";
  return `<span class="stigma-icon-frame ${frame}">${id ? iconTag(id, "icon") : ""}</span>`;
}

const CC_TAGS = new Set([
  "Стан",
  "Опрокидывание",
  "Воздушные оковы",
  "Отталкивание",
  "Оковы",
  "Немота",
  "Вращение",
]);

function skillTags(id) {
  return SKILLS[id]?.tags || [];
}

function tagClass(t) {
  if (t === "Маг. статус") return "tag tag-mag";
  if (CC_TAGS.has(t)) return "tag tag-cc";
  return "tag";
}

function showInspect(skillId, key, layer) {
  const el = document.getElementById("inspect");
  if (!skillId) {
    el.innerHTML = `<p>${isMove(key) ? "W и S — вперёд/назад. A и D под скиллы, камера мышью." : "Пустой слот. Перетащите умение с другой клавиши или из списка справа. Клик по скиллу — крестик, чтобы снять."}</p>`;
    return;
  }
  const s = SKILLS[skillId];
  const tagList = skillTags(skillId);
  const tags = tagList
    .map((t) => `<span class="${tagClass(t)}">${t}</span>`)
    .join("");
  const lay = layer || state.layer;
  const unbind =
    key && !isMove(key)
      ? `<button type="button" class="unbind" data-unbind="${key}" data-unbind-layer="${lay}">Снять с ${formatLayerKey(lay, key)}</button>`
      : "";
  el.innerHTML = `
    <div class="inspect-head">
      ${iconTag(skillId, "icon-lg")}
      <h3>${s.name}</h3>
    </div>
    ${tags ? `<div class="tags">${tags}</div>` : ""}
    <p>${s.desc}</p>
    ${skillStatTables(s)}
    ${unbind}
  `;
}

function renderCombos() {
  const list = classCombos(state.class);
  const root = document.getElementById("combos");
  if (!list.length) {
    root.innerHTML = "";
    root.hidden = true;
    return;
  }
  root.hidden = false;
  root.innerHTML = list.map(
    (c) => `
    <article class="combo card">
      <h2>${c.title}</h2>
      <div class="keys">${c.keys}</div>
      <p>${c.text}</p>
    </article>`
  ).join("");
}

function renderKeyboard() {
  const root = document.getElementById("keyboard");
  root.innerHTML = KEYBOARD.map((row) => {
    const keys = row
      .map((k) => {
        const sid = bindAt(k.id);
        const skill = sid ? SKILLS[sid] : null;
        const cls = [
          "key",
          skill ? skill.kind : "empty",
          isMove(k.id) ? "move" : "",
          state.pickKey === k.id ? "selected" : "",
        ]
          .filter(Boolean)
          .join(" ");
        const skillText = isMove(k.id) ? "ход" : skill ? skill.name : "";
        const ico = skill && !isMove(k.id) ? iconTag(sid, "icon") : "";
        const canDrag = Boolean(skill && !isMove(k.id));
        return `<button type="button" class="${cls}" data-key="${k.id}" style="--w:${k.w || 1}" draggable="${canDrag ? "true" : "false"}">
          <span class="cap">${k.label}</span>
          <span class="skill">${ico}<span class="skill-name">${skillText}</span></span>
          ${clearBtn(k.id)}
        </button>`;
      })
      .join("");
    return `<div class="row">${keys}</div>`;
  }).join("");
}

function renderQbSlot(bar, index) {
  const ref = qbRef(bar, index);
  const sid = qbSkill(bar, index);
  const skill = sid ? SKILLS[sid] : null;
  const cap = qbCaption(bar, index);
  const cls = ["qb-slot", skill ? skill.kind : "empty", qbSlotSelected(bar, index) ? "selected" : ""]
    .filter(Boolean)
    .join(" ");
  const title = skill ? `${skill.name} · ${cap}` : cap || "Перетащите клавишу с биндом";
  return `<button type="button" class="${cls}" data-qb-bar="${bar}" data-qb-index="${index}" draggable="${ref ? "true" : "false"}" title="${title}">
    ${cap ? `<span class="cap">${cap}</span>` : ""}
    ${sid ? iconTag(sid, "icon") : ""}
    ${clearBtnSlot(bar, index)}
  </button>`;
}

function renderQbBar(bar) {
  const spec = QB_BARS[bar];
  const slots = Array.from({ length: QB_SLOT_COUNT }, (_, i) => renderQbSlot(bar, i)).join("");
  if (spec.kind === "main") {
    return `<div class="qb-bar main" aria-label="${spec.label}">
      <div class="qb-slots">${slots}</div>
    </div>`;
  }
  if (spec.kind === "stack") {
    return `<div class="qb-bar stack ${bar}" aria-label="${spec.label}">
      <span class="qb-stack-tag">${spec.tag}</span>
      <div class="qb-slots">${slots}</div>
    </div>`;
  }
  if (spec.kind === "side") {
    return `<div class="qb-bar qb-side" aria-label="${spec.label}">
      <div class="qb-slots">${slots}</div>
    </div>`;
  }
  const layout = extraLayout(state.quickbar[spec.mode]);
  const badge = `<img class="qb-index" src="img/ui/${spec.index === 2 ? "bar-index-2.png" : "bar-index-1.png"}" alt="${spec.label}" />`;
  return `<div class="qb-bar extra ${bar} rot${layout.rot} rows${layout.rows}" aria-label="${spec.label}">
    <div class="qb-slots">${slots}</div>
    <div class="qb-grip">
      ${badge}
      <button type="button" class="qb-rotate" data-qb-rotate="${bar}" title="Повернуть панель" aria-label="Повернуть ${spec.label}"></button>
    </div>
  </div>`;
}

function renderQuickbar() {
  const root = document.getElementById("quickbar-hud");
  if (!root) return;
  root.innerHTML = `
    <p class="qb-legend">Доп. I и II — над стопкой III / II / главная (кнопка поворота — четыре ориентации). Боковая — справа от всей группы. Перетащите умение с клавиши на ячейку. Крестик убирает ячейку, бинд на клавиатуре остаётся.</p>
    <div class="qb-stage">
      <div class="qb-center">
        <div class="qb-extras">
          ${renderQbBar("extra1")}
          ${renderQbBar("extra2")}
        </div>
        <div class="qb-stack">
          ${renderQbBar("bar3")}
          ${renderQbBar("bar2")}
          ${renderQbBar("main")}
        </div>
      </div>
      <div class="qb-dock">${renderQbBar("side")}</div>
    </div>`;
}

function paintMouse() {
  for (const id of ["Mouse4", "Mouse5", "Wheel"]) {
    const btn = document.querySelector(`[data-key="${id}"]`);
    if (!btn) continue;
    const sid = bindAt(id);
    btn.classList.toggle("selected", state.pickKey === id);
    btn.draggable = Boolean(sid);
    btn.title = sid ? SKILLS[sid].name : id;
    const clear = clearBtn(id);
    if (id === "Wheel") {
      btn.innerHTML = (sid ? iconTag(sid, "icon-mouse") : "") + clear;
    } else if (sid) {
      btn.innerHTML = iconTag(sid, "icon-mouse") + clear;
    } else {
      btn.textContent = prettyKey(id);
    }
  }
}

function visibleSkillIds() {
  const q = (document.getElementById("filter")?.value || "").trim().toLowerCase();
  return Object.keys(SKILLS).filter((id) => {
    if (!isVisibleSkill(id)) return false;
    if (!q) return true;
    const s = SKILLS[id];
    const extra = [...(s.params || []), ...(s.hidden || []), ...(s.trap || [])].flatMap((h) => [h.name, h.value]);
    return [s.name, s.desc, ...(s.tags || []), ...extra].join(" ").toLowerCase().includes(q);
  });
}

function skillButton(id, used, allBinds) {
  const s = SKILLS[id];
  const hits = allBinds[id] || [];
  const here = Boolean(used[id]);
  const elsewhere = hits.some((h) => h.layer !== state.layer);
  const cls = [
    "skill-item",
    s.kind,
    stigmaTier(id) ? "stigma" : "",
    here ? "used" : "",
    elsewhere ? "used-other" : "",
    state.pickSkill === id ? "picked" : "",
  ]
    .filter(Boolean)
    .join(" ");
  const labels = hits.map((h) => formatLayerKey(h.layer, h.key));
  const where = labels.length
    ? labels.join(" · ")
    : stigmaTier(id)
      ? "стигма, без клавиши"
      : "не назначен";
  return `<button type="button" class="${cls}" data-skill="${id}" draggable="true">
    ${iconTag(id, "icon")}
    <span class="meta">
      <span class="n">${s.name}</span>
      <span class="m">${where}</span>
    </span>
    ${skillListHover(id)}
  </button>`;
}

function boundHudBinds() {
  const q = (document.getElementById("filter")?.value || "").trim().toLowerCase();
  const out = [];
  for (const layer of QB_LAYERS) {
    for (const [key, sid] of Object.entries(state.binds[layer] || {})) {
      if (isMove(key) || !isVisibleSkill(sid) || !SKILLS[sid]) continue;
      const s = SKILLS[sid];
      const cap = formatHudKey(layer, key);
      if (q) {
        const extra = [...(s.params || []), ...(s.hidden || []), ...(s.trap || [])].flatMap((h) => [h.name, h.value]);
        const hay = [s.name, s.desc, ...(s.tags || []), ...extra, cap, prettyKey(key)].join(" ").toLowerCase();
        if (!hay.includes(q)) continue;
      }
      out.push({ layer, key, skill: sid, cap });
    }
  }
  out.sort((a, b) => {
    const li = QB_LAYERS.indexOf(a.layer) - QB_LAYERS.indexOf(b.layer);
    if (li) return li;
    return a.cap.localeCompare(b.cap, "ru");
  });
  return out;
}

function hudPlacedBindKeys() {
  const out = new Set();
  const bars = state.quickbar && state.quickbar.bars;
  if (!bars) return out;
  for (const bar of Object.keys(QB_BARS)) {
    const slots = bars[bar];
    if (!slots) continue;
    for (let i = 0; i < QB_SLOT_COUNT; i += 1) {
      const ref = slots[i];
      if (ref && ref.layer && ref.key) out.add(`${ref.layer}:${ref.key}`);
    }
  }
  return out;
}

function renderHudPalette() {
  const root = document.getElementById("skills");
  root.classList.add("hud-palette");
  const items = boundHudBinds();
  const placed = hudPlacedBindKeys();
  root.innerHTML = items.length
    ? items
        .map((b) => {
          const picked = Boolean(
            state.pickBind && state.pickBind.layer === b.layer && state.pickBind.key === b.key
          );
          const onBar = placed.has(`${b.layer}:${b.key}`);
          const name = SKILLS[b.skill].name;
          const cls = ["hud-bind", onBar ? "placed" : "unplaced", picked ? "picked" : ""]
            .filter(Boolean)
            .join(" ");
          const hint = onBar ? "на панели" : "не на панели";
          return `<button type="button" class="${cls}" data-skill="${b.skill}" data-layer="${b.layer}" data-key="${b.key}" draggable="true" title="${name} · ${b.cap} · ${hint}">
            ${iconTag(b.skill, "icon")}
            <span class="hud-bind-cap">${b.cap}</span>
          </button>`;
        })
        .join("")
    : `<p class="empty-list">Нет умений на клавишах. Назначьте их на «Раскладке».</p>`;
}

function renderSkills() {
  const root = document.getElementById("skills");
  if (state.view === "hud") {
    renderHudPalette();
    return;
  }
  root.classList.remove("hud-palette");
  const used = usedMap();
  const allBinds = bindsBySkill();
  const ids = visibleSkillIds();
  const basic = ids.filter((id) => isBasicSkill(id));
  const learned = ids.filter((id) => !stigmaTier(id) && !isPotion(id) && !isBasicSkill(id));
  const potions = ids.filter((id) => isPotion(id));
  const stones = ids.filter((id) => stigmaTier(id));
  const block = (title, list) =>
    list.length
      ? `<h3 class="list-h">${title}</h3>${list.map((id) => skillButton(id, used, allBinds)).join("")}`
      : "";
  root.innerHTML =
    block("Базовые", basic) +
      block("Умения", learned) +
      block("Банки", potions) +
      block("Установленные стигмы", stones) ||
    `<p class="empty-list">Ничего не найдено.</p>`;
}

function renderStigmaBoard() {
  const root = document.getElementById("stigma-board");
  root.innerHTML = STIGMA_BOARD.map((slot) => {
    const id = state.stigmas[slot.tier][slot.index];
    const greater = slot.tier === "greater";
    const label = id ? SKILLS[id].name : greater ? "Greater Stigma" : "Normal Stigma";
    return `<button type="button" class="slot ${slot.tier}${id ? " filled" : " empty"}" data-stigma-tier="${slot.tier}" data-stigma-index="${slot.index}" aria-label="${label}">
      ${stigmaFrame(id, greater)}
      ${id ? stigmaHover(id) : ""}
    </button>`;
  }).join("");
}

function renderStigmaPool() {
  const used = installedStigmaSet(state.stigmas);
  const ids = Object.keys(SKILLS).filter((id) => {
    if (!stigmaTier(id)) return false;
    if (!belongsToClass(id)) return false;
    const race = skillRace(id);
    if (race && race !== state.race) return false;
    return true;
  });
  const root = document.getElementById("stigma-list");
  root.innerHTML = ids
    .map((id) => {
      const on = used.has(id);
      const can = on || Boolean(firstEmptyCompatible(id));
      const cls = ["stigma-row", on ? "used selected" : "", !can ? "disabled" : ""].filter(Boolean).join(" ");
      return `<button type="button" class="${cls}" data-skill="${id}" data-stigma-src="list" ${can && !on ? "" : ""}>
        ${iconTag(id, "skill-icon")}
        ${stigmaHover(id)}
      </button>`;
    })
    .join("");
}

function renderStigmaTrees() {
  const used = installedStigmaSet(state.stigmas);
  const usedEn = new Set([...used].map((id) => STIGMA_ID_TO_EN[id]).filter(Boolean));
  const root = document.getElementById("stigma-trees");
  const trees =
    (typeof STIGMA_TREES_BY_CLASS !== "undefined" && STIGMA_TREES_BY_CLASS[state.class]) || [];
  if (!trees.length) {
    root.innerHTML = "";
    return;
  }
  root.innerHTML = `<div class="tree-grid">${trees.map((tree) => {
    const layout = layoutStigmaTree(tree);
    const selected = (name) => usedEn.has(name);
    const edges = layout.connectors
      .flatMap((c) =>
        c.sources.map((s) => {
          const t = c.target;
          const x1 = s.x + 80;
          const y1 = s.y + 40;
          const x2 = t.x;
          const y2 = t.y + 40;
          const mx = (x1 + x2) / 2;
          const on = selected(s.name) && selected(t.name);
          const d = `M${x1} ${y1} C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`;
          const act = on ? " tree-flow-edge-active" : "";
          return `<path class="tree-flow-edge-shadow${act}" d="${d}" /><path class="tree-flow-edge-rail${act}" d="${d}" /><path class="tree-flow-edge-core${act}" d="${d}" />`;
        })
      )
      .join("");
    const nodes = layout.nodes
      .map((n) => {
        const id = stigmaIdFromEn(n.name);
        const on = id && used.has(id);
        const missing = (STIGMA_REQS[n.name] || []).filter((req) => !usedEn.has(req));
        const locked = !on && missing.length > 0;
        const cls = [
          "tree-flow-node",
          on ? "tree-node-selected" : "",
          locked ? "tree-node-locked" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return `<button type="button" class="${cls}" data-skill="${id || ""}" data-stigma-src="tree" style="left:${n.x}px;top:${n.y}px" ${id ? "" : "disabled"}>
          ${stigmaFrame(id, id ? stigmaTier(id) === "greater" : false)}
          ${id ? stigmaHover(id, missing) : ""}
        </button>`;
      })
      .join("");
    return `<section class="stigma-tree" aria-label="${tree.name}">
      <div class="tree-canvas">
        <svg class="tree-edges" viewBox="0 0 540 470">${edges}</svg>
        ${nodes}
      </div>
    </section>`;
  }).join("")}</div>`;
}

function renderChrome() {
  document.querySelectorAll("[data-view]").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === state.view);
  });
  document.querySelectorAll("[data-race]").forEach((b) => {
    b.classList.toggle("active", b.dataset.race === state.race);
  });
  const multi = document.getElementById("multirace");
  if (multi) {
    multi.classList.toggle("active", state.multirace);
    multi.setAttribute("aria-pressed", state.multirace ? "true" : "false");
  }
  const pick = document.getElementById("class-pick");
  if (pick && pick.value !== state.class) {
    classPickSync = true;
    pick.value = state.class;
    classPickSync = false;
  }
  document.querySelectorAll("[data-layer]").forEach((b) => {
    b.classList.toggle("active", b.dataset.layer === state.layer);
  });
  document.getElementById("binds-view").hidden = state.view !== "binds";
  document.getElementById("hud-view").hidden = state.view !== "hud";
  document.getElementById("stigma-view").hidden = state.view !== "stigmas";
  document.getElementById("reset-binds").hidden = state.view !== "binds";
  document.getElementById("reset-stigmas").hidden = state.view !== "stigmas";
  document.querySelector(".app").classList.toggle("is-stigmas", state.view === "stigmas");
  document.querySelector(".app").classList.toggle("is-hud", state.view === "hud");
  document.getElementById("combos").hidden = state.view === "binds" ? !classCombos(state.class).length : true;
  const sideTitle = document.getElementById("side-title");
  const filter = document.getElementById("filter");
  if (state.view === "stigmas") {
    sideTitle.textContent = "Стигмы";
    filter.placeholder = "Поиск стигмы…";
  } else if (state.view === "hud") {
    sideTitle.textContent = "На клавишах";
    filter.placeholder = "Поиск по умениям и клавишам…";
    document.getElementById("skills").classList.remove("is-stigma-pool");
  } else {
    sideTitle.textContent = "Умения и стигмы";
    filter.placeholder = "Поиск умения…";
    document.getElementById("skills").classList.remove("is-stigma-pool");
  }
  const mouseHint = document.getElementById("mouse-hint");
  const boardHint = document.getElementById("board-hint");
  if (mouseHint) mouseHint.textContent = "Мышь — в движении. W/S ход, A и D можно назначить умения. Перетащите умение на клавишу.";
  if (boardHint) {
    boardHint.textContent =
      "Перетащите умение на клавишу. Клик по скиллу — крестик справа сверху, чтобы снять. ПКМ тоже снимает.";
  }
}

function render() {
  renderChrome();
  if (state.view === "stigmas") {
    renderStigmaBoard();
    renderStigmaPool();
    renderStigmaTrees();
    return;
  }
  renderSkills();
  if (state.view === "hud") {
    renderQuickbar();
    return;
  }
  renderKeyboard();
  paintMouse();
}

function onKey(key) {
  if (isMove(key)) {
    state.pickKey = key;
    state.pickSlot = null;
    showInspect(null, key);
    render();
    return;
  }
  if (state.pickSlot) {
    if (state.pickSkill) assign(key, state.pickSkill);
    placeBindOnSlot(state.pickSlot.bar, state.pickSlot.index, state.layer, key);
    state.pickKey = key;
    showInspect(bindAt(key) || state.pickSkill, key);
    state.pickSkill = null;
    render();
    return;
  }
  if (state.pickSkill) {
    assign(key, state.pickSkill);
    state.pickKey = key;
    state.pickSlot = null;
    showInspect(state.pickSkill, key);
    state.pickSkill = null;
    render();
    return;
  }
  state.pickKey = key;
  state.pickSlot = null;
  showInspect(bindAt(key), key);
  render();
}

function tryPlaceSkillOnSlot(bar, index, skillId) {
  let ref = refForSkill(skillId);
  if (!ref && state.pickKey && !isMove(state.pickKey)) {
    assign(state.pickKey, skillId);
    ref = { layer: state.layer, key: state.pickKey };
  }
  if (!ref) {
    toast("Сначала повесьте умение на клавишу, затем перетащите клавишу на панель.");
    return false;
  }
  placeBindOnSlot(bar, index, ref.layer, ref.key);
  return true;
}

function placePickedBindOnSlot(bar, index) {
  const bind = state.pickBind;
  if (!bind) return false;
  placeBindOnSlot(bar, index, bind.layer, bind.key);
  state.pickSlot = { bar, index };
  state.pickKey = null;
  state.pickSkill = null;
  state.pickBind = null;
  const ref = qbRef(bar, index);
  showInspect(qbSkill(bar, index), ref && ref.key, ref && ref.layer);
  render();
  return true;
}

function onHudBindPick(skillId, layer, key) {
  if (!skillId || !layer || !key || isMove(key)) return;
  if (state.pickSlot) {
    placeBindOnSlot(state.pickSlot.bar, state.pickSlot.index, layer, key);
    const slot = state.pickSlot;
    state.pickSkill = null;
    state.pickBind = null;
    state.pickKey = null;
    const ref = qbRef(slot.bar, slot.index);
    showInspect(qbSkill(slot.bar, slot.index), ref && ref.key, ref && ref.layer);
    render();
    return;
  }
  const same =
    state.pickBind && state.pickBind.layer === layer && state.pickBind.key === key;
  state.pickBind = same ? null : { layer, key };
  state.pickSkill = state.pickBind ? skillId : null;
  state.pickKey = null;
  showInspect(skillId, key, layer);
  render();
}

function onSlot(bar, index) {
  if (!QB_BARS[bar]) return;
  if (state.pickBind) {
    placePickedBindOnSlot(bar, index);
    return;
  }
  if (state.pickSkill) {
    if (!tryPlaceSkillOnSlot(bar, index, state.pickSkill)) {
      state.pickSlot = { bar, index };
      render();
      return;
    }
    state.pickSlot = { bar, index };
    state.pickKey = null;
    state.pickSkill = null;
    const ref = qbRef(bar, index);
    showInspect(qbSkill(bar, index), ref && ref.key, ref && ref.layer);
    render();
    return;
  }
  if (state.pickKey && !isMove(state.pickKey)) {
    placeBindOnSlot(bar, index, state.layer, state.pickKey);
    state.pickSlot = { bar, index };
    showInspect(bindAt(state.pickKey), state.pickKey);
    render();
    return;
  }
  const ref = qbRef(bar, index);
  state.pickSlot = { bar, index };
  state.pickKey = null;
  showInspect(qbSkill(bar, index), ref && ref.key, ref && ref.layer);
  render();
}

function cycleExtraBar(bar) {
  const spec = QB_BARS[bar];
  if (!spec || spec.kind !== "extra" || !spec.mode) return;
  const next = (extraLayout(state.quickbar[spec.mode]).mode + 1) % 4;
  setExtraMode(state.quickbar, spec.mode, next);
  save();
  render();
}

function unbindKey(key, layer) {
  if (!key || isMove(key)) return;
  const lay = layer || state.layer;
  assignOnLayer(lay, key, null);
  state.pickSkill = null;
  state.pickKey = key;
  showInspect(null, key, lay);
  render();
}

function onSkill(id) {
  if (state.view === "stigmas") {
    onStigmaPick(id, false);
    return;
  }
  if (state.pickSlot) {
    if (tryPlaceSkillOnSlot(state.pickSlot.bar, state.pickSlot.index, id)) {
      const ref = qbRef(state.pickSlot.bar, state.pickSlot.index);
      showInspect(id, ref && ref.key, ref && ref.layer);
      state.pickSkill = null;
      render();
      return;
    }
    state.pickSkill = id;
    showInspect(id, usedMap()[id]);
    render();
    return;
  }
  if (state.pickKey && !isMove(state.pickKey)) {
    assign(state.pickKey, id);
    showInspect(id, state.pickKey);
    state.pickSkill = null;
    render();
    return;
  }
  state.pickSkill = state.pickSkill === id ? null : id;
  showInspect(id, usedMap()[id]);
  render();
}

function onStigmaPick(id, fromTree) {
  if (!id || !stigmaTier(id)) return;
  if (findStigmaSlot(id)) {
    if (fromTree) removeCascade(id);
    render();
    return;
  }
  if (fromTree) installChain(id);
  else {
    const slot = firstEmptyCompatible(id);
    if (slot) installStigma(slot.tier, slot.index, id);
  }
  render();
}

function onStigmaSlot(tier, index) {
  const id = state.stigmas[tier][index];
  if (id) removeCascade(id);
  render();
}

let dnd = null;
let ignoreClick = false;

function dropKeyFromEvent(e) {
  const btn = e.target.closest("[data-key]");
  if (!btn || isMove(btn.dataset.key)) return null;
  return btn.dataset.key;
}

function dropSlotFromEvent(e) {
  const btn = e.target.closest("[data-qb-bar]");
  if (!btn) return null;
  const bar = btn.dataset.qbBar;
  const index = Number(btn.dataset.qbIndex);
  if (!QB_BARS[bar] || !Number.isInteger(index) || index < 0 || index >= QB_SLOT_COUNT) return null;
  return { bar, index };
}

function setDropTarget(el) {
  document.querySelectorAll(".drop-ok").forEach((n) => {
    if (n !== el) n.classList.remove("drop-ok");
  });
  if (el) el.classList.add("drop-ok");
}

function clearDndMarks() {
  document.querySelectorAll(".drop-ok, .dragging").forEach((n) => {
    n.classList.remove("drop-ok", "dragging");
  });
}

function onBindDragStart(e) {
  if (e.target.closest("[data-clear-key], [data-clear-slot]")) {
    e.preventDefault();
    return;
  }
  const src = e.target.closest("[data-skill], [data-qb-bar], [data-key]");
  if (!src) {
    dnd = null;
    return;
  }
  if (src.hasAttribute("data-qb-bar")) {
    const bar = src.dataset.qbBar;
    const index = Number(src.dataset.qbIndex);
    const ref = qbRef(bar, index);
    if (!ref) {
      dnd = null;
      return;
    }
    dnd = { from: "slot", bar, index, ref, skill: qbSkill(bar, index) };
    src.classList.add("dragging");
  } else if (src.dataset.skill && state.view !== "stigmas") {
    if (src.dataset.layer && src.dataset.key) {
      dnd = {
        from: "key",
        key: src.dataset.key,
        layer: src.dataset.layer,
        skill: src.dataset.skill,
      };
    } else {
      dnd = { from: "skill", skill: src.dataset.skill };
    }
    src.classList.add("dragging");
  } else if (src.dataset.key && bindAt(src.dataset.key) && !isMove(src.dataset.key)) {
    dnd = { from: "key", key: src.dataset.key, layer: state.layer, skill: bindAt(src.dataset.key) };
    src.classList.add("dragging");
  } else {
    dnd = null;
    return;
  }
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", dnd.skill || `${(dnd.ref && dnd.ref.layer) || dnd.layer}:${dnd.key || (dnd.ref && dnd.ref.key) || ""}`);
}

function onBindDragOver(e) {
  if (!dnd) return;
  const key = dropKeyFromEvent(e);
  const slot = dropSlotFromEvent(e);
  if (!key && !slot) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
  setDropTarget(e.target.closest("[data-key], [data-qb-bar]"));
}

function onBindDragLeave(e) {
  const btn = e.target.closest("[data-key], [data-qb-bar]");
  if (!btn) return;
  if (e.relatedTarget && btn.contains(e.relatedTarget)) return;
  btn.classList.remove("drop-ok");
}

function applySlotDrop(to, dndSrc) {
  if (dndSrc.from === "key") {
    return placeBindOnSlot(to.bar, to.index, dndSrc.layer || state.layer, dndSrc.key);
  }
  if (dndSrc.from === "slot") {
    if (dndSrc.bar === to.bar && dndSrc.index === to.index) return false;
    const fromRef = qbRef(dndSrc.bar, dndSrc.index);
    const toRef = qbRef(to.bar, to.index);
    setQbRef(to.bar, to.index, fromRef);
    setQbRef(dndSrc.bar, dndSrc.index, toRef);
    save();
    return true;
  }
  return tryPlaceSkillOnSlot(to.bar, to.index, dndSrc.skill);
}

function onBindDrop(e) {
  const toKey = dropKeyFromEvent(e);
  const toSlot = dropSlotFromEvent(e);
  if (!dnd || (!toKey && !toSlot)) return;
  e.preventDefault();
  let ok = false;
  if (toSlot) {
    ok = applySlotDrop(toSlot, dnd);
    if (ok) {
      ignoreClick = true;
      state.pickSkill = null;
      state.pickKey = null;
      state.pickSlot = toSlot;
      const ref = qbRef(toSlot.bar, toSlot.index);
      showInspect(qbSkill(toSlot.bar, toSlot.index), ref && ref.key, ref && ref.layer);
      render();
    }
  } else {
    if (dnd.from === "key") ok = swapOrMove(dnd.key, toKey);
    else if (dnd.from === "slot") {
      const sid = dnd.skill || qbSkill(dnd.bar, dnd.index);
      ok = sid ? placeSkillOnKey(toKey, sid) : false;
    } else ok = placeSkillOnKey(toKey, dnd.skill);
    if (ok) {
      ignoreClick = true;
      state.pickSkill = null;
      state.pickSlot = null;
      state.pickKey = toKey;
      showInspect(bindAt(toKey), toKey);
      render();
    }
  }
  dnd = null;
  clearDndMarks();
}

function onBindDragEnd() {
  dnd = null;
  clearDndMarks();
}

function handleBindClick(e) {
  if (ignoreClick) {
    ignoreClick = false;
    return;
  }
  const clear = e.target.closest("[data-clear-key]");
  if (clear) {
    e.preventDefault();
    e.stopPropagation();
    unbindKey(clear.dataset.clearKey);
    return;
  }
  const btn = e.target.closest("[data-key]");
  if (btn) onKey(btn.dataset.key);
}

function handleBindContext(e) {
  const btn = e.target.closest("[data-key]");
  if (!btn) return;
  e.preventDefault();
  unbindKey(btn.dataset.key);
}

for (const id of ["keyboard", "mouse"]) {
  const el = document.getElementById(id);
  el.addEventListener("click", handleBindClick);
  el.addEventListener("contextmenu", handleBindContext);
  el.addEventListener("dragstart", onBindDragStart);
  el.addEventListener("dragover", onBindDragOver);
  el.addEventListener("dragleave", onBindDragLeave);
  el.addEventListener("drop", onBindDrop);
  el.addEventListener("dragend", onBindDragEnd);
}
(function bindQuickbarHud() {
  const el = document.getElementById("quickbar-hud");
  if (!el) return;
  el.addEventListener("click", (e) => {
    if (ignoreClick) {
      ignoreClick = false;
      return;
    }
    const rot = e.target.closest("[data-qb-rotate]");
    if (rot) {
      e.preventDefault();
      cycleExtraBar(rot.dataset.qbRotate);
      return;
    }
    const clear = e.target.closest("[data-clear-slot]");
    if (clear) {
      e.preventDefault();
      e.stopPropagation();
      const [bar, idx] = clear.dataset.clearSlot.split(":");
      if (QB_BARS[bar]) clearHudSlot(bar, Number(idx));
      return;
    }
    const slot = e.target.closest("[data-qb-bar]");
    if (slot) onSlot(slot.dataset.qbBar, Number(slot.dataset.qbIndex));
  });
  el.addEventListener("contextmenu", (e) => {
    const slot = e.target.closest("[data-qb-bar]");
    if (!slot) return;
    e.preventDefault();
    clearHudSlot(slot.dataset.qbBar, Number(slot.dataset.qbIndex));
  });
  el.addEventListener("dragstart", onBindDragStart);
  el.addEventListener("dragover", onBindDragOver);
  el.addEventListener("dragleave", onBindDragLeave);
  el.addEventListener("drop", onBindDrop);
  el.addEventListener("dragend", onBindDragEnd);
})();
document.getElementById("skills").addEventListener("dragstart", onBindDragStart);
document.getElementById("skills").addEventListener("dragend", onBindDragEnd);
document.getElementById("skills").addEventListener("click", (e) => {
  if (ignoreClick) {
    ignoreClick = false;
    return;
  }
  const btn = e.target.closest("[data-skill]");
  if (!btn) return;
  if (state.view === "hud" && btn.dataset.layer && btn.dataset.key) {
    onHudBindPick(btn.dataset.skill, btn.dataset.layer, btn.dataset.key);
    return;
  }
  onSkill(btn.dataset.skill);
});
function placeHoverCard(e) {
  const host = e.target.closest(".slot, .stigma-row, .tree-flow-node, .skill-item");
  if (!host) return;
  const card = host.querySelector(":scope > .skill-hover-card");
  if (!card) return;
  const r = host.getBoundingClientRect();
  const spaceBelow = window.innerHeight - r.bottom;
  const flip = spaceBelow < 240;
  card.style.setProperty("--hover-top", `${Math.round(flip ? r.top : r.bottom)}px`);
  card.style.setProperty("--hover-left", `${Math.round(r.left + r.width / 2)}px`);
  card.classList.toggle("hover-flip", flip);
}
document.getElementById("stigma-view").addEventListener("pointerover", placeHoverCard);
document.getElementById("skills").addEventListener("pointerover", placeHoverCard);
document.getElementById("stigma-view").addEventListener("click", (e) => {
  const slotBtn = e.target.closest("[data-stigma-tier]");
  if (slotBtn) {
    onStigmaSlot(slotBtn.dataset.stigmaTier, Number(slotBtn.dataset.stigmaIndex));
    return;
  }
  const skillBtn = e.target.closest("[data-skill]");
  if (skillBtn) onStigmaPick(skillBtn.dataset.skill, skillBtn.dataset.stigmaSrc === "tree");
});
document.querySelector(".layers").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-layer]");
  if (!btn) return;
  state.layer = btn.dataset.layer;
  state.pickKey = null;
  render();
});
document.querySelector(".view-tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-view]");
  if (!btn) return;
  const prev = state.view;
  state.view = btn.dataset.view;
  if (state.view === "stigmas" || prev === "stigmas") {
    state.pickSkill = null;
    state.pickSlot = null;
    state.pickKey = null;
    state.pickBind = null;
  }
  if (state.view !== "hud") state.pickBind = null;
  render();
});
document.querySelector(".race-switch").addEventListener("click", (e) => {
  const multi = e.target.closest("#multirace");
  if (multi) {
    setMultirace(!state.multirace);
    return;
  }
  const btn = e.target.closest("[data-race]");
  if (btn) setRace(btn.dataset.race);
});
document.getElementById("class-pick").addEventListener("change", (e) => {
  if (classPickSync) return;
  setClass(e.target.value);
});
document.getElementById("share").addEventListener("click", copyShareLink);
document.getElementById("reset-binds").addEventListener("click", openResetBindsModal);
document.getElementById("reset-binds-cancel").addEventListener("click", closeResetBindsModal);
document.getElementById("reset-binds-confirm").addEventListener("click", confirmResetBinds);
document.getElementById("reset-binds-modal").addEventListener("click", (e) => {
  if (e.target.closest("[data-reset-cancel]")) closeResetBindsModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const modal = document.getElementById("reset-binds-modal");
  if (!modal.hidden) closeResetBindsModal();
});
document.getElementById("reset-stigmas").addEventListener("click", clearAllStigmas);
document.getElementById("inspect").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-unbind]");
  if (btn) unbindKey(btn.dataset.unbind, btn.dataset.unbindLayer);
});
document.getElementById("filter").addEventListener("input", () => {
  if (state.view !== "stigmas") renderSkills();
});

function fillClassPick() {
  const sel = document.getElementById("class-pick");
  if (!sel || typeof CLASSES === "undefined") return;
  classPickSync = true;
  sel.innerHTML = CLASSES.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
  sel.value = state.class;
  classPickSync = false;
}

loadState();
fillClassPick();
renderCombos();
openShareFromUrl().finally(() => {
  fillClassPick();
  render();
  if (USE_STATE_API) pullState();
});
if (USE_STATE_API) setInterval(pullState, 800);
