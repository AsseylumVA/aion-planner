"""Read base combat stats from client_skills.xml by skill id."""
from __future__ import annotations

import json
import re
import zipfile
from hashlib import pbkdf2_hmac
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETAILS_PATH = ROOT / "tools" / "aidb_details.json"
STATS_PATH = ROOT / "tools" / "client_skill_stats.json"
SKILLS_JS = ROOT / "js" / "skills.js"
SKILLS_ZIP = ROOT / "tools" / "encdec" / "unpack" / "skills_dec.zip"
SKILLS_PAK = Path(r"D:\OriginAion\Data\skills\skills.pak")
STRINGS_PATH = Path(r"D:\OriginAion\L10N\2_plk\data\Strings\client_strings_skill.xml")
PASSWORD = b"kqsudze752eiaqvzy523dhsfsjyfphlb08g347"

BLOCK_RE = re.compile(
    r"<skill_base_client>\s*<id>(\d+)</id>(.*?)</skill_base_client>",
    re.S,
)
FIELD_RE = re.compile(r"<([^>]+)>([^<]*)</")
EFFECT_RE = re.compile(r"^effect(\d+)_(.+)$")
STAT_TAIL_RE = re.compile(
    r"(?: Базовая точность(?: магии)? \+\d+\.| Урон в PvP \d+%\.| Шанс [^.]+\."
    r"| (?:Стан|Опрокидывание|Ошеломление|Вращение|Немота|Оковы|Воздушные оковы"
    r"|Притягивание|Замедление|Ослепление|Сон|Паралич|Страх)(?:, [^.]*)?\.)+$"
)

CC_TYPES = {
    "stun": ("стан", "стана"),
    "stumble": ("опрокидывание", "опрокидывания"),
    "stagger": ("ошеломление", "ошеломления"),
    "spin": ("вращение", "вращения"),
    "silence": ("немота", "немоты"),
    "bind": ("оковы", "оков"),
    "simpleroot": ("оковы", "оков"),
    "openaerial": ("воздушные оковы", "воздушных оков"),
    "pulled": ("притягивание", "притягивания"),
    "snare": ("замедление", "замедления"),
    "blind": ("ослепление", "ослепления"),
    "root": ("оковы", "оков"),
    "sleep": ("сон", "сна"),
    "paralyze": ("паралич", "паралича"),
    "fear": ("страх", "страха"),
}

# EffectTemplate.isMagicalEffectTemp(): these always roll mag acc / mag resist,
# even when the skill <type> is Physical (sin/ranger/chanter stuns, poisons…).
MAGICAL_EFFECT_TYPES = {
    "silence",
    "sleep",
    "root",
    "snare",
    "stun",
    "poison",
    "bind",
    "bleed",
    "blind",
    "deboostheal",
    "paralyze",
    "slow",
}

MAG_STATUS_TAG = "Маг. статус"
# Physical tooltips in this client/aidb are reserved4 + 16 ~ +20 (same pad as Dash, Massacre, etc.)
PHYS_TOOLTIP_PAD = 16
PLACEHOLDER_RE = re.compile(r"\[%([^%\]]+)%?\]")
STRING_RE = re.compile(r"<name>(STR_SKILL_[^<]+)</name>\s*<body>(.*?)</body>", re.S)
STAT_RU = {
    "MagicalHitAccuracy": "Точн. магии",
    "MagicalResist": "Маг. защита",
    "ElementalDefendAll": "Защ. от стихий",
    "Dodge": "Уклонение",
    "Speed": "Скорость",
}
KNOWN_ATTRS = {
    "MinDamage",
    "MaxDamage",
    "RemainTime",
    "AddDamage",
    "AddEffect",
    "SignetGrade",
    "StatName",
    "Value",
    "FixDamage",
    "ConditionProb",
    "Damage",
    "OtherSkill",
}


def decrypt_pak(path: Path) -> bytes:
    pak = path.read_bytes()
    if pak[:8] != b"OADTENC1":
        raise ValueError(f"not OADTENC1: {path}")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt, nonce, tag, ct = pak[8:24], pak[0x18:0x24], pak[0x24:0x34], pak[0x34:]
    key = pbkdf2_hmac("sha256", PASSWORD, salt, 100000, dklen=32)
    return AESGCM(key).decrypt(nonce, ct + tag, None)


