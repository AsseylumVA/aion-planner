const STORE = "aion-binds-v8";
const STATE_API = "http://127.0.0.1:46462/api/state";

const state = {
  view: "binds",
  layer: "combat",
  class: DEFAULT_CLASS,
  race: DEFAULT_RACE,
  multirace: false,
  stigmas: defaultStigmaBoard(),
  binds: null,
  byClass: {},
  pickSkill: null,
  pickKey: null,
  pickSlot: null,
};

loadState();

function defaultState() {
  const stigmas = defaultStigmaBoard(DEFAULT_CLASS);
  return {
    class: DEFAULT_CLASS,
    race: DEFAULT_RACE,
    multirace: false,
    stigmas,
    binds: buildDefaultBinds(DEFAULT_CLASS, DEFAULT_RACE, stigmas),
    byClass: {},
  };
}

function cleanClass(id) {
  if (id && typeof CLASSES !== "undefined" && CLASSES.some((c) => c.id === id)) return id;
  return DEFAULT_CLASS;
}

function loadState() {
  const fallback = defaultState();
  try {
    const raw = localStorage.getItem(STORE);
    if (!raw) {
      applyCore(fallback);
      return;
    }
    const parsed = JSON.parse(raw);
    state.class = cleanClass(parsed.class);
    state.race = parsed.race === "elyos" ? "elyos" : "asmo";
    state.multirace = Boolean(parsed.multirace);
    state.byClass = parsed.byClass && typeof parsed.byClass === "object" ? parsed.byClass : {};
    state.stigmas = padStigmas(parsed.stigmas || classLayout(state.class).defaultStigmas);
    pruneStigmas();
    const base = buildDefaultBinds(state.class, state.race, state.stigmas);
    state.binds = {
      combat: { ...base.combat, ...(parsed.binds && parsed.binds.combat) },
      shift: { ...base.shift, ...(parsed.binds && parsed.binds.shift) },
      ctrl: { ...base.ctrl, ...(parsed.binds && parsed.binds.ctrl) },
    };
    pruneBinds();
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
  state.byClass = next.byClass || {};
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
    },
  };
}

function skillName(id) {
  return id && SKILLS[id] ? SKILLS[id].name : null;
}

let lastRemoteAt = 0;

function snapshot(source) {
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
    byClass: state.byClass,
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
  };
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
  localStorage.setItem(STORE, JSON.stringify(payload));
  fetch(STATE_API, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => {});
}

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    t.style.display = "none";
  }, 1600);
}

async function saveToFile() {
  save();
  toast("Сохранено");
}

function sharePayload() {
  return {
    k: state.class,
    r: state.race === "elyos" ? 1 : 0,
    m: state.multirace ? 1 : 0,
    n: state.stigmas.normal.map((id) => id || ""),
    g: state.stigmas.greater.map((id) => id || ""),
    c: state.binds.combat,
    s: state.binds.shift,
    t: state.binds.ctrl,
  };
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
  const raw = new TextEncoder().encode(JSON.stringify(data));
  if (typeof CompressionStream === "function") {
    try {
      const packed = await transformBytes(raw, new CompressionStream("gzip"));
      if (packed.length < raw.length) return "z" + bytesToB64url(packed);
    } catch {
      /* fallback to json */
    }
  }
  return "j" + bytesToB64url(raw);
}

async function decodeShare(token) {
  if (!token || token.length < 2) throw new Error("empty");
  const kind = token[0];
  const bytes = b64urlToBytes(token.slice(1));
  let jsonBytes = bytes;
  if (kind === "z") {
    if (typeof DecompressionStream !== "function") throw new Error("gzip");
    jsonBytes = await transformBytes(bytes, new DecompressionStream("gzip"));
  } else if (kind !== "j") {
    throw new Error("format");
  }
  const data = JSON.parse(new TextDecoder().decode(jsonBytes));
  if (!data || typeof data !== "object") throw new Error("payload");
  return data;
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
  };
  pruneBinds();
  state.pickSkill = null;
  state.pickKey = null;
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
  const next = new URL(location.href);
  next.searchParams.delete("s");
  history.replaceState(null, "", next.pathname + next.search);
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
    if (!window.confirm("Открыть раскладку из ссылки? Текущие бинды и стигмы будут заменены.")) {
      clearShareFromLocation();
      return;
    }
    applyShare(data);
    save();
    clearShareFromLocation();
    toast("Открыта раскладка по ссылке");
  } catch {
    toast("Ссылка повреждена");
  }
}

