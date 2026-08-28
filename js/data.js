const COMBOS = [
  {
    title: "Засада-клык",
    keys: "F6 · 1 → 5",
    text: "В поле всё на внезапность: из инвиза засада и сразу клык. До подхода — слабые места ⇧R, клятвы F1–F5, в бою ритуал Q и ТР E. Если цель в барьере и стан не прошёл — не сливать засаду в уворот.",
  },
  {
    title: "Клеймо III+, потом вспышка",
    keys: "2 / F → C · ⇧F",
    text: "Вспышка C и оковы ⇧F имеют смысл только с клейма III. Клеймо F и серия рева на 2 дают +1. В оковы лучше в V: свиток поглощения съест урон с III, и цель не повиснет.",
  },
  {
    title: "Истребление — не в открытие",
    keys: "⇧E",
    text: "Не сливать в начале боя. Даёт +2 к текущему клейму: на цели II и она в антишоке убегает — станет IV, можно вспышку или оковы. Каст с места, рвётся с 16 м. Не для осады.",
  },
  {
    title: "Режущая → опрокид",
    keys: "A → ⇧A",
    text: "Режущая и подлый набег — почти всегда полсекунды стана. Сразу падение в тень: развод на антишок, засада цела. На пинге можно не успеть. Клык, рев и истребление привязывают к месту.",
  },
  {
    title: "После уворота, ~2 с",
    keys: "Z → D / ⇧D · R",
    text: "Контра и ураган — триггеры после любого уклона, окно около 2 с. Стан контры не 100%. Цепь уклонений R, пока висит уклон. Обострялка F2. Клятва уклонения ⇧Z — дольше по анимации, на наживку лучше Z.",
  },
  {
    title: "Снять уклон",
    keys: "G · H · ⇧G",
    text: "Против сина, лука и сорка побеждает кто быстрее жмёт вспышки. Тьма ⇧G на 20 м — как засада; иссушающее G и особое H ближе. Подлый удар V (−800 уклона) — не дебаф, банкой не снимается, толк только vs син/лук.",
  },
  {
    title: "Второй антишок",
    keys: "Ctrl+F · Ctrl+E · Ё",
    text: "Спасение 7 с +500, усмирение 30 с +500. Вместе как второй антишок: после своего АШ или в начале, чтобы сорк слил падение и ураган. Снятие шока Ё. Со стойкой налетчика обострялка и цепь бессмысленны.",
  },
  {
    title: "Что-то пошло не так",
    keys: "⇧2 · T · Ctrl+D · Ctrl+F",
    text: "Прыжок на 15 м, теневая иллюзия, покров сумрака. Иллюзия в полёте не жмётся: сложить крылья, снять корень, сбросить цель, снова открыть. В воздухе в корне — спасение, без возни с крыльями.",
  },
];

const LOCKED = new Set(["combat:1", "combat:2", "combat:3", "combat:4", "combat:5"]);
const MOVE = new Set(["KeyW", "KeyS"]);
const CHAIN_FOLLOW = new Set([
  "cleave",
  "beastKick",
  "beastSwipe",
  "ancient",
  "sideStrike",
  "encirclingStrike",
  "crossSlash",
  "storm",
]);

const DEFAULT_RACE = "asmo";
const STIGMA_SLOTS = { normal: 6, greater: 6 };

// Как на stigma.origincdx.com: 4×3, слева обычные, справа великие.
const STIGMA_BOARD = [
  { tier: "normal", index: 0, level: 20 },
  { tier: "normal", index: 1, level: 20 },
  { tier: "greater", index: 0, level: 45 },
  { tier: "greater", index: 1, level: 45 },
  { tier: "normal", index: 2, level: 30 },
  { tier: "normal", index: 3, level: 40 },
  { tier: "greater", index: 2, level: 50 },
  { tier: "greater", index: 3, level: 52 },
  { tier: "normal", index: 4, level: 50 },
  { tier: "normal", index: 5, level: 60 },
  { tier: "greater", index: 4, level: 53 },
  { tier: "greater", index: 5, level: 59 },
];

const DEFAULT_STIGMAS = {
  normal: ["ambush", "complex", "fog", "crush", "oathDodge", "oathSpeed"],
  greater: ["lightning", "senses"],
};

