"""Build js/skills.js and js/class-defaults.js from Origin client XML.

Primary sources: client_skill_learns.xml + client_skills.xml in skills_dec.zip,
client_strings_skill.xml for Russian names/descriptions. Assassin planner IDs
from tools/aidb_details.json are preserved by client skill id.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from io import BytesIO
from pathlib import Path

from client_skill_stats import (
    MAG_STATUS_TAG,
    SKILLS_ZIP,
    STRINGS_PATH,
    client_xml_text,
    fill_client_desc,
    fmt_sec,
    parse_block,
    with_mag_status_tag,
    with_stats,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_JS = ROOT / "js" / "skills.js"
OUT_DEFAULTS = ROOT / "js" / "class-defaults.js"
CATALOG_PATH = ROOT / "tools" / "client_skill_catalog.json"
DETAILS_PATH = ROOT / "tools" / "aidb_details.json"
AIDB_RACE_PATH = ROOT / "tools" / "aidb_race.json"
SKILLS_JS = ROOT / "js" / "skills.js"
ICON_DIR = ROOT / "img" / "skills"

# Specialized 4.6 classes that have Russian names in this client pack.
# Base classes (WARRIOR/SCOUT/MAGE/CLERIC) are folded into their specs.
# GUNNER/BARD/RIDER exist in XML but have no RU class names here — omit.
CLASSES = [
    {"id": "gladiator", "name": "Гладиатор", "client": "FIGHTER", "base": "WARRIOR"},
    {"id": "templar", "name": "Страж", "client": "KNIGHT", "base": "WARRIOR"},
    {"id": "assassin", "name": "Убийца", "client": "ASSASSIN", "base": "SCOUT"},
    {"id": "ranger", "name": "Стрелок", "client": "RANGER", "base": "SCOUT"},
    {"id": "sorcerer", "name": "Волшебник", "client": "WIZARD", "base": "MAGE"},
    {"id": "spiritmaster", "name": "Заклинатель", "client": "ELEMENTALLIST", "base": "MAGE"},
    {"id": "cleric", "name": "Целитель", "client": "PRIEST", "base": "CLERIC"},
    {"id": "chanter", "name": "Чародей", "client": "CHANTER", "base": "CLERIC"},
]
CLASS_IDS = [c["id"] for c in CLASSES]
CLIENT_TO_ID = {c["client"]: c["id"] for c in CLASSES}
BASE_TO_SPECS = defaultdict(list)
for c in CLASSES:
    BASE_TO_SPECS[c["base"]].append(c["id"])

ASSASSIN_CHAIN_FOLLOW = {
    "cleave",
    "beastKick",
    "beastSwipe",
    "ancient",
    "sideStrike",
    "encirclingStrike",
    "crossSlash",
    "storm",
}

SKIP_ACT = {"passive", "provoked"}
SKIP_PREFIX = ("P_EQUIP",)
RACE_MAP = {
    "pc_light": "elyos",
    "pc_dark": "asmo",
    "all": None,
}

# Learned race comes from aidb.ru (class-tree «Только для …» / skill_info Раса),
# not Origin client_skill_learns — Origin is multirace and marks many as All.

RANK_TAIL = re.compile(r"\s+[IVXLCDM]+\s*$")
G_TAIL = re.compile(r"_G(\d+)$")
LEARN_RE = re.compile(r"<client_skill_learn>(.*?)</client_skill_learn>", re.S)
SKILL_RE = re.compile(
    r"<skill_base_client>\s*<id>(\d+)</id>\s*<name>([^<]+)</name>(.*?)</skill_base_client>",
    re.S,
)
FIELD_RE = re.compile(r"<([^/>]+)>([^<]*)</")
STRING_RE = re.compile(r"<name>(STR_SKILL_[^<]+)</name>\s*<body>(.*?)</body>", re.S)
JS_KIND_RE = re.compile(
    r"  (\w+): \{\s*\n    name: \".*?\",\s*\n    kind: \"([^\"]+)\"",
    re.S,
)

EXTRA = {
    "autoAttack": {
        "name": "Атака",
        "kind": "combat",
        "tags": ["ближний"],
        "desc": "Базовая автоатака выбранной цели оружием в руках. Общая для всех классов, в клиенте, не в дереве умений.",
        "cd": "нет",
    },
    "weaponSwap": {
        "name": "Смена оружия",
        "kind": "utility",
        "tags": ["на себя"],
        "desc": "Переключает основной и запасной набор оружия. Общая для всех классов. В клиенте по умолчанию Shift+Z.",
        "cd": "нет",
    },
    "curePotion": {
        "name": "Сильное зелье исцеления",
        "kind": "utility",
        "tags": ["на себя", "КД 10 с"],
        "desc": "Снимает негативные эффекты.",
        "cd": "10 с",
    },
    "recoverySerum": {
        "name": "Редкое зелье восстановления VI",
        "kind": "utility",
        "tags": ["на себя", "КД 10 с"],
        "desc": "Восстанавливает 1940 HP и 1680 MP.",
        "cd": "10 с",
    },
    "manaSerum": {
        "name": "Чудесное зелье маны IV",
        "kind": "utility",
        "tags": ["на себя", "КД 10 с"],
        "desc": "Восстанавливает 3450 MP. За очки бездны.",
        "cd": "10 с",
    },
    "lifeSerum": {
        "name": "Особое зелье жизни IV",
        "kind": "utility",
        "tags": ["на себя", "КД 10 с"],
        "desc": "Восстанавливает 3680 HP. За очки бездны.",
        "cd": "10 с",
    },
    "fastReturn": {
        "name": "Быстрое возвращение",
        "kind": "utility",
        "tags": ["на себя", "КД 3600 с"],
        "desc": "Позволяет вернуться к точке воскрешения.",
        "cd": "3600 с",
    },
}

POTION_IDS = ("curePotion", "recoverySerum", "manaSerum", "lifeSerum")
BASIC_IDS = ("autoAttack", "weaponSwap")

BUFF_KEYS = ["F1", "F2", "F3", "F4", "F5"]
COMBAT_KEYS = [
    "Digit2",
    "Digit3",
    "Digit4",
    "Digit5",
    "KeyQ",
    "KeyE",
    "KeyR",
    "KeyF",
    "KeyA",
    "KeyD",
    "KeyC",
    "KeyV",
    "KeyX",
    "KeyZ",
    "KeyG",
    "KeyH",
]
SHIFT_KEYS = [
    "KeyQ",
    "KeyE",
    "KeyR",
    "KeyF",
    "KeyA",
    "KeyD",
    "KeyC",
    "KeyV",
    "KeyX",
    "KeyZ",
    "KeyG",
    "KeyB",
]
CTRL_POTIONS = {
    "Digit1": "lifeSerum",
    "Digit2": "manaSerum",
    "Digit3": "recoverySerum",
    "Digit4": "curePotion",
}


def js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def load_strings() -> dict[str, str]:
    raw = STRINGS_PATH.read_bytes()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")
    out = {}
    for name, body in STRING_RE.findall(text):
        out[name] = " ".join(body.split())
    return out


def load_old_kinds() -> dict[str, str]:
    if not SKILLS_JS.exists():
        return {}
    return dict(JS_KIND_RE.findall(SKILLS_JS.read_text(encoding="utf-8")))


def load_id_by_client() -> dict[int, str]:
    out: dict[int, str] = {}
    if CATALOG_PATH.exists():
        cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        for sid, rec in cat.get("skills", {}).items():
            cid = rec.get("client_id")
            if cid:
                out[int(cid)] = sid
    if DETAILS_PATH.exists():
        details = json.loads(DETAILS_PATH.read_text(encoding="utf-8"))
        for sid, rec in details.items():
            if rec.get("skill_id") and int(rec["skill_id"]) not in out:
                out[int(rec["skill_id"])] = sid
    return out


def load_aidb_race() -> dict[int, str]:
    from fetch_aidb_race import load_aidb_race as _load

    return _load()


def build_aidb_stem_index(skills_xml: str, aidb_by_id: dict[int, str]) -> dict[tuple[str, str], str]:
    """(skill_group, name_stem) -> race. Light/Dark variants share a group, not a stem."""
    by_stem: dict[tuple[str, str], str] = {}
    for m in SKILL_RE.finditer(skills_xml):
        cid = int(m.group(1))
        race = aidb_by_id.get(cid)
        if not race:
            continue
        name = m.group(2)
        fields = dict(FIELD_RE.findall(m.group(3)))
        by_stem[(group_name(name, fields), name_stem(name))] = race
    return by_stem


def lookup_aidb_race(
    cid: int,
    name: str,
    group: str,
    aidb_by_id: dict[int, str],
    aidb_by_stem: dict[tuple[str, str], str],
) -> str | None:
    if cid in aidb_by_id:
        return aidb_by_id[cid]
    hit = aidb_by_stem.get((group, name_stem(name)))
    if hit:
        return hit
    matches = {r for (g, st), r in aidb_by_stem.items() if g == group and name.startswith(st)}
    if len(matches) == 1:
        return next(iter(matches))
    return None


def resolve_aidb_race(
    cid: int,
    name: str,
    group: str,
    origin_race: str | None,
    stigma_disp: str,
    aidb_by_id: dict[int, str],
    aidb_by_stem: dict[tuple[str, str], str],
) -> str | None:
    aidb = lookup_aidb_race(cid, name, group, aidb_by_id, aidb_by_stem)
    if stigma_disp in ("1", "2"):
        return aidb or origin_race or stigma_race_from_name(name, group, None, stigma_disp)
    return aidb


def decode_learns(xml: str) -> list[dict[str, str]]:
    out = []
    for body in LEARN_RE.findall(xml):
        out.append(dict(FIELD_RE.findall(body)))
    return out


def class_ids_for_learn(client_class: str) -> list[str]:
    if client_class == "ALL":
        return list(CLASS_IDS)
    if client_class in CLIENT_TO_ID:
        return [CLIENT_TO_ID[client_class]]
    if client_class in BASE_TO_SPECS:
        return list(BASE_TO_SPECS[client_class])
    return []


def group_name(name: str, fields: dict[str, str]) -> str:
    g = (fields.get("skill_group_name") or "").strip()
    if g:
        return g
    return G_TAIL.sub("", name)


def skill_rank(name: str) -> int:
    m = G_TAIL.search(name)
    return int(m.group(1)) if m else 1


def parse_race(raw: str | None) -> str | None:
    return RACE_MAP.get((raw or "all").lower(), None)


def stigma_race_from_name(name: str, group: str, race: str | None, stigma_disp: str) -> str | None:
    """Stigmas stay race-locked even when skill_learns says All (Origin exception is learned-only)."""
    if race:
        return race
    if stigma_disp not in ("1", "2"):
        return None
    blob = f"{name} {group}".lower()
    if any(x in blob for x in ("_light_", "light_", "sunburst", "novaburst", "_elyos", "elyos", "angelic")):
        return "elyos"
    if any(x in blob for x in ("_dark_", "dark_", "moonburst", "demonicburst", "_asmo", "asmo", "demonic")):
        return "asmo"
    return None


def to_camel(group: str) -> str:
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", group) if p]
    if not parts:
        return "skill"
    head = parts[0]
    rest = parts[1:]
    if len(head) <= 3 and head.isupper():
        head = head.lower()
    else:
        head = head[:1].lower() + head[1:]
    return head + "".join(p[:1].upper() + p[1:] for p in rest)


def unique_id(base: str, used: set[str], extra: str | None = None) -> str:
    cand = base
    if extra:
        cand = base + extra
    if cand[0].isdigit():
        cand = "s" + cand
    if cand not in used:
        return cand
    n = 2
    while f"{cand}{n}" in used:
        n += 1
    return f"{cand}{n}"


def infer_kind(fields: dict[str, str], stigma: bool, old: str | None) -> str:
    if old:
        return old
    if stigma:
        return "stigma"
    sub = (fields.get("sub_type") or "").lower()
    act = (fields.get("activation_attribute") or "").lower()
    if act in ("toggle", "maintain"):
        return "buff"
    if sub == "buff":
        return "buff"
    if sub == "heal":
        return "utility"
    if sub in ("summon", "summontrap", "summonhoming", "chant"):
        return "combat"
    return "combat"


def cd_from_fields(fields: dict[str, str]) -> str:
    raw = fields.get("delay_time") or "0"
    try:
        ms = int(raw)
    except ValueError:
        return "нет"
    if ms <= 0:
        return "мгновенно"
    return fmt_sec(ms)


def range_tag(fields: dict[str, str], stats: dict | None) -> str:
    if stats and stats.get("range_m"):
        return f"{stats['range_m']} м"
    dist = fields.get("first_target_valid_distance") or "0"
    try:
        n = int(dist)
    except ValueError:
        n = 0
    first = (fields.get("first_target") or "").lower()
    if first in ("me", "") or n <= 1:
        if first in ("me",):
            return "на себя"
        return "ближний"
    return f"{n} м"


def strip_rank(name: str) -> str:
    return RANK_TAIL.sub("", name).strip() or name


def skill_desc(
    body: str,
    fields: dict[str, str],
    strings: dict[str, str],
    by_name: dict[str, str],
    stats: dict | None,
) -> str:
    filled = fill_client_desc(body, strings, by_name)
    if filled and "?" not in filled:
        return with_stats(filled, stats)
    key = fields.get("desc_long") or fields.get("desc") or ""
    raw = strings.get(key) or ""
    raw = re.sub(r"\[%[^%\]]+%?\]", "", raw)
    raw = re.sub(r" +", " ", raw).replace("%%", "%").strip()
    if not raw:
        short = strings.get(fields.get("desc") or "") or ""
        raw = strip_rank(short) or fields.get("name") or ""
    return with_stats(raw, stats)


def is_chain_follow(
    planner_id: str,
    fields: dict[str, str],
    stigma: bool,
    desc: str,
    reserved: set[str],
) -> bool:
    if planner_id in ASSASSIN_CHAIN_FOLLOW:
        return True
    if planner_id in reserved or stigma:
        return False
    pre = fields.get("prechain_category_name") or fields.get("prechain_skillname")
    if not pre:
        return False
    if (fields.get("sub_type") or "").lower() != "attack":
        return False
    return "2-е умение" in desc or "2-e умение" in desc


def parse_skills_xml(xml: str) -> dict[str, tuple[int, str, dict[str, str]]]:
    """name -> (id, body, fields). Last rank wins if duplicated names."""
    out: dict[str, tuple[int, str, dict[str, str]]] = {}
    for m in SKILL_RE.finditer(xml):
        sid = int(m.group(1))
        name = m.group(2)
        body = m.group(3)
        fields = dict(FIELD_RE.findall(body))
        out[name] = (sid, body, fields)
    return out


_GRAY_PAD = 130
_GRAY_TOL = 8


def skill_icon_content_bbox(im):
    """Art bbox, ignoring transparent pixels and flat gray DDS padding."""
    px = im.load()
    w, h = im.size
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a <= 8:
                continue
            if (
                abs(r - _GRAY_PAD) < _GRAY_TOL
                and abs(g - _GRAY_PAD) < _GRAY_TOL
                and abs(b - _GRAY_PAD) < _GRAY_TOL
            ):
                continue
            if x < minx:
                minx = x
            if y < miny:
                miny = y
            if x > maxx:
                maxx = x
            if y > maxy:
                maxy = y
    if maxx < 0:
        return None
    return (minx, miny, maxx + 1, maxy + 1)


def crop_skill_icon(im):
    """Export native skill-icon pixels. Do not nearest-scale a padded canvas.

    Origin 4.6 skills.pak DDS are 64×64. Every planner class skill is 40×40 art
    in the top-left (padding is usually alpha; a few files use opaque gray).
    `*_64.dds` exists for ~122 proc/event/generic textures, not a 64/128 class
    pack. Codex/aidb icons are the same 40×40 art.
    """
    im = im.convert("RGBA")
    w, h = im.size
    if w == 40 and h == 40:
        return im
    box = skill_icon_content_bbox(im)
    if box is None:
        box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if box:
        bw, bh = box[2] - box[0], box[3] - box[1]
        if box[0] <= 2 and box[1] <= 2 and bw <= 48 and bh <= 48:
            if w >= 40 and h >= 40:
                return im.crop((0, 0, 40, 40))
            return im.crop(box)
        return im.crop(box) if (bw, bh) != (w, h) else im
    if w >= 40 and h >= 40:
        return im.crop((0, 0, 40, 40))
    return im


def _icon_zip_member(icon_name: str, zip_names: dict[str, str]) -> str | None:
    key = icon_name.lower()
    member = zip_names.get(key)
    if not member:
        member = zip_names.get(key.replace(".dds", "") + ".dds")
    return member


def copy_icon(icon_name: str, dest: Path, zip_names: dict[str, str], zf) -> bool:
    member = _icon_zip_member(icon_name, zip_names)
    if not member:
        return dest.exists() and dest.stat().st_size > 200
    stem = member[:-4] if member.lower().endswith(".dds") else member
    member64 = zip_names.get(stem.lower() + "_64.dds")
    try:
        from PIL import Image

        im = Image.open(BytesIO(zf.read(member))).convert("RGBA")
        if member64:
            im64 = Image.open(BytesIO(zf.read(member64))).convert("RGBA")
            b0 = skill_icon_content_bbox(im)
            b1 = skill_icon_content_bbox(im64)
            a0 = 0 if not b0 else (b0[2] - b0[0]) * (b0[3] - b0[1])
            a1 = 0 if not b1 else (b1[2] - b1[0]) * (b1[3] - b1[1])
            if a1 > a0:
                im = im64
        dest.parent.mkdir(parents=True, exist_ok=True)
        crop_skill_icon(im).save(dest, "PNG")
        return True
    except Exception as e:
        print("icon fail", icon_name, e)
        return False


def name_stem(name: str) -> str:
    return G_TAIL.sub("", name)


def collect_max_rank(
    learns: list[dict],
    meta: dict,
    id_by_client: dict[int, str],
    aidb_by_id: dict[int, str],
    aidb_by_stem: dict[tuple[str, str], str],
) -> dict[tuple, dict]:
    """(group, name_stem, race) -> highest G rank. Stem keeps ShadowHide vs WindWalk apart."""
    best: dict[tuple, dict] = {}
    for rec in learns:
        cls_ids = class_ids_for_learn(rec.get("class") or "")
        if not cls_ids:
            continue
        name = rec.get("skill") or ""
        if not name or name.startswith(SKIP_PREFIX):
            continue
        if name not in meta:
            continue
        cid, body, fields = meta[name]
        act = (fields.get("activation_attribute") or "").lower()
        if act in SKIP_ACT:
            continue
        if rec.get("ui_display") in ("0",):
            continue
        group = group_name(name, fields)
        stigma_disp = rec.get("stigma_display") or "0"
        race = resolve_aidb_race(
            cid,
            name,
            group,
            parse_race(rec.get("race")),
            stigma_disp,
            aidb_by_id,
            aidb_by_stem,
        )
        stem = name_stem(name)
        key = (group, stem, race or "all")
        rank = skill_rank(name)
        planner_id = id_by_client.get(cid)
        prev = best.get(key)
        if prev and rank < prev["rank"]:
            prev["classes"].update(cls_ids)
            if planner_id and not prev.get("planner_id"):
                prev["planner_id"] = planner_id
            continue
        classes = set(cls_ids)
        if prev:
            classes |= prev["classes"]
            planner_id = planner_id or prev.get("planner_id")
        if prev and rank == prev["rank"]:
            prev["classes"] |= classes
            if planner_id:
                prev["planner_id"] = planner_id
            if stigma_disp in ("1", "2"):
                prev["stigma_display"] = stigma_disp
            continue
        best[key] = {
            "rank": rank,
            "name": name,
            "client_id": cid,
            "body": body,
            "fields": fields,
            "classes": classes,
            "race": race,
            "stigma_display": stigma_disp,
            "group": group,
            "stem": stem,
            "planner_id": planner_id,
        }
    return best


def assign_ids(best: dict, id_by_client: dict[int, str]) -> dict[str, dict]:
    used = set(EXTRA) | set(ASSASSIN_CHAIN_FOLLOW)
    # reserve existing assassin ids first
    reserved = set(id_by_client.values()) | used
    out: dict[str, dict] = {}
    # two-pass: known client ids, then generated
    items = sorted(best.values(), key=lambda r: (r["group"], r.get("stem") or "", r["race"] or "", r["client_id"]))
    pending = []
    for rec in items:
        sid = rec.get("planner_id") or id_by_client.get(rec["client_id"])
        if sid:
            if sid in out:
                # Light/Dark slayer-style split already unique
                pending.append(rec)
                continue
            rec = dict(rec)
            rec["id"] = sid
            out[sid] = rec
            used.add(sid)
        else:
            pending.append(rec)
    for rec in pending:
        rec = dict(rec)
        base = to_camel(rec["group"])
        extra = None
        if rec["race"] == "elyos":
            extra = "Elyos"
        elif rec["race"] == "asmo":
            extra = "Asmo"
        sid = unique_id(base, used, extra)
        rec["id"] = sid
        out[sid] = rec
        used.add(sid)
    return out


def build_skill_objects(
    assigned: dict[str, dict],
    strings: dict[str, str],
    by_name: dict[str, str],
    old_kinds: dict[str, str],
    reserved_binds: set[str],
) -> tuple[dict, dict, dict, dict, set[str]]:
    skills = {}
    stigma_tier = {}
    skill_race = {}
    skill_class = {}
    chain_follow = set(ASSASSIN_CHAIN_FOLLOW)
    catalog = {}

    for sid, rec in assigned.items():
        fields = rec["fields"]
        stats = parse_block(rec["body"])
        stats["skill_id"] = rec["client_id"]
        name_key = fields.get("desc") or ""
        ru = strip_rank(strings.get(name_key) or rec["name"])
        desc = skill_desc(rec["body"], fields, strings, by_name, stats)
        stigma = rec["stigma_display"] in ("1", "2")
        kind = infer_kind(fields, stigma, old_kinds.get(sid))
        cd = cd_from_fields(fields)
        tags = [range_tag(fields, stats)]
        if cd and cd not in ("нет", "мгновенно"):
            tags.append(f"КД {cd}")
        for cc in stats.get("cc") or []:
            tag = cc["name"].capitalize() if cc["name"] != "стан" else "Стан"
            if tag not in tags:
                tags.append(tag)
        tags = with_mag_status_tag(tags, stats)
        follow = is_chain_follow(sid, fields, stigma, desc, reserved_binds)
        if follow:
            chain_follow.add(sid)
        skills[sid] = {
            "name": ru,
            "kind": kind,
            "tags": tags,
            "desc": desc,
            "cd": cd,
            "icon": fields.get("skillicon_name") or "",
            "client_id": rec["client_id"],
            "group": rec["group"],
        }
        if stigma:
            stigma_tier[sid] = "greater" if rec["stigma_display"] == "2" else "normal"
        if rec["race"]:
            skill_race[sid] = rec["race"]
        skill_class[sid] = sorted(rec["classes"])
        catalog[sid] = {
            "client_id": rec["client_id"],
            "client_name": rec["name"],
            "group": rec["group"],
            "classes": skill_class[sid],
            "race": rec["race"],
            "stigma": stigma_tier.get(sid),
            "chain_follow": follow,
            "activation": fields.get("activation_attribute"),
            "icon": fields.get("skillicon_name"),
        }
    return skills, stigma_tier, skill_race, skill_class, chain_follow, catalog


def write_skills_js(
    skills: dict,
    stigma_tier: dict,
    skill_race: dict,
    skill_class: dict,
    chain_follow: set[str],
) -> None:
    # extras first, then the rest alphabetically but keep extras order
    lines = ["const SKILLS = {"]
    extra_ids = list(EXTRA)
    rest = [s for s in skills if s not in extra_ids]
    rest.sort(key=lambda s: (skills[s]["name"], s))
    for sid in extra_ids + rest:
        s = skills[sid]
        tags = ", ".join(js_str(t) for t in s["tags"])
        lines.append(f"  {sid}: {{")
        lines.append(f"    name: {js_str(s['name'])},")
        lines.append(f"    kind: {js_str(s['kind'])},")
        lines.append(f"    tags: [{tags}],")
        lines.append(f"    desc: {js_str(s['desc'])},")
        lines.append(f"    cd: {js_str(s['cd'])},")
        lines.append("  },")
    lines.append("};")
    lines.append("")
    lines.append("const STIGMA_TIER = {")
    for sid, tier in sorted(stigma_tier.items()):
        lines.append(f"  {sid}: {js_str(tier)},")
    lines.append("};")
    lines.append("")
    lines.append("const SKILL_RACE = {")
    for sid, race in sorted(skill_race.items()):
        lines.append(f"  {sid}: {js_str(race)},")
    lines.append("};")
    lines.append("")
    lines.append("const SKILL_CLASS = {")
    for sid, cls in sorted(skill_class.items()):
        arr = ", ".join(js_str(c) for c in cls)
        lines.append(f"  {sid}: [{arr}],")
    lines.append("};")
    lines.append("")
    follow = ", ".join(js_str(s) for s in sorted(chain_follow))
    lines.append(f"const CHAIN_FOLLOW = new Set([{follow}]);")
    lines.append("")
    basic = ", ".join(js_str(s) for s in BASIC_IDS)
    lines.append(f"const BASIC_SKILLS = new Set([{basic}]);")
    lines.append("")
    OUT_JS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def delay_ms(fields: dict[str, str]) -> int:
    try:
        return int(fields.get("delay_time") or 0)
    except ValueError:
        return 0


def is_self_buff(fields: dict[str, str], kind: str) -> bool:
    if kind != "buff":
        return False
    first = (fields.get("first_target") or "").lower()
    return first in ("me", "")


def generate_class_defaults(assigned: dict[str, dict], skills: dict, chain_follow: set[str]) -> dict:
    """Heuristic layouts for non-assassin classes. Assassin stays hand-authored."""
    by_class: dict[str, list[str]] = defaultdict(list)
    for sid, rec in assigned.items():
        if sid in chain_follow:
            continue
        for cid in rec["classes"]:
            by_class[cid].append(sid)

    out = {}
    for cid in CLASS_IDS:
        if cid == "assassin":
            continue
        ids = by_class[cid]
        # stable: name then id
        ids.sort(key=lambda s: (skills[s]["name"], s))
        combat: dict[str, str] = {}
        shift: dict[str, str] = {}
        ctrl = dict(CTRL_POTIONS)
        racial = {"elyos": [], "asmo": []}

        buffs = []
        attacks = []
        utils = []
        racial_skills = {"elyos": [], "asmo": []}
        for sid in ids:
            rec = assigned[sid]
            if rec["stigma_display"] in ("1", "2"):
                continue
            race = rec["race"]
            fields = rec["fields"]
            kind = skills[sid]["kind"]
            name = skills[sid]["name"]
            if race:
                racial_skills[race].append(sid)
                continue
            if "возвращен" in name.lower() or delay_ms(fields) >= 1_200_000:
                utils.append(sid)
                continue
            if is_self_buff(fields, kind) and delay_ms(fields) >= 20_000:
                buffs.append(sid)
            elif kind in ("combat", "stigma") or (fields.get("sub_type") or "").lower() in (
                "attack",
                "debuff",
            ):
                attacks.append(sid)
            else:
                utils.append(sid)

        for key, sid in zip(BUFF_KEYS, buffs):
            combat[key] = sid
        leftover_buffs = buffs[len(BUFF_KEYS) :]
        for key, sid in zip(COMBAT_KEYS, attacks):
            combat[key] = sid
        leftover_atk = attacks[len(COMBAT_KEYS) :]
        shift_i = 0
        for sid in leftover_atk + leftover_buffs:
            if shift_i >= len(SHIFT_KEYS):
                break
            shift[SHIFT_KEYS[shift_i]] = sid
            shift_i += 1
        if utils:
            combat.setdefault("F8", utils[0])

        def place_racial(race: str) -> list[dict]:
            rows = []
            keys_left = [k for k in COMBAT_KEYS if k not in combat]
            keys_left += [k for k in ("KeyX", "KeyC", "KeyQ") if k not in combat]
            for i, sid in enumerate(racial_skills[race][:3]):
                if i >= len(keys_left):
                    break
                key = keys_left[i]
                layer = "shift" if key in shift or key not in COMBAT_KEYS else "combat"
                if key in combat and layer == "combat":
                    layer = "shift"
                rows.append({"layer": layer, "key": key, "skill": sid})
            return rows

        racial["elyos"] = place_racial("elyos")
        racial["asmo"] = place_racial("asmo")
        out[cid] = {
            "learned": {"combat": combat, "shift": shift, "ctrl": ctrl},
            "racial": racial,
            "stigma": {},
            "defaultStigmas": {"normal": [], "greater": []},
        }
    return out


def write_class_defaults(defaults: dict) -> None:
    lines = ["const CLASSES = ["]
    for c in CLASSES:
        lines.append(
            f"  {{ id: {js_str(c['id'])}, name: {js_str(c['name'])}, client: {js_str(c['client'])} }},"
        )
    lines.append("];")
    lines.append("")
    lines.append("const CLASS_DEFAULTS = {")
    for cid, layout in defaults.items():
        lines.append(f"  {cid}: {{")
        lines.append("    learned: {")
        for layer in ("combat", "shift", "ctrl"):
            pairs = ", ".join(
                f"{k}: {js_str(v)}" for k, v in layout["learned"][layer].items()
            )
            lines.append(f"      {layer}: {{{pairs}}},")
        lines.append("    },")
        lines.append("    racial: {")
        for race in ("elyos", "asmo"):
            rows = layout["racial"][race]
            inner = ", ".join(
                "{ layer: %s, key: %s, skill: %s }"
                % (js_str(r["layer"]), js_str(r["key"]), js_str(r["skill"]))
                for r in rows
            )
            lines.append(f"      {race}: [{inner}],")
        lines.append("    },")
        lines.append("    stigma: {},")
        lines.append('    defaultStigmas: { normal: [], greater: [] },')
        lines.append("  },")
    lines.append("};")
    lines.append("")
    OUT_DEFAULTS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def catalog_race_for(
    rec: dict,
    aidb_by_id: dict[int, str],
    aidb_by_stem: dict[tuple[str, str], str],
) -> str | None:
    cid = int(rec["client_id"]) if rec.get("client_id") else 0
    name = rec.get("client_name") or ""
    group = rec.get("group") or ""
    aidb = lookup_aidb_race(cid, name, group, aidb_by_id, aidb_by_stem)
    if rec.get("stigma"):
        return aidb or rec.get("race")
    return aidb


def replace_skill_race_js(skill_race: dict[str, str]) -> None:
    text = OUT_JS.read_text(encoding="utf-8")
    block = ["const SKILL_RACE = {"]
    for sid, race in sorted(skill_race.items()):
        block.append(f"  {sid}: {js_str(race)},")
    block.append("};")
    new_text, n = re.subn(
        r"const SKILL_RACE = \{.*?\n\};",
        "\n".join(block),
        text,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise SystemExit(f"SKILL_RACE replace failed: {n}")
    OUT_JS.write_text(new_text, encoding="utf-8")


def update_race_only() -> None:
    """Rebuild SKILL_RACE from aidb without rewriting skill ids/icons."""
    aidb_by_id = load_aidb_race()
    skills_xml = client_xml_text()
    aidb_by_stem = build_aidb_stem_index(skills_xml, aidb_by_id)
    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    skill_race: dict[str, str] = {}
    learned = stigma = 0
    for sid, rec in cat["skills"].items():
        race = catalog_race_for(rec, aidb_by_id, aidb_by_stem)
        rec["race"] = race
        if race:
            skill_race[sid] = race
            if rec.get("stigma"):
                stigma += 1
            else:
                learned += 1
    replace_skill_race_js(skill_race)
    CATALOG_PATH.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "SKILL_RACE",
        len(skill_race),
        "learned",
        learned,
        "stigma",
        stigma,
        "aidb ids",
        len(aidb_by_id),
    )


def main() -> None:
    print("loading client xml…")
    skills_xml = client_xml_text()
    import zipfile

    with zipfile.ZipFile(SKILLS_ZIP) as z:
        learns_raw = z.read("client_skill_learns.xml")
        zip_names = {n.lower(): n for n in z.namelist() if n.lower().endswith(".dds")}
        learns_xml = (
            learns_raw.decode("utf-16")
            if learns_raw[:2] in (b"\xff\xfe", b"\xfe\xff")
            else learns_raw.decode("utf-8")
        )
        print("parsing learns + skills…")
        learns = decode_learns(learns_xml)
        meta = parse_skills_xml(skills_xml)
        strings = load_strings()
        by_name = {name: body for name, (_cid, body, _f) in meta.items()}
        old_kinds = load_old_kinds()
        id_by_client = load_id_by_client()
        reserved_binds = set(id_by_client.values())
        aidb_by_id = load_aidb_race()
        aidb_by_stem = build_aidb_stem_index(skills_xml, aidb_by_id)
        print("aidb racial ids", len(aidb_by_id), "stems", len(aidb_by_stem))
        best = collect_max_rank(learns, meta, id_by_client, aidb_by_id, aidb_by_stem)
        print("max-rank groups", len(best))
        assigned = assign_ids(best, id_by_client)
        print("assigned ids", len(assigned))
        skills, stigma_tier, skill_race, skill_class, chain_follow, catalog = build_skill_objects(
            assigned, strings, by_name, old_kinds, reserved_binds
        )
        for sid, item in EXTRA.items():
            skills.setdefault(sid, dict(item))
        print("writing icons…")
        ICON_DIR.mkdir(parents=True, exist_ok=True)
        ok = 0
        miss = 0
        for sid, rec in assigned.items():
            icon = rec["fields"].get("skillicon_name") or ""
            if not icon:
                miss += 1
                continue
            if copy_icon(icon, ICON_DIR / f"{sid}.png", zip_names, z):
                ok += 1
            else:
                miss += 1
                print("NO ICON", sid, icon)
        print("icons ok", ok, "miss", miss)

    write_skills_js(skills, stigma_tier, skill_race, skill_class, chain_follow)
    defaults = generate_class_defaults(assigned, skills, chain_follow)
    write_class_defaults(defaults)
    CATALOG_PATH.write_text(
        json.dumps(
            {
                "classes": CLASSES,
                "skills": catalog,
                "chain_follow": sorted(chain_follow),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        "wrote",
        OUT_JS,
        "skills",
        len(skills),
        "stigmas",
        len(stigma_tier),
        "chain",
        len(chain_follow),
        "defaults",
        list(defaults),
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--race-only" in sys.argv:
        update_race_only()
    else:
        main()