async function pullState() {
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
  if (typeof CHAIN_FOLLOW !== "undefined" && CHAIN_FOLLOW.has(id)) return false;
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
  if (typeof CHAIN_FOLLOW !== "undefined" && CHAIN_FOLLOW.has(sid)) return true;
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
  if (key === "Digit1" && !isInstalledStigma("ambush")) return false;
  return LOCKED.has(`${state.layer}:${prettyKey(key)}`);
}

function isMove(key) {
  return MOVE.has(key);
}

function bindAt(key) {
  const sid = state.binds[state.layer][key] || null;
  return sid && isVisibleSkill(sid) ? sid : null;
}

function skillIcon(id) {
  return `img/skills/${id}.png?v=42`;
}

function iconTag(id, cls) {
  if (!id || !SKILLS[id]) return "";
  return `<img class="${cls}" src="${skillIcon(id)}" alt="" draggable="false" onerror="this.remove()">`;
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
  for (const layer of ["combat", "shift", "ctrl"]) {
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
  return `Ctrl+${label}`;
}

function assign(key, skillId) {
  if (isMove(key)) return;
  if (skillId && !isVisibleSkill(skillId)) return;
  const layer = state.binds[state.layer];
  for (const [k, sid] of Object.entries(layer)) {
    if (sid === skillId) delete layer[k];
  }
  if (skillId) layer[key] = skillId;
  else delete layer[key];
  save();
}

function swapOrMove(fromKey, toKey) {
  if (!fromKey || !toKey || fromKey === toKey || isMove(fromKey) || isMove(toKey)) return false;
  const layer = state.binds[state.layer];
  const fromSkill = layer[fromKey];
  if (!fromSkill) return false;
  const toSkill = layer[toKey] || null;
  if (toSkill) layer[fromKey] = toSkill;
  else delete layer[fromKey];
  layer[toKey] = fromSkill;
  save();
  return true;
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

function emptyBinds() {
  return { combat: {}, shift: {}, ctrl: {} };
}

function clearAllBinds() {
  state.binds = emptyBinds();
  state.pickSkill = null;
  state.pickKey = null;
  save();
  render();
}

function clearAllStigmas() {
  for (const id of installedStigmaSet(state.stigmas)) removeSkillBinds(id);
  state.stigmas = emptyStigmas();
  pruneBinds();
  save();
  render();
}

function applyStigmaDefault(id) {
  const layout = classLayout(state.class);
  const slot = (layout.stigma && layout.stigma[id]) || STIGMA_BINDS[id];
  if (!slot) return;
  applyBind(state.binds, slot.layer, slot.key, id);
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
  for (const row of classLayout(state.class).racial[race] || []) {
    applyBind(state.binds, row.layer, row.key, row.skill);
  }
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
  persistClassSnapshot(state.class);
  state.class = cls;
  const snap = state.byClass[cls];
  if (snap && snap.binds) {
    state.stigmas = padStigmas(snap.stigmas);
    state.binds = {
      combat: { ...(snap.binds.combat || {}) },
      shift: { ...(snap.binds.shift || {}) },
      ctrl: { ...(snap.binds.ctrl || {}) },
    };
  } else {
    state.stigmas = defaultStigmaBoard(cls);
    state.binds = buildDefaultBinds(cls, state.race, state.stigmas);
  }
  pruneStigmas();
  pruneBinds();
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
  if (id) applyStigmaDefault(id);
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

function stigmaHover(id, missing) {
  if (!id || !SKILLS[id]) return "";
  const s = SKILLS[id];
  const en = STIGMA_ID_TO_EN[id] || "";
  const tier = stigmaTier(id) === "greater" ? "Greater Stigma" : "Normal Stigma";
  const reqs =
    missing && missing.length
      ? `<span class="hover-requirements">Нужно: ${missing.join(", ")}</span>`
      : "";
  return `<span class="skill-hover-card">
    <span class="hover-title">${s.name}</span>
    <span class="hover-meta">${en ? en + " · " : ""}${tier} · КД ${s.cd}</span>
    <span class="hover-description">${s.desc}</span>
    ${reqs}
  </span>`;
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

function showInspect(skillId, key) {
  const el = document.getElementById("inspect");
  if (!skillId) {
    el.innerHTML = `<p>${isMove(key) ? "W и S — вперёд/назад. A и D под скиллы, камера мышью." : "Пустой слот. Перетащите умение с другой клавиши или из списка справа. Клик по скиллу — крестик, чтобы снять."}</p>`;
    return;
  }
  const s = SKILLS[skillId];
  const tags = skillTags(skillId)
    .map((t) => `<span class="${tagClass(t)}">${t}</span>`)
    .join("");
  const unbind =
    key && !isMove(key)
      ? `<button type="button" class="unbind" data-unbind="${key}">Снять с ${prettyKey(key)}</button>`
      : "";
  el.innerHTML = `
    <div class="inspect-head">
      ${iconTag(skillId, "icon-lg")}
      <h3>${s.name}</h3>
    </div>
    <div class="tags">${tags}</div>
    <p>${s.desc}</p>
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
    return [s.name, s.desc, ...(s.tags || [])].join(" ").toLowerCase().includes(q);
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
  </button>`;
}

function renderSkills() {
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
  document.getElementById("skills").innerHTML =
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
  if (pick && pick.value !== state.class) pick.value = state.class;
  document.querySelectorAll("[data-layer]").forEach((b) => {
    b.classList.toggle("active", b.dataset.layer === state.layer);
  });
  document.getElementById("binds-view").hidden = state.view !== "binds";
  document.getElementById("stigma-view").hidden = state.view !== "stigmas";
  document.getElementById("reset-binds").hidden = state.view !== "binds";
  document.getElementById("reset-stigmas").hidden = state.view !== "stigmas";
  document.querySelector(".app").classList.toggle("is-stigmas", state.view === "stigmas");
  document.getElementById("combos").hidden = state.view === "stigmas" || !classCombos(state.class).length;
  const sideTitle = document.getElementById("side-title");
  const filter = document.getElementById("filter");
  if (state.view === "stigmas") {
    sideTitle.textContent = "Стигмы";
    filter.placeholder = "Поиск стигмы…";
  } else {
    sideTitle.textContent = "Умения и стигмы";
    filter.placeholder = "Поиск умения…";
    document.getElementById("skills").classList.remove("is-stigma-pool");
  }
  const mouseHint = document.getElementById("mouse-hint");
  const boardHint = document.getElementById("board-hint");
  if (state.class === "assassin") {
    if (mouseHint) mouseHint.textContent = "Мышь — в движении. M4 клятва уклонения, M5 маскировка, колесо просветление.";
    if (boardHint) {
      boardHint.textContent =
        "До боя только F1–F5: скорость, чувства, готовность, штурмовая, точность (КТ последней). В бою Q ритуал, E ТР. Контроль: F клеймо, C вспышка-стан, B кинжал в воздух, V спина, X убийство, ⇧C клинок, ⇧B смертельные яды. Перетащите скилл на другую клавишу, чтобы поменять местами. Клик по скиллу — крестик справа сверху, чтобы снять. ПКМ тоже снимает.";
    }
  } else {
    if (mouseHint) mouseHint.textContent = "Мышь — в движении. W/S ход, A и D — скиллы. Автоатака и смена оружия не на M4/M5.";
    if (boardHint) {
      boardHint.textContent =
        "F1–F5 — баффы до боя. Боевые умения на 1–5 и Q E R A D F. Клавиши 6+ и F7–F12 далеко для боя. Перетащите скилл на клавишу. Клик по скиллу — крестик, чтобы снять. ПКМ тоже снимает.";
    }
  }
}

function render() {
  renderChrome();
  if (state.view === "binds") {
    renderKeyboard();
    renderSkills();
    paintMouse();
  } else {
    renderStigmaBoard();
    renderStigmaPool();
    renderStigmaTrees();
  }
}

function onKey(key) {
  if (isMove(key)) {
    state.pickKey = key;
    showInspect(null, key);
    render();
    return;
  }
  if (state.pickSkill) {
    assign(key, state.pickSkill);
    state.pickKey = key;
    showInspect(state.pickSkill, key);
    state.pickSkill = null;
    render();
    return;
  }
  state.pickKey = key;
  showInspect(bindAt(key), key);
  render();
}

function unbindKey(key) {
  if (!key || isMove(key)) return;
  assign(key, null);
  state.pickSkill = null;
  state.pickKey = key;
  showInspect(null, key);
  render();
}

function onSkill(id) {
  if (state.view === "stigmas") {
    onStigmaPick(id, false);
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

function copyBinds() {
  const raceName = state.race === "elyos" ? "Элиос" : "Асмодианин";
  const lines = [
    `Aion 4.6 ${classNameOf(state.class)} — ${raceName}${state.multirace ? ", мультирасса" : ""}, W/S ход, A/D скиллы`,
    "",
    "Стигмы",
    "Обычные: " + state.stigmas.normal.map((id) => (id ? SKILLS[id].name : "—")).join(", "),
    "Великие: " + state.stigmas.greater.map((id) => (id ? SKILLS[id].name : "—")).join(", "),
    "",
    "Бой",
  ];
  const dump = (layer, prefix) => {
    const entries = Object.entries(state.binds[layer]).filter(([, sid]) => isVisibleSkill(sid));
    entries.sort((a, b) => prettyKey(a[0]).localeCompare(prettyKey(b[0]), "ru"));
    for (const [key, sid] of entries) {
      lines.push(`${prefix}${prettyKey(key)}  ${SKILLS[sid].name}`);
    }
  };
  dump("combat", "");
  lines.push("", "Shift");
  dump("shift", "⇧");
  lines.push("", "Ctrl");
  dump("ctrl", "Ctrl+");
  navigator.clipboard.writeText(lines.join("\n")).then(() => {
    toast("Скопировано");
  });
}

let dnd = null;
let ignoreClick = false;

function dropKeyFromEvent(e) {
  const btn = e.target.closest("[data-key]");
  if (!btn || isMove(btn.dataset.key)) return null;
  return btn.dataset.key;
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
  if (e.target.closest("[data-clear-key]")) {
    e.preventDefault();
    return;
  }
  const keyBtn = e.target.closest("[data-key]");
  const skillBtn = e.target.closest("[data-skill]");
  if (keyBtn && bindAt(keyBtn.dataset.key) && !isMove(keyBtn.dataset.key)) {
    dnd = { from: "key", key: keyBtn.dataset.key, skill: bindAt(keyBtn.dataset.key) };
    keyBtn.classList.add("dragging");
  } else if (skillBtn && state.view === "binds" && skillBtn.dataset.skill) {
    dnd = { from: "skill", skill: skillBtn.dataset.skill };
    skillBtn.classList.add("dragging");
  } else {
    dnd = null;
    return;
  }
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", dnd.skill);
}

function onBindDragOver(e) {
  if (!dnd) return;
  const key = dropKeyFromEvent(e);
  if (!key) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
  setDropTarget(e.target.closest("[data-key]"));
}

function onBindDragLeave(e) {
  const btn = e.target.closest("[data-key]");
  if (!btn) return;
  if (e.relatedTarget && btn.contains(e.relatedTarget)) return;
  btn.classList.remove("drop-ok");
}

function onBindDrop(e) {
  const toKey = dropKeyFromEvent(e);
  if (!dnd || !toKey) return;
  e.preventDefault();
  const ok = dnd.from === "key" ? swapOrMove(dnd.key, toKey) : placeSkillOnKey(toKey, dnd.skill);
  if (ok) {
    ignoreClick = true;
    state.pickSkill = null;
    state.pickKey = toKey;
    showInspect(bindAt(toKey), toKey);
    render();
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
document.getElementById("skills").addEventListener("dragstart", onBindDragStart);
document.getElementById("skills").addEventListener("dragend", onBindDragEnd);
document.getElementById("skills").addEventListener("click", (e) => {
  if (ignoreClick) {
    ignoreClick = false;
    return;
  }
  const btn = e.target.closest("[data-skill]");
  if (btn) onSkill(btn.dataset.skill);
});
document.getElementById("stigma-view").addEventListener("pointerover", (e) => {
  const host = e.target.closest(".slot, .stigma-row, .tree-flow-node");
  if (!host) return;
  const card = host.querySelector(":scope > .skill-hover-card");
  if (!card) return;
  const r = host.getBoundingClientRect();
  card.style.setProperty("--hover-top", `${Math.round(r.bottom)}px`);
  card.style.setProperty("--hover-left", `${Math.round(r.left + r.width / 2)}px`);
});
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
  state.view = btn.dataset.view;
  state.pickSkill = null;
  state.pickSlot = null;
  state.pickKey = null;
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
  setClass(e.target.value);
});
document.getElementById("save-state").addEventListener("click", saveToFile);
document.getElementById("share").addEventListener("click", copyShareLink);
document.getElementById("copy").addEventListener("click", copyBinds);
document.getElementById("reset-binds").addEventListener("click", clearAllBinds);
document.getElementById("reset-stigmas").addEventListener("click", clearAllStigmas);
document.getElementById("inspect").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-unbind]");
  if (btn) unbindKey(btn.dataset.unbind);
});
document.getElementById("filter").addEventListener("input", () => {
  if (state.view !== "stigmas") renderSkills();
});

function fillClassPick() {
  const sel = document.getElementById("class-pick");
  if (!sel || typeof CLASSES === "undefined") return;
  sel.innerHTML = CLASSES.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
  sel.value = state.class;
}

fillClassPick();
renderCombos();
openShareFromUrl().finally(() => {
  render();
  pullState();
});
setInterval(pullState, 800);