def client_xml_text() -> str:
    if SKILLS_ZIP.exists() and SKILLS_ZIP.stat().st_size > 1000:
        with zipfile.ZipFile(SKILLS_ZIP) as z:
            raw = z.read("client_skills.xml")
    else:
        pt = decrypt_pak(SKILLS_PAK)
        SKILLS_ZIP.parent.mkdir(parents=True, exist_ok=True)
        SKILLS_ZIP.write_bytes(pt)
        with zipfile.ZipFile(SKILLS_ZIP) as z:
            raw = z.read("client_skills.xml")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


def fmt_sec(ms: int) -> str:
    s = ms / 1000
    if s == int(s):
        return f"{int(s)} с"
    return f"{s:g} с".replace(".", ",")


def parse_cc(body: str) -> list[dict]:
    out = []
    for i, e in sorted(parse_effects(body).items()):
        kind = CC_TYPES.get((e.get("type") or "").lower())
        if not kind:
            continue
        chance = None
        if "cond_preeffect_prob2" in e or "cond_preeffect" in e:
            p1 = int(e.get("cond_preeffect_prob1") or 0)
            p2 = int(e.get("cond_preeffect_prob2") or 100)
            chance = p2 + p1
        dur = None
        if "remain2" in e:
            dur = int(e.get("remain2") or 0) + int(e.get("remain1") or 0)
        if chance is None and dur is None:
            continue
        item = {"name": kind[0], "name_of": kind[1]}
        if chance is not None:
            item["chance"] = chance
        if dur:
            item["duration_ms"] = dur
        out.append(item)
    return out


def parse_effects(body: str) -> dict[int, dict[str, str]]:
    effects: dict[int, dict[str, str]] = {}
    for name, val in FIELD_RE.findall(body):
        m = EFFECT_RE.match(name)
        if not m:
            continue
        effects.setdefault(int(m.group(1)), {})[m.group(2)] = val
    return effects


def effect_uses_magic_acc(effect_type: str) -> bool:
    return (effect_type or "").lower() in MAGICAL_EFFECT_TYPES


def effect_acc(e: dict[str, str]) -> int:
    return int(e.get("acc_mod2") or 0) + int(e.get("acc_mod1") or 0)


def parse_block(body: str) -> dict:
    skill_type = None
    pvp = None
    dist = None
    for name, val in FIELD_RE.findall(body):
        if name == "type" and skill_type is None:
            skill_type = val
        elif name == "pvp_damage_ratio" and val and val != "100":
            pvp = int(val)
        elif name == "first_target_valid_distance" and val:
            dist = int(val)
    skill_is_magic = (skill_type or "").lower() == "magical"
    acc_phys = 0
    acc_magic = 0
    has_mag_status = False
    for e in parse_effects(body).values():
        et = e.get("type") or ""
        if effect_uses_magic_acc(et):
            has_mag_status = True
        acc = effect_acc(e)
        if not acc:
            continue
        # acc_mod lives on the effect. Stun/poison/… always vs mag resist;
        # damage on a Magical skill too; otherwise physical dodge.
        if skill_is_magic or effect_uses_magic_acc(et):
            acc_magic = max(acc_magic, acc)
        else:
            acc_phys = max(acc_phys, acc)
    out = {}
    if acc_phys:
        out["acc_phys"] = acc_phys
    if acc_magic:
        out["acc_magic"] = acc_magic
    if acc_phys or acc_magic:
        out["type"] = skill_type or ""
    if has_mag_status and not skill_is_magic:
        out["mag_status"] = True
        if "type" not in out:
            out["type"] = skill_type or ""
    if pvp:
        out["pvp"] = pvp
    if dist and dist > 1:
        out["range_m"] = dist
    cc = parse_cc(body)
    if cc:
        out["cc"] = cc
    return out


def load_cached_stats() -> dict[str, dict]:
    if STATS_PATH.exists():
        return json.loads(STATS_PATH.read_text(encoding="utf-8"))
    return {}


def planner_ids() -> dict[str, int]:
    catalog = ROOT / "tools" / "client_skill_catalog.json"
    if catalog.exists():
        data = json.loads(catalog.read_text(encoding="utf-8"))
        out = {
            sid: int(rec["client_id"])
            for sid, rec in (data.get("skills") or {}).items()
            if rec.get("client_id")
        }
        if out:
            return out
    details = json.loads(DETAILS_PATH.read_text(encoding="utf-8"))
    return {sid: int(rec["skill_id"]) for sid, rec in details.items() if rec.get("skill_id")}