const STIGMA_EN_TO_ID = {
  Flurry: "oathSpeed",
  Aethertwisting: "oathDodge",
  Ambush: "ambush",
  "Apply Deadly Poison": "deadlyPoison",
  "Rune Burst": "crush",
  "Oath of Accuracy": "oathAcc",
  "Rune Knife": "runeKnife",
  "Blinding Burst": "fog",
  "Eye of Wrath": "eyeWrath",
  "Flash of Speed": "flashSpeed",
  "Throw Shuriken": "throwShuriken",
  "Agonizing Slash": "agonySlash",
  "Apply Lethal Venom": "lethalVenom",
  "Beastly Scar": "beastScar",
  "Lightning Slash": "lightning",
  "Shadow Walk": "shadowStep",
  "Deadly Abandon": "deadlyAbandon",
  "Agony Rune": "agonyRune",
  "Dash and Slash": "dashSlash",
  "Divine Rune": "divineRune",
  "Rune Swipe": "runeSwipe",
  "Explosive Burst": "explosiveBurst",
  "Sensory Boost": "senses",
  "Venomous Strike": "poisonHit",
  "Quickening Doom": "quickDoom",
  "Signet Silence": "silenceRune",
  Shadowfall: "shadowfall",
  "Break Away": "escape",
  "Searching Strike": "searchStrike",
};

const STIGMA_ID_TO_EN = Object.fromEntries(
  Object.entries(STIGMA_EN_TO_ID).map(([en, id]) => [id, en])
);
STIGMA_ID_TO_EN.slayerElyos = "Slayer Form";
STIGMA_ID_TO_EN.slayerAsmo = "Slayer Form";
STIGMA_ID_TO_EN.complex = "Complex Rune Carve";

const STIGMA_TREES = [
  {
    name: "Quickening Doom",
    requirements: {
      "Quickening Doom": ["Dash and Slash", "Sensory Boost"],
      "Dash and Slash": ["Apply Lethal Venom", "Lightning Slash"],
      "Apply Lethal Venom": ["Apply Deadly Poison", "Oath of Accuracy"],
      "Lightning Slash": ["Blinding Burst"],
      "Sensory Boost": ["Apply Deadly Poison", "Blinding Burst"],
    },
  },
  {
    name: "Signet Silence",
    requirements: {
      "Signet Silence": ["Agony Rune", "Explosive Burst"],
      "Agony Rune": ["Beastly Scar", "Agonizing Slash"],
      "Beastly Scar": ["Rune Knife", "Rune Burst"],
      "Agonizing Slash": ["Eye of Wrath"],
      "Explosive Burst": ["Rune Knife", "Eye of Wrath"],
    },
  },
];

function stigmaIdFromEn(en) {
  if (en === "Slayer Form") return state.race === "elyos" ? "slayerElyos" : "slayerAsmo";
  return STIGMA_EN_TO_ID[en] || null;
}

function layoutStigmaTree(tree) {
  const nodes = [];
  const connectors = [];
  const col = { leaf: 18, branch: 166, merge: 314, final: 452 };
  const groups = [
    { leafYs: [12, 104, 196], targetY: 104, intermediateYs: [58, 152] },
    { leafX: col.branch, leafYs: [292, 386, 292], targetY: 340, intermediateYs: [292, 386] },
  ];
  const add = (name, x, y) => {
    const node = { id: `${name}-${nodes.length}`, name, x, y };
    nodes.push(node);
    return node;
  };
  const link = (sources, target) => {
    const src = sources.filter(Boolean);
    if (!src.length || !target) return;
    connectors.push({ sources: src, target });
  };
  const branch = (name, cfg) => {
    const target = add(name, cfg.targetX ?? col.merge, cfg.targetY);
    const mids = [];
    let leafI = 0;
    for (const child of tree.requirements[name] || []) {
      const grand = tree.requirements[child] || [];
      if (grand.length) {
        const mid = add(child, cfg.intermediateX ?? col.branch, cfg.intermediateYs[mids.length] ?? cfg.targetY);
        const leaves = grand.map((g) => {
          const n = add(g, cfg.leafX ?? col.leaf, cfg.leafYs[leafI] ?? cfg.leafYs[cfg.leafYs.length - 1]);
          leafI += 1;
          return n;
        });
        link(leaves, mid);
        mids.push(mid);
      } else {
        const n = add(child, cfg.leafX ?? col.leaf, cfg.leafYs[leafI] ?? cfg.leafYs[cfg.leafYs.length - 1]);
        leafI += 1;
        mids.push(n);
      }
    }
    link(mids, target);
    return target;
  };
  const root = add(tree.name, col.final, 222);
  const tops = (tree.requirements[tree.name] || []).map((n, i) => branch(n, groups[i] ?? groups[groups.length - 1]));
  link(tops, root);
  return { nodes, connectors };
}