def collect(xml: str | None = None) -> dict[str, dict]:
    xml = xml or client_xml_text()
    blocks = {int(i): body for i, body in BLOCK_RE.findall(xml)}
    out = {}
    for sid, cid in planner_ids().items():
        body = blocks.get(cid)
        if not body:
            continue
        stats = parse_block(body)
        if stats:
            stats["skill_id"] = cid
            out[sid] = stats
    return out


def format_stats(stats: dict) -> str:
    parts = []
    if stats.get("acc_phys"):
        parts.append(f"Базовая точность +{stats['acc_phys']}.")
    if stats.get("acc_magic"):
        parts.append(f"Базовая точность магии +{stats['acc_magic']}.")
    if stats.get("pvp"):
        parts.append(f"Урон в PvP {stats['pvp']}%.")
    for cc in stats.get("cc") or []:
        bit = f"Шанс {cc['name_of']} {cc['chance']}%" if "chance" in cc else cc["name"].capitalize()
        if cc.get("duration_ms"):
            bit += f", {fmt_sec(cc['duration_ms'])}"
        parts.append(bit + ".")
    return " ".join(parts)


def with_stats(desc: str, stats: dict | None) -> str:
    desc = STAT_TAIL_RE.sub("", (desc or "").rstrip())
    extra = format_stats(stats or {})
    if not extra:
        return desc
    if desc and desc[-1] not in ".!?":
        desc += "."
    return f"{desc} {extra}".strip()


def with_mag_status_tag(tags: list[str], stats: dict | None) -> list[str]:
    tags = [t for t in tags if t != MAG_STATUS_TAG]
    if stats and stats.get("range_m"):
        rng = f"{stats['range_m']} м"
        if tags and (tags[0] == "ближний" or re.fullmatch(r"\d+ м", tags[0])):
            tags = [rng, *tags[1:]]
        elif rng not in tags:
            tags = [rng, *tags]
    if stats and stats.get("mag_status"):
        tags.append(MAG_STATUS_TAG)
    return tags


def load_skill_strings() -> dict[str, str]:
    raw = STRINGS_PATH.read_bytes()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")
    out = {}
    for name, body in STRING_RE.findall(text):
        out[name] = " ".join(body.split())
    return out


def parse_skill_meta(body: str) -> tuple[dict[str, str], dict[int, dict[str, str]]]:
    fields: dict[str, str] = {}
    for name, val in FIELD_RE.findall(body):
        if name not in fields:
            fields[name] = val
    return fields, parse_effects(body)


def skill_name_index(blocks: dict[int, str]) -> dict[str, str]:
    out = {}
    for body in blocks.values():
        m = re.search(r"<name>([^<]+)</name>", body)
        if m:
            out[m.group(1)] = body
    return out


def phys_damage(e: dict[str, str]) -> tuple[int, int]:
    r4 = int(e.get("reserved4") or 0)
    r3 = int(e.get("reserved3") or 0)
    if r4 == 100 and not r3:
        r4 = 0
    lo = r4 + PHYS_TOOLTIP_PAD
    return lo, lo + 4


def fmt_remain(ms: int | str) -> str:
    s = int(ms) / 1000
    if s == int(s):
        return f"{int(s)} сек."
    return f"{s:g} сек.".replace(".", ",")


def format_attr(attr: str, e: dict[str, str]) -> str:
    if attr in ("MinDamage", "MaxDamage"):
        lo, hi = phys_damage(e)
        return str(lo if attr == "MinDamage" else hi)
    if attr == "RemainTime":
        return fmt_remain(int(e.get("remain2") or 0))
    if attr == "AddDamage":
        return e.get("reserved10") or "?"
    if attr == "AddEffect":
        return e.get("reserved14") or "?"
    if attr == "SignetGrade":
        et = (e.get("type") or "").lower()
        if et == "signetburst":
            return e.get("reserved8") or "?"
        return e.get("reserved14") or e.get("reserved8") or "?"
    if attr == "StatName":
        raw = e.get("reserved13") or ""
        return STAT_RU.get(raw, raw or "?")
    if attr == "Value":
        return e.get("reserved2") or "?"
    if attr in ("FixDamage", "Damage"):
        return e.get("reserved2") or "?"
    if attr == "ConditionProb":
        return e.get("reserved_cond1_prob2") or "?"
    return "?"


def resolve_placeholder(
    token: str,
    fields: dict[str, str],
    effects: dict[int, dict[str, str]],
    by_name: dict[str, str],
) -> str:
    if token == "First_Target_Valid_Distance":
        return fields.get("first_target_valid_distance") or "?"
    ctx = effects
    parts = token.split(".")
    i = 0
    while i < len(parts):
        p = parts[i]
        if p.startswith("e") and p[1:].isdigit():
            e = ctx.get(int(p[1:])) or {}
            i += 1
            if i < len(parts) and parts[i] not in KNOWN_ATTRS:
                i += 1
            if i >= len(parts):
                return "?"
            attr = parts[i]
            if attr == "OtherSkill":
                proc = by_name.get(e.get("reserved17") or "")
                if not proc:
                    return "?"
                _, ctx = parse_skill_meta(proc)
                i += 1
                continue
            return format_attr(attr, e)
        i += 1
    return "?"


def fill_client_desc(body: str, strings: dict[str, str], by_name: dict[str, str]) -> str | None:
    fields, effects = parse_skill_meta(body)
    key = fields.get("desc_long") or fields.get("desc")
    tpl = strings.get(key or "")
    if not tpl or "[%" not in tpl:
        return None

    def repl(m: re.Match) -> str:
        return resolve_placeholder(m.group(1), fields, effects, by_name)

    text = PLACEHOLDER_RE.sub(repl, tpl).replace("%%", "%")
    text = re.sub(r" +", " ", text).strip()
    return text or None


_FILL_CACHE: dict[str, str] | None = None


def filled_descs() -> dict[str, str]:
    global _FILL_CACHE
    if _FILL_CACHE is not None:
        return _FILL_CACHE
    xml = client_xml_text()
    blocks = {int(i): body for i, body in BLOCK_RE.findall(xml)}
    strings = load_skill_strings()
    by_name = skill_name_index(blocks)
    out: dict[str, str] = {}
    for sid, cid in planner_ids().items():
        body = blocks.get(cid)
        if not body:
            continue
        filled = fill_client_desc(body, strings, by_name)
        if filled:
            out[sid] = filled
    _FILL_CACHE = out
    return out


def maybe_fill_desc(sid: str, desc: str) -> str:
    filled = filled_descs().get(sid)
    if not filled or "?" in filled:
        return desc
    base = STAT_TAIL_RE.sub("", (desc or "").rstrip())
    if "?" in base or sid in {"needle", "crush"}:
        return filled
    return desc


def apply_to_details(stats: dict[str, dict]) -> None:
    details = json.loads(DETAILS_PATH.read_text(encoding="utf-8"))
    for sid, rec in details.items():
        rec["desc"] = with_stats(maybe_fill_desc(sid, rec.get("desc") or ""), stats.get(sid))
        if stats.get(sid, {}).get("range_m") and rec.get("range") in ("ближний", None, ""):
            rec["range"] = f"{stats[sid]['range_m']} м"
        if sid in stats:
            rec["client_stats"] = {k: v for k, v in stats[sid].items() if k != "skill_id"}
        else:
            rec.pop("client_stats", None)
    DETAILS_PATH.write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_to_skills_js(stats: dict[str, dict]) -> int:
    text = SKILLS_JS.read_text(encoding="utf-8")
    n = 0
    pattern = re.compile(
        r'(  (\w+): \{\n    name: ".*?",\n    kind: ".*?",\n    tags: )(\[[^\]]*\])(,\n    desc: )("(?:\\.|[^"\\])*")(,\n    cd:)',
        re.S,
    )

    def block(m: re.Match) -> str:
        nonlocal n
        sid = m.group(2)
        tags = json.loads(m.group(3))
        desc = json.loads(m.group(5))
        st = stats.get(sid)
        new_tags = with_mag_status_tag(tags, st)
        new_desc = with_stats(maybe_fill_desc(sid, desc), st)
        if new_tags != tags or new_desc != desc:
            n += 1
        return (
            m.group(1)
            + json.dumps(new_tags, ensure_ascii=False)
            + m.group(4)
            + json.dumps(new_desc, ensure_ascii=False)
            + m.group(6)
        )

    SKILLS_JS.write_text(pattern.sub(block, text), encoding="utf-8")
    return n


def main() -> None:
    stats = collect()
    STATS_PATH.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    apply_to_details(stats)
    n = apply_to_skills_js(stats)
    print("skills with stats", len(stats), "js updated", n, "flash", stats.get("flash"))


if __name__ == "__main__":
    main()