const STIGMA_REQS = (() => {
  const map = {};
  for (const tree of STIGMA_TREES) {
    for (const [name, reqs] of Object.entries(tree.requirements)) {
      map[name] = reqs;
    }
  }
  return map;
})();

const STIGMA_BINDS = {
  ambush: { layer: "combat", key: "Digit1" },
  oathSpeed: { layer: "combat", key: "F1" },
  senses: { layer: "combat", key: "F2" },
  deadlyAbandon: { layer: "combat", key: "F3" },
  oathAcc: { layer: "combat", key: "F5" },
  oathDodge: { layer: "shift", key: "KeyZ" },
  flashSpeed: { layer: "combat", key: "KeyT" },
  shadowfall: { layer: "shift", key: "KeyA" },
  slayerAsmo: { layer: "ctrl", key: "KeyZ" },
  slayerElyos: { layer: "ctrl", key: "KeyZ" },
  fog: { layer: "shift", key: "KeyQ" },
  deadlyPoison: { layer: "shift", key: "KeyB" },
  escape: { layer: "ctrl", key: "KeyF" },
  complex: { layer: "shift", key: "KeyG" },
  crush: { layer: "shift", key: "KeyG" },
  lightning: { layer: "shift", key: "KeyB" },
  shadowStep: { layer: "combat", key: "F11" },
  runeKnife: { layer: "shift", key: "KeyA" },
  eyeWrath: { layer: "combat", key: "F12" },
  throwShuriken: { layer: "combat", key: "Digit7" },
  poisonHit: { layer: "shift", key: "KeyB" },
  searchStrike: { layer: "shift", key: "KeyV" },
  runeSwipe: { layer: "shift", key: "KeyG" },
  divineRune: { layer: "shift", key: "KeyG" },
  beastScar: { layer: "shift", key: "KeyD" },
  agonySlash: { layer: "shift", key: "KeyN" },
  lethalVenom: { layer: "shift", key: "KeyC" },
  agonyRune: { layer: "combat", key: "KeyH" },
  dashSlash: { layer: "combat", key: "Digit8" },
  silenceRune: { layer: "shift", key: "KeyX" },
  explosiveBurst: { layer: "shift", key: "KeyG" },
  quickDoom: { layer: "combat", key: "Digit9" },
  needle: { layer: "combat", key: "KeyH" },
};

const RACIAL_BINDS = {
  elyos: [
    { layer: "shift", key: "KeyX", skill: "divineStrike" },
    { layer: "ctrl", key: "KeyC", skill: "spelldodge" },
  ],
  asmo: [
    { layer: "shift", key: "KeyX", skill: "darkStrike" },
    { layer: "ctrl", key: "KeyQ", skill: "stance" },
    { layer: "shift", key: "KeyG", skill: "darknessRune" },
  ],
};

const LEARNED_BINDS = {
  combat: {
    Digit2: "roar",
    Digit3: "sudden",
    Digit4: "swift",
    Digit5: "fang",
    KeyA: "dash",
    KeyE: "calc",
    KeyD: "counter",
    KeyR: "evasiveBoost",
    KeyF: "stigma",
    KeyG: "bloodRune",
    KeyH: "needle",
    KeyQ: "ritual",
    KeyC: "flash",
    KeyV: "weaken",
    KeyX: "assassination",
    KeyZ: "focusedEvasion",
    Backquote: "unshock",
    CapsLock: "illusion",
    F4: "deadlyFocus",
    F6: "stealth",
    F7: "dagger",
    Mouse4: "weaponSwap",
    Mouse5: "autoAttack",
    Wheel: "seeing",
  },
  shift: {
    Digit2: "beastLeap",
    Digit3: "killingSpree",
    KeyD: "whirl",
    KeyE: "massacre",
    KeyF: "bindingRune",
    KeyR: "weakspot",
    KeyC: "poisonBlade",
  },
  ctrl: {
    KeyA: "searchingEye",
    KeyE: "calm",
    KeyD: "windWalk",
    KeyR: "powder",
    Digit1: "lifeSerum",
    Digit2: "manaSerum",
    Digit3: "recoverySerum",
    Digit4: "curePotion",
  },
};

function emptyStigmas() {
  return {
    normal: Array(STIGMA_SLOTS.normal).fill(null),
    greater: Array(STIGMA_SLOTS.greater).fill(null),
  };
}

function padStigmas(src) {
  const out = emptyStigmas();
  for (const tier of ["normal", "greater"]) {
    const list = (src && src[tier]) || [];
    for (let i = 0; i < STIGMA_SLOTS[tier]; i++) out[tier][i] = list[i] || null;
  }
  return out;
}

function defaultStigmaBoard() {
  return padStigmas(DEFAULT_STIGMAS);
}

function installedStigmaSet(board) {
  const set = new Set();
  for (const tier of ["normal", "greater"]) {
    for (const id of board[tier]) if (id) set.add(id);
  }
  return set;
}

function applyBind(binds, layer, key, skillId) {
  for (const [k, sid] of Object.entries(binds[layer])) {
    if (sid === skillId) delete binds[layer][k];
  }
  binds[layer][key] = skillId;
}

function buildDefaultBinds(race, board) {
  const binds = structuredClone(LEARNED_BINDS);
  for (const row of RACIAL_BINDS[race] || []) {
    applyBind(binds, row.layer, row.key, row.skill);
  }
  for (const id of installedStigmaSet(board)) {
    const slot = STIGMA_BINDS[id];
    if (slot) applyBind(binds, slot.layer, slot.key, id);
  }
  return binds;
}

const DEFAULT_BINDS = buildDefaultBinds(DEFAULT_RACE, defaultStigmaBoard());

const KEYBOARD = [
  [
    { id: "Escape", label: "Esc", w: 1.2 },
    { id: "F1", label: "F1" },
    { id: "F2", label: "F2" },
    { id: "F3", label: "F3" },
    { id: "F4", label: "F4" },
    { id: "F5", label: "F5" },
    { id: "F6", label: "F6" },
    { id: "F7", label: "F7" },
    { id: "F8", label: "F8" },
    { id: "F9", label: "F9" },
    { id: "F10", label: "F10" },
    { id: "F11", label: "F11" },
    { id: "F12", label: "F12" },
  ],
  [
    { id: "Backquote", label: "Ё `" },
    { id: "Digit1", label: "1" },
    { id: "Digit2", label: "2" },
    { id: "Digit3", label: "3" },
    { id: "Digit4", label: "4" },
    { id: "Digit5", label: "5" },
    { id: "Digit6", label: "6" },
    { id: "Digit7", label: "7" },
    { id: "Digit8", label: "8" },
    { id: "Digit9", label: "9" },
    { id: "Digit0", label: "0" },
    { id: "Minus", label: "-" },
    { id: "Equal", label: "=" },
    { id: "Backspace", label: "⌫", w: 1.6 },
  ],
  [
    { id: "Tab", label: "Tab", w: 1.4 },
    { id: "KeyQ", label: "Q" },
    { id: "KeyW", label: "W" },
    { id: "KeyE", label: "E" },
    { id: "KeyR", label: "R" },
    { id: "KeyT", label: "T" },
    { id: "KeyY", label: "Y" },
    { id: "KeyU", label: "U" },
    { id: "KeyI", label: "I" },
    { id: "KeyO", label: "O" },
    { id: "KeyP", label: "P" },
    { id: "BracketLeft", label: "[" },
    { id: "BracketRight", label: "]" },
  ],
  [
    { id: "CapsLock", label: "Caps", w: 1.7 },
    { id: "KeyA", label: "A" },
    { id: "KeyS", label: "S" },
    { id: "KeyD", label: "D" },
    { id: "KeyF", label: "F" },
    { id: "KeyG", label: "G" },
    { id: "KeyH", label: "H" },
    { id: "KeyJ", label: "J" },
    { id: "KeyK", label: "K" },
    { id: "KeyL", label: "L" },
    { id: "Semicolon", label: ";" },
    { id: "Quote", label: "'" },
    { id: "Enter", label: "↵", w: 1.5 },
  ],
  [
    { id: "ShiftLeft", label: "Shift", w: 2.2 },
    { id: "KeyZ", label: "Z" },
    { id: "KeyX", label: "X" },
    { id: "KeyC", label: "C" },
    { id: "KeyV", label: "V" },
    { id: "KeyB", label: "B" },
    { id: "KeyN", label: "N" },
    { id: "KeyM", label: "M" },
    { id: "Comma", label: "," },
    { id: "Period", label: "." },
    { id: "Slash", label: "/" },
    { id: "ShiftRight", label: "Shift", w: 2.2 },
  ],
  [
    { id: "ControlLeft", label: "Ctrl", w: 1.4 },
    { id: "MetaLeft", label: "Win", w: 1.2 },
    { id: "AltLeft", label: "Alt", w: 1.2 },
    { id: "Space", label: "пробел", w: 6.2 },
    { id: "AltRight", label: "Alt", w: 1.2 },
    { id: "ControlRight", label: "Ctrl", w: 1.4 },
  ],
];
