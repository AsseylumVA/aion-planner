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
NPCS_ZIP = ROOT / "tools" / "encdec" / "unpack" / "npcs_dec.zip"
NPCS_PAK = Path(r"D:\OriginAion\Data\Npcs\npcs.pak")
STRINGS_PATH = Path(r"D:\OriginAion\L10N\2_plk\data\Strings\client_strings_skill.xml")
PASSWORD = b"kqsudze752eiaqvzy523dhsfsjyfphlb08g347"

BLOCK_RE = re.compile(
    r"<skill_base_client>\s*<id>(\d+)</id>(.*?)</skill_base_client>",
    re.S,
)
FIELD_RE = re.compile(r"<([^>]+)>([^<]*)</")
EFFECT_RE = re.compile(r"^effect(\d+)_(.+)$")

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
_CC_CHANCE_NAMES = "|".join(
    sorted({genitive for _nom, genitive in CC_TYPES.values()}, key=len, reverse=True)
)
# Do not match chain-window sentences («Шанс открыть…» / «Шанс появления…»).
STAT_TAIL_RE = re.compile(
    r"(?: Базовая точность(?: магии)? \+\d+\.| Урон в PvP \d+%\.|"
    rf" Шанс (?:{_CC_CHANCE_NAMES}) \d+%(?:, [^.]*)?\."
    r"| Урон \d+(?:-\d+)?\.| Восстанавливает \d+ HP\."
    r"| (?:Стан|Опрокидывание|Ошеломление|Вращение|Немота|Оковы|Воздушные оковы"
    r"|Притягивание|Замедление|Ослепление|Сон|Паралич|Страх)(?:, [^.]*)?\.)+$"
)
CHAIN_CHANCE_RE = re.compile(
    r"(?: Шанс открыть следующее умение серии \([^)]+\): \d+%\."
    r"| Шанс появления этого умения после [^.]+: \d+%\.)+$"
)
CHAIN_100_RE = re.compile(
    r"\s*Шанс открыть следующее умение серии \([^)]+\): 100%\."
    r"|\s*Шанс появления этого умения после [^.]+: 100%\."
)
ACTIVATION_100_PREFIX_RE = re.compile(r"(?i)(?:^|(?<=\. ))С вероятностью 100%\s+(\S)")
ACTIVATION_100_MID_RE = re.compile(r"(?i)\s+с вероятностью 100%")
ACTIVATION_100_NAMED_RE = re.compile(
    r"(?i)\s*шанс(?:ом)? активации(?: умения)? 100%\.?"
    r"|\s*вероятность активации(?: умения)? 100%\.?"
)

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
    "PhyAttack": "Физ. атака",
    "phyAttack": "Физ. атака",
    "phyattack": "Физ. атака",
    "MaxHP": "Макс. HP",
    "maxHp": "Макс. HP",
    "maxhp": "Макс. HP",
    "MagicalSkillBoost": "Сила магии",
    "MagicalSkillBoostResist": "Сопр. магии",
    "magicalskillboostresist": "Сопр. магии",
    "physicaldefend": "Физ. защита",
    "PhysicalDefend": "Физ. защита",
    "AttackDelay": "Скор. атаки",
    "attackRange": "Дальность",
    "ElementalDefendWater": "Защ. от воды",
    "ElementalDefendFire": "Защ. от огня",
    "ElementalDefendAir": "Защ. от воздуха",
    "ElementalDefendEarth": "Защ. от земли",
    "hitAccuracy": "Точность",
    "HitAccuracy": "Точность",
    "Critical": "Крит",
    "critical": "Крит",
    "PhysicalCritical": "Крит",
    "MagicalCritical": "Маг. крит",
    "Flyspeed": "Скор. полета",
    "flyspeed": "Скор. полета",
    "block": "Блок",
    "Block": "Блок",
    "parry": "Парирование",
    "Parry": "Парирование",
    "PhysicalCriticalReduceRate": "Сниж. крита",
    "arstunlike": "Сопр. оглушению",
    "Stun_Arp": "Пробитие оглушения",
    "HealSkillBoost": "Сила лечения",
    "MagicalAccuracy": "Точн. магии",
    "PvPAttackRatio": "Атака в PvP",
    "PVPAttackRatio": "Атака в PvP",
    "pvpattackratio": "Атака в PvP",
    "PvPDefendRatio": "Защита в PvP",
    "PVPDefendRatio": "Защита в PvP",
    "pvpdefendratio": "Защита в PvP",
    "BoostHate": "Агрессия",
    "boosthate": "Агрессия",
    "AllSpeed": "Скорость",
    "allspeed": "Скорость",
    "arSilence": "Сопр. немоте",
    "arsilence": "Сопр. немоте",
    "arRoot": "Сопр. оковам",
    "arroot": "Сопр. оковам",
    "arSnare": "Сопр. замедлению",
    "arsnare": "Сопр. замедлению",
    "arSleep": "Сопр. сну",
    "arsleep": "Сопр. сну",
    "arStumble": "Сопр. опрокидыванию",
    "arstumble": "Сопр. опрокидыванию",
    "ArAll": "Сопр. контролю",
    "arall": "Сопр. контролю",
    "FPRegen": "Восст. полета",
    "fpregen": "Восст. полета",
    "HPRegen": "Реген. HP",
    "hpregen": "Реген. HP",
    "MPRegen": "Реген. MP",
    "mpregen": "Реген. MP",
}
CONDITION_RU = {
    "EveryHit": "каждый удар",
    "Nmlatk": "обычная атака",
    "MagicalAtk": "маг. атака",
    "SkillAtk": "умение",
}
WEAPON_RU = {
    "bow": "лук",
    "dagger": "кинжал",
    "sword": "меч",
    "mace": "булава",
    "staff": "посох",
    "orb": "сфера",
    "spellbook": "книга",
    "polearm": "пика",
    "1h_sword": "меч",
    "2hsword": "двуручный меч",
}
PERIODIC_DAMAGE_TYPES = {"spellatk", "poison", "bleed", "fpatk", "mpatk"}
PHYS_DAMAGE_TYPES = {
    "skillatk_instant",
    "dashatk",
    "movebehindatk",
    "carvesignet",
    "skillatkdrain_instant",
    "backdashatk",
    "closeaerialatk",
    "delayedskillatk_instant",
    "proc_atk_instant",
    "procatk_instant",
}
MAG_DAMAGE_TYPES = {
    "spellatk_instant",
    "signetburst",
    "delayedspellatk_instant",
    "spellatkdrain_instant",
    "mpattack_instant",
}
KNOWN_ATTRS = {
    "MinDamage",
    "MaxDamage",
    "RemainTime",
    "AddDamage",
    "AddEffect",
    "AddEffectCondition",
    "SignetGrade",
    "ChangeSignetGrade",
    "StatName",
    "StatName2",
    "StatName3",
    "Value",
    "Value2",
    "Value3",
    "FixDamage",
    "FixedDamage",
    "ConditionProb",
    "Condition",
    "Damage",
    "OtherSkill",
    "Heal",
    "HealPoint",
    "CheckTime",
    "CheckTimeHeal",
    "SummonTime",
    "CoverValue",
    "ShieldValue",
    "Range",
    "UnitNumber",
    "HPHeal",
    "MPHeal",
    "DelayedTime",
    "CastingBonus",
    "FixValue",
    "RateValue",
    "RandomTime",
    "WeaponCategory",
    "Count",
    "MaxRange",
    "DispelCount",
    "Distance",
    "Speed",
    "AttackType",
    "BonusRate",
    "BoostCount",
    "CurrentHPMP",
    "EffectArea",
    "SubType",
    "BonusValue",
    "DeBoostPenalty",
    "AttackCount",
    "RateDamage",
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


def npc_xml_text() -> str:
    if NPCS_ZIP.exists() and NPCS_ZIP.stat().st_size > 1000:
        with zipfile.ZipFile(NPCS_ZIP) as z:
            raw = z.read("client_npcs.xml")
    else:
        pt = decrypt_pak(NPCS_PAK)
        NPCS_ZIP.parent.mkdir(parents=True, exist_ok=True)
        NPCS_ZIP.write_bytes(pt)
        with zipfile.ZipFile(NPCS_ZIP) as z:
            raw = z.read("client_npcs.xml")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


_NPC_INDEX: dict[str, dict] | None = None
_NPC_BLOCK_RE = re.compile(r"<npc_client>(.*?)</npc_client>", re.S)
_NPC_FIELD_RE = re.compile(r"<([a-zA-Z0-9_]+)>([^<]*)</\1>")
# Combat-ish npc_client tags. Ranger trap objects in this pack only fill
# sensory_range / attack_delay; they have no hit_accuracy / magical_hit_accuracy.
_NPC_KEEP = (
    "id",
    "name",
    "sensory_range",
    "attack_delay",
    "attack_range",
    "attack_rate",
    "move_speed_combat_run",
    "move_speed_normal_run",
    "tribe",
    "ui_type",
    "hpgauge_level",
    "magical_skill_boost",
    "magical_skill_boost_resist",
    "hit_accuracy",
    "magical_hit_accuracy",
    "magical_accuracy",
    "critical",
    "physical_critical",
    "magical_critical",
    "pvp_attack_ratio",
    "pvp_defend_ratio",
)
_NPC_COMBAT_ROWS = (
    ("hit_accuracy", "Точность"),
    ("magical_hit_accuracy", "Точн. магии"),
    ("magical_accuracy", "Точн. магии"),
    ("critical", "Крит"),
    ("physical_critical", "Крит"),
    ("magical_critical", "Маг. крит"),
    ("magical_skill_boost", "Сила магии"),
)
_ELEMENT_RU = {
    "earth": "земля",
    "air": "воздух",
    "wind": "воздух",
    "fire": "огонь",
    "water": "вода",
}


def load_npc_by_name(xml: str | None = None) -> dict[str, dict]:
    global _NPC_INDEX
    if _NPC_INDEX is not None and xml is None:
        return _NPC_INDEX
    text = xml or npc_xml_text()
    out: dict[str, dict] = {}
    for body in _NPC_BLOCK_RE.findall(text):
        fields = {k: v for k, v in _NPC_FIELD_RE.findall(body) if k in _NPC_KEEP}
        name = fields.get("name")
        if name:
            out[name] = fields
    if xml is None:
        _NPC_INDEX = out
    return out


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
        bounds = duration_bounds_ms(e) if "remain2" in e else None
        if chance is None and bounds is None:
            continue
        item = {"name": kind[0], "name_of": kind[1]}
        if chance is not None:
            item["chance"] = chance
        if bounds:
            lo, hi = bounds
            item["duration_ms"] = hi
            if lo != hi:
                item["duration_min_ms"] = lo
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


def _int_field(val: str | None) -> int | None:
    if not val:
        return None
    try:
        n = int(float(val))
    except ValueError:
        return None
    return n if n else None


def parse_block(body: str) -> dict:
    skill_type = None
    pvp = None
    dist = None
    cost_end = None
    cost_param = None
    cost_dp = None
    cast_ms = None
    for name, val in FIELD_RE.findall(body):
        if name == "type" and skill_type is None:
            skill_type = val
        elif name == "pvp_damage_ratio" and val and val != "100":
            pvp = int(val)
        elif name == "first_target_valid_distance" and val:
            dist = int(val)
        elif name == "cost_end" and cost_end is None:
            cost_end = _int_field(val)
        elif name == "cost_parameter" and cost_param is None:
            cost_param = val
        elif name == "cost_dp" and cost_dp is None:
            cost_dp = _int_field(val)
        elif name == "casting_delay" and cast_ms is None:
            cast_ms = _int_field(val)
    skill_is_magic = (skill_type or "").lower() == "magical"
    acc_phys = 0
    acc_magic = 0
    has_mag_status = False
    duration_ms = 0
    duration_min_ms = 0
    interval_ms = 0
    dmg = None
    heal = None
    for e in parse_effects(body).values():
        et = (e.get("type") or "").lower()
        if effect_uses_magic_acc(et):
            has_mag_status = True
        acc = effect_acc(e)
        if acc:
            # acc_mod lives on the effect. Stun/poison/… always vs mag resist;
            # damage on a Magical skill too; otherwise physical dodge.
            # Keep negatives (spiral acc_mod2=-300); max() would drop them.
            dest = "acc_magic" if skill_is_magic or effect_uses_magic_acc(et) else "acc_phys"
            cur = acc_magic if dest == "acc_magic" else acc_phys
            if not cur or abs(acc) > abs(cur):
                if dest == "acc_magic":
                    acc_magic = acc
                else:
                    acc_phys = acc
        remain = remain_ms(e)
        rand = int(e.get("randomtime") or 0)
        if remain > duration_ms:
            duration_ms = remain
            duration_min_ms = remain - rand if rand else remain
        check = int(e.get("checktime") or 0)
        if check > interval_ms:
            interval_ms = check
        if dmg is None and et in MAG_DAMAGE_TYPES:
            n = _int_field(e.get("reserved2"))
            if n:
                dmg = n
        if dmg is None and et in PHYS_DAMAGE_TYPES and e.get("reserved4") not in (None, "", "0"):
            lo, hi = phys_damage(e)
            dmg = [lo, hi]
        if heal is None and et == "heal_instant":
            n = _int_field(e.get("reserved2"))
            if n:
                heal = n
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
    if duration_ms:
        out["duration_ms"] = duration_ms
        if duration_min_ms and duration_min_ms != duration_ms:
            out["duration_min_ms"] = duration_min_ms
    if interval_ms:
        out["interval_ms"] = interval_ms
    if dmg is not None:
        out["dmg"] = dmg
    if heal is not None:
        out["heal"] = heal
    if cast_ms:
        out["cast_ms"] = cast_ms
    param = (cost_param or "").upper()
    if cost_end:
        if param == "HP":
            out["hp_cost"] = cost_end
        elif param == "MP_RATIO":
            out["mp_ratio"] = cost_end
        elif param == "HP_RATIO":
            out["hp_ratio"] = cost_end
        else:
            out["mp"] = cost_end
    if cost_dp:
        out["dp"] = cost_dp
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


def format_core_numbers(desc: str, stats: dict) -> str:
    """When the L10N string has no placeholders, still surface XML damage/heal/duration."""
    if re.search(r"\d", desc or ""):
        return ""
    parts = []
    dmg = stats.get("dmg")
    if isinstance(dmg, list) and len(dmg) == 2:
        parts.append(f"Урон {dmg[0]}-{dmg[1]}.")
    elif isinstance(dmg, int):
        parts.append(f"Урон {dmg}.")
    if stats.get("heal"):
        parts.append(f"Восстанавливает {stats['heal']} HP.")
    if stats.get("duration_ms"):
        parts.append(f"Время действия: {fmt_stats_duration(stats)}")
    return " ".join(parts)


def format_stats(stats: dict) -> str:
    parts = []
    if stats.get("acc_phys"):
        parts.append(f"Базовая точность +{stats['acc_phys']}.")
    if stats.get("acc_magic"):
        parts.append(f"Базовая точность магии +{stats['acc_magic']}.")
    if stats.get("pvp"):
        parts.append(f"Урон в PvP {stats['pvp']}%.")
    for cc in stats.get("cc") or []:
        chance = cc.get("chance")
        if chance is None or chance == 100:
            bit = cc["name"].capitalize()
        else:
            bit = f"Шанс {cc['name_of']} {chance}%"
        if cc.get("duration_ms"):
            bit += f", {fmt_duration_range(cc.get('duration_min_ms') or cc['duration_ms'], cc['duration_ms'])}"
        parts.append(bit + ".")
    return " ".join(parts)


def _keep_chain_tail(chain: str) -> str:
    if not chain:
        return ""
    return "".join(
        sent
        for sent in re.findall(
            r" Шанс открыть следующее умение серии \([^)]+\): \d+%\."
            r"| Шанс появления этого умения после [^.]+: \d+%\.",
            chain,
        )
        if not sent.endswith(": 100%.")
    )


def strip_guaranteed_chances(desc: str) -> str:
    """Drop 100% chain-open / appear / activation phrases; keep other percents."""
    desc = (desc or "").rstrip()
    desc = CHAIN_100_RE.sub("", desc)

    def _cap_after_prob(m: re.Match) -> str:
        word = m.group(1)
        return word[:1].upper() + word[1:]

    desc = ACTIVATION_100_PREFIX_RE.sub(_cap_after_prob, desc)
    desc = ACTIVATION_100_MID_RE.sub("", desc)
    desc = ACTIVATION_100_NAMED_RE.sub("", desc)
    desc = re.sub(
        rf"Шанс ({_CC_CHANCE_NAMES}) 100%(, [^.]+)?\.",
        _cc_100_to_guaranteed,
        desc,
    )
    desc = re.sub(r" {2,}", " ", desc)
    desc = re.sub(r" \.", ".", desc)
    desc = desc.strip()
    if desc and desc[-1] not in ".!?":
        desc += "."
    return desc


def _cc_100_to_guaranteed(m: re.Match) -> str:
    genitive = m.group(1)
    nom = next((nom for nom, gen in CC_TYPES.values() if gen == genitive), genitive)
    tail = m.group(2) or ""
    return f"{nom.capitalize()}{tail}."


def with_stats(desc: str, stats: dict | None) -> str:
    """Keep official L10N only: drop invented stat / chain sentences we used to append."""
    desc = (desc or "").rstrip()
    m = CHAIN_CHANCE_RE.search(desc)
    if m:
        desc = desc[: m.start()].rstrip()
    desc = STAT_TAIL_RE.sub("", desc).rstrip()
    return strip_guaranteed_chances(desc)


def _int0(val: str | None) -> int:
    try:
        return int(float(val or 0))
    except ValueError:
        return 0


def _signed(n: int, pct: bool = False) -> str:
    text = f"+{n}" if n > 0 else str(n)
    return f"{text}%" if pct else text


def _tpl_covers(tpl: str, effect_i: int, attrs: set[str]) -> bool:
    if not tpl:
        return False
    needle = f"e{effect_i}."
    for token in PLACEHOLDER_RE.findall(tpl):
        low = token.lower()
        if needle.lower() not in low:
            continue
        for attr in attrs:
            if attr.lower() in low:
                return True
    return False


def _already_shown(desc: str, label: str, value: str) -> bool:
    """True when the original filled L10N already states this value."""
    if not desc:
        return False
    val = str(value).strip().rstrip(".")
    if val:
        if val.endswith(" с") and not val.endswith("сек"):
            n = val[:-2]
            if re.search(rf"(?<!\d){re.escape(n)} с(?!ек)", desc):
                return True
        elif val in desc:
            return True
    nums = re.findall(r"-?\d+", str(value))
    if not nums or not all(n in desc for n in nums):
        return False
    d = desc.lower()
    keys = {
        "Дальность": ("дальност", "радиус", "расстояни"),
        "КД": ("перезаряд", "кд ", "восстановлен"),
        "Стоимость": ("mp", "hp", "dp", "маны", "затрат"),
        "Время каста": ("каст", "произнес"),
        "Длительность": ("время действия",),
        "Урон": ("урон",),
        "Агрессия": ("агресс", "враждеб"),
        "Длит. агрессии": ("агресс", "враждеб", "сек"),
        "Физ. атака": ("физ. атака", "physical", "phyattack"),
        "Физ. защита": ("физ. защита", "physicaldefend"),
        "Точность": ("точност", "hitaccuracy"),
        "Точн. магии": ("точн. магии", "точность магии", "magicalhit"),
        "Крит": ("крит", "critical"),
        "Уклонение": ("уклон", "dodge"),
        "Блок": ("блок", "block"),
        "Парирование": ("парир", "parry"),
        "Скор. атаки": ("скор. атаки", "скорость атаки", "attackdelay"),
        "Скорость": ("скорость", "speed", "медленн"),
        "Макс. HP": ("макс. hp", "maxhp", "max. hp"),
        "Щит": ("щит", "барьер", "поглощ"),
        "Щит, макс.": ("щит", "барьер", "поглощ", "урона"),
        "Отражение": ("отраж", "reflect"),
        "Интервал": ("интервал", "каждые"),
        "Время действия": ("время действия",),
        "Каст умений": ("каст", "скорость чтения", "casting"),
        "Стоимость умений": ("стоимость", "затрат"),
        "Лечение": ("лечен", "heal", "восстанавливает"),
        "В вампир. HP": ("вампир", "переводит", "поглощ", "hp"),
        "В вампир. MP": ("вампир", "переводит", "поглощ", "мр", "mp"),
        "Атака в PvP": ("pvp", "атака в pvp"),
        "Защита в PvP": ("pvp", "защит"),
        "Урон в PvP": ("pvp",),
        "Сопр. немоте": ("немот", "silence"),
        "Стан": ("стан", "оглуш"),
        "Опрокидывание": ("опрокид", "stumble"),
        "Замедление": ("замедл", "скорость движения"),
        "Немота": ("немот", "silence"),
        "Оковы": ("оков", "обездвиж"),
        "Воздушные оковы": ("воздушн", "оков"),
        "Ошеломление": ("ошелом", "stagger"),
        "Ослепление": ("слеп", "blind"),
        "Промах": ("промах",),
        "Стихия": ("стихи", "земл", "воздух", "огн", "вод"),
        "Шанс активации": ("активац",),
        "Сбить оковы": ("сбить", "обездвиж", "оков"),
    }.get(label, (label.lower(),))
    return any(k in d for k in keys)


def _push_hidden(out: list[dict], seen: set[tuple[str, str]], desc: str, name: str, value: str) -> None:
    value = (value or "").strip()
    if not value or value == "0" or value in {"+0", "0%", "+0%"}:
        return
    if value in {"+100%", "100%"} and "агресс" not in name.lower():
        # 100% success / activation — skip; keep real stat bonuses like «Физ. атака +100%».
        if name.startswith("Шанс") or "активац" in name.lower():
            return
    key = (name, value)
    if key in seen or _already_shown(desc, name, value):
        return
    seen.add(key)
    out.append({"name": name, "value": value})


def hop_is_skill_lv(hop_type: str | None) -> bool:
    """Client hop_type spelling varies: SkillLV / SkillLv / SKillLv / skillLV."""
    return (hop_type or "").lower() == "skilllv"


def skill_lv_hate(e: dict[str, str]) -> int | None:
    """Hate from hop_b when hop_type is SkillLV.

    deepburn's ranger table (4gameforum.com/threads/513760) prints these hop_b
    values as «агрессия» on Sleep / Snare / Stun / Silence / Root / StatUp /
    StatDown / BoostSkillCastingTime — not only HostileUp. hop_type=Damage is
    a different hop (skill damage) and is not hate.
    """
    if not hop_is_skill_lv(e.get("hop_type")):
        return None
    n = _int0(e.get("hop_b"))
    return n or None


def hostile_hate(e: dict[str, str]) -> int | None:
    """HostileUp amount: reserved2 when it is a real delta (calm/taunt), else hop_b."""
    r1 = _int0(e.get("reserved1"))
    r2 = _int0(e.get("reserved2"))
    hop_b = _int0(e.get("hop_b"))
    if abs(r1) > 1 and abs(r2) > 1:
        return r2 if abs(r2) >= abs(r1) else r1
    if abs(r2) > 1:
        return r2
    if abs(r1) > 1:
        return r1
    if hop_b:
        return hop_b
    return None


def _stat_mod_rows(e: dict[str, str], down: bool) -> list[tuple[str, str]]:
    rows = []
    triples = (
        ("reserved13", "reserved2", "reserved4"),
        ("reserved14", "reserved4", None),
        ("reserved18", "reserved16", None),
    )
    pct_flag = e.get("reserved6") == "1"
    for name_k, fix_k, rate_k in triples:
        label = stat_ru(e.get(name_k))
        if not label or label == "?":
            continue
        fix = _int0(e.get(fix_k)) if e.get(fix_k) not in (None, "") else 0
        rate = _int0(e.get(rate_k)) if rate_k and e.get(rate_k) not in (None, "") else 0
        n = fix or rate
        if not n:
            continue
        pct = pct_flag or (not fix and bool(rate))
        if down:
            n = -abs(n)
        rows.append((label, _signed(n, pct)))
    return rows


def _cost_rows(stats: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if stats.get("mp"):
        rows.append(("Стоимость", f"MP {stats['mp']}"))
    elif stats.get("hp_cost"):
        rows.append(("Стоимость", f"HP {stats['hp_cost']}"))
    elif stats.get("mp_ratio"):
        rows.append(("Стоимость", f"{stats['mp_ratio']}% MP"))
    elif stats.get("hp_ratio"):
        rows.append(("Стоимость", f"{stats['hp_ratio']}% HP"))
    if stats.get("dp"):
        rows.append(("Стоимость", f"DP {stats['dp']}"))
    return rows


CLIENT_PARAM_NAMES = frozenset({"КД", "Стоимость", "Время каста"})


def extract_client_params(
    body: str,
    desc: str,
    stats: dict | None = None,
    fields: dict[str, str] | None = None,
) -> list[dict]:
    """CD / cost / cast from skill XML chrome — the client tooltip already shows these."""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    if fields is None:
        fields, _ = parse_skill_meta(body)
    stats = stats if stats is not None else parse_block(body)
    delay = _int0(fields.get("delay_time"))
    if delay > 0:
        _push_hidden(out, seen, desc, "КД", fmt_sec(delay))
    for name, val in _cost_rows(stats):
        _push_hidden(out, seen, desc, name, val)
    if stats.get("cast_ms"):
        _push_hidden(out, seen, desc, "Время каста", fmt_sec(stats["cast_ms"]))
    return out


def _push_base_stats(
    out: list[dict],
    seen: set[tuple[str, str]],
    desc: str,
    stats: dict,
) -> None:
    """XML numbers that the original filled L10N never mentioned."""
    if stats.get("range_m"):
        _push_hidden(out, seen, desc, "Дальность", f"{stats['range_m']} м")
    if stats.get("duration_ms"):
        _push_hidden(out, seen, desc, "Длительность", fmt_stats_duration(stats))
    if stats.get("interval_ms"):
        _push_hidden(out, seen, desc, "Интервал", fmt_remain(stats["interval_ms"]))
    dmg = stats.get("dmg")
    if isinstance(dmg, list) and len(dmg) == 2:
        _push_hidden(out, seen, desc, "Урон", f"{dmg[0]}-{dmg[1]}")
    elif isinstance(dmg, int):
        _push_hidden(out, seen, desc, "Урон", str(dmg))
    if stats.get("heal"):
        _push_hidden(out, seen, desc, "Лечение", str(stats["heal"]))
    if stats.get("acc_phys"):
        _push_hidden(out, seen, desc, "Точность", _signed(stats["acc_phys"]))
    if stats.get("acc_magic"):
        _push_hidden(out, seen, desc, "Точн. магии", _signed(stats["acc_magic"]))
    pvp = stats.get("pvp")
    if pvp and pvp != 100:
        _push_hidden(out, seen, desc, "Урон в PvP", f"{pvp}%")
    for cc in stats.get("cc") or []:
        chance = cc.get("chance")
        if chance is not None and 0 < chance < 100:
            _push_hidden(out, seen, desc, f"Шанс {cc['name_of']}", f"{chance}%")
        if cc.get("duration_ms"):
            label = cc["name"].capitalize() if cc["name"] != "стан" else "Стан"
            _push_hidden(
                out,
                seen,
                desc,
                label,
                fmt_duration_range(cc.get("duration_min_ms") or cc["duration_ms"], cc["duration_ms"]),
            )


def extract_hidden(
    body: str,
    desc: str,
    tpl: str | None = None,
    stats: dict | None = None,
    chain_rows: list[dict] | None = None,
) -> list[dict]:
    """XML stats that the original Russian L10N does not already state."""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    tpl = tpl or ""
    effects = parse_effects(body)
    stats = stats if stats is not None else parse_block(body)
    _push_base_stats(out, seen, desc, stats)
    for row in chain_rows or []:
        _push_hidden(out, seen, desc, row.get("name") or "", row.get("value") or "")

    for i, e in sorted(effects.items()):
        et = (e.get("type") or "").lower()
        hop_hate = skill_lv_hate(e)
        # L10N eN.Value is the effect magnitude (stat/heal), not hate.
        if hop_hate and not _tpl_covers(tpl, i, {"hate", "enmity"}):
            _push_hidden(out, seen, desc, "Агрессия", _signed(hop_hate))
        if et == "hostileup":
            hate = hostile_hate(e)
            if hate and not _tpl_covers(tpl, i, {"value", "hate", "enmity"}):
                _push_hidden(out, seen, desc, "Агрессия", _signed(hate))
            dur = _int0(e.get("reserved5"))
            if dur >= 1000 and not _tpl_covers(tpl, i, {"remaintime", "delayedtime"}):
                _push_hidden(out, seen, desc, "Длит. агрессии", fmt_remain(dur))
        elif et == "boosthate":
            n = _int0(e.get("reserved2"))
            if n and not _tpl_covers(tpl, i, {"value", "ratevalue"}):
                _push_hidden(out, seen, desc, "Агрессия", _signed(n, True))
        elif et in {"statup", "statboost", "weaponstatup", "weaponstatboost", "statdown"}:
            down = et == "statdown"
            slots = (
                ({"statname", "value", "fixvalue", "ratevalue"}, 0),
                ({"statname2", "value2"}, 1),
                ({"statname3", "value3"}, 2),
            )
            rows = _stat_mod_rows(e, down=down)
            for attrs, idx in slots:
                if idx >= len(rows) or _tpl_covers(tpl, i, attrs):
                    continue
                label, val = rows[idx]
                _push_hidden(out, seen, desc, label, val)
        elif et == "shield":
            cover = e.get("reserved2")
            cap = e.get("reserved8")
            if cover and not _tpl_covers(tpl, i, {"covervalue", "value"}):
                _push_hidden(out, seen, desc, "Щит", cover)
            cap_n = _int0(cap)
            if cap and cap not in {"0", ""} and cap_n < 1000000 and not _tpl_covers(tpl, i, {"shieldvalue"}):
                _push_hidden(out, seen, desc, "Щит, макс.", cap)
        elif et == "reflector":
            dmg = e.get("reserved2")
            if dmg and not _tpl_covers(tpl, i, {"fixdamage", "fixeddamage", "damage"}):
                _push_hidden(out, seen, desc, "Отражение", dmg)
        elif et == "boostskillcastingtime":
            n = _int0(e.get("reserved2"))
            if n and not _tpl_covers(tpl, i, {"castingbonus", "value", "bonusrate"}):
                _push_hidden(out, seen, desc, "Каст умений", _signed(n, True))
        elif et == "boostskillcost":
            n = _int0(e.get("reserved2"))
            if n and "без затрат" not in (desc or "").lower() and not _tpl_covers(tpl, i, {"value", "bonusrate"}):
                _push_hidden(out, seen, desc, "Стоимость умений", _signed(n, True))
        elif et == "deboosthealamount":
            n = _int0(e.get("reserved2"))
            if n and not _tpl_covers(tpl, i, {"value", "deboostpenalty"}):
                _push_hidden(out, seen, desc, "Лечение", _signed(n, True))
        elif et in {"alwaysdodge", "alwaysparry", "alwaysresist", "alwaysblock"}:
            n = _int0(e.get("reserved9"))
            if 0 < n <= 20 and not _tpl_covers(tpl, i, {"count", "boostcount"}):
                label = {
                    "alwaysdodge": "Гарант. уклонение",
                    "alwaysparry": "Гарант. парирование",
                    "alwaysresist": "Гарант. сопр. магии",
                    "alwaysblock": "Гарант. блок",
                }[et]
                _push_hidden(out, seen, desc, label, str(n))
        elif et == "blind":
            miss = _int0(e.get("reserved2"))
            if 0 < miss < 100 and not _tpl_covers(tpl, i, {"value", "ratevalue"}):
                _push_hidden(out, seen, desc, "Промах", f"{miss}%")
        elif et == "randommoveloc":
            n = e.get("reserved2")
            if n and n not in {"0", ""} and not _tpl_covers(tpl, i, {"distance"}):
                _push_hidden(out, seen, desc, "Дистанция", f"{n} м")
        elif et == "spellatkdrain_instant":
            hp = e.get("reserved15")
            mp = e.get("reserved17")
            if hp and hp not in {"0", ""} and not _tpl_covers(tpl, i, {"hpheal"}):
                _push_hidden(out, seen, desc, "В вампир. HP", f"{hp}%")
            if mp and mp not in {"0", ""} and not _tpl_covers(tpl, i, {"mpheal"}):
                _push_hidden(out, seen, desc, "В вампир. MP", f"{mp}%")
        elif et == "skillatkdrain_instant":
            hp = e.get("reserved15")
            mp = e.get("reserved17")
            if hp and hp not in {"0", ""} and not _tpl_covers(tpl, i, {"hpheal"}):
                _push_hidden(out, seen, desc, "В вампир. HP", f"{hp}%")
            if mp and mp not in {"0", ""} and not _tpl_covers(tpl, i, {"mpheal"}):
                _push_hidden(out, seen, desc, "В вампир. MP", f"{mp}%")
        elif et == "slow":
            n = _int0(e.get("reserved2"))
            if n and not _tpl_covers(tpl, i, {"value", "ratevalue"}):
                pct = e.get("reserved6") == "1" or abs(n) < 100
                _push_hidden(out, seen, desc, "Скор. атаки", _signed(n, pct))
        elif et == "root":
            # reserved2 is the on-hit break chance (forum shackle 50% = reserved2 50).
            brk = _int0(e.get("reserved2"))
            if 0 < brk < 100 and not _tpl_covers(tpl, i, {"value"}):
                _push_hidden(out, seen, desc, "Сбить оковы", f"{brk}%")

        if et in PHYS_DAMAGE_TYPES:
            # SkillATK reserved6 is 100 on ordinary shots; 200/500 match
            # deepburn «шанс крита» on raging-wind / lethal (thread 513760).
            crit = _int0(e.get("reserved6"))
            if crit and crit != 100 and not _tpl_covers(tpl, i, {"critical", "value"}):
                _push_hidden(out, seen, desc, "Крит", _signed(crit))

        check = _int0(e.get("checktime"))
        if check and not _tpl_covers(tpl, i, {"checktime"}):
            _push_hidden(out, seen, desc, "Интервал", fmt_remain(check))

        if (e.get("type") or "").lower() not in CC_TYPES:
            if "cond_preeffect_prob2" in e or "cond_preeffect" in e:
                chance = _int0(e.get("cond_preeffect_prob2")) + _int0(e.get("cond_preeffect_prob1"))
                if 0 < chance < 100 and not _tpl_covers(tpl, i, {"conditionprob", "prob"}):
                    _push_hidden(out, seen, desc, "Шанс активации", f"{chance}%")
            condp = _int0(e.get("reserved_cond1_prob2"))
            if 0 < condp < 100 and not _tpl_covers(tpl, i, {"conditionprob"}):
                _push_hidden(out, seen, desc, "Шанс активации", f"{condp}%")

    return out


_TRAP_NAME_PREFIXES = ("RA_Light_", "RA_Dark_", "Light_", "Dark_", "RA_")
_PERIODIC_TICK_TYPES = {"poison", "bleed", "spellatk", "fpatk"}

# Absolute trap-NPC magic accuracy (base TM, character without «green» TM).
# 4gameforum.com/threads/343938 deepburn ru-PTS 4.0.2 inspect of trap as NPC.
# 4.x ranks match this table (user: «4.x версия не отличается, уровни ловушек те же»).
_TRAP_FORUM_TM = {
    "DestructionTrap": 1876,  # Взрывная III
    "SpikeTrap": 2325,  # Липкая V
    "SleepingTrap": 2321,  # Ловушка сна II
    "SpikeBiteTrap": 2361,  # Оковы III
    "ExplosionTrap": 2361,  # Мина IV
    "SandstormTrap": 2363,  # Песчаная III
    "StormMine": 2406,  # Ураганная мина I
    "ShockwaveTrap": 2363,  # Шоковая I
    "PoisonTrap": 2321,  # Ядовитая V
    "ThrowingTrap": 2263,  # Замедления V
    "SnakeBiteTrap": 2406,  # Злого духа II
    "FairyFlare": 1050,  # Ясновидения I
    "BlazingTrap": 2396,  # Неистовая V
    "HeavensTrap": 2528,  # Опутывающая VII
}
_TRAP_FORUM_TM_FAMILIES = tuple(sorted(_TRAP_FORUM_TM, key=len, reverse=True))


def trap_forum_mag_acc(*names: str) -> int | None:
    hay = " ".join(n for n in names if n)
    for family in _TRAP_FORUM_TM_FAMILIES:
        if family in hay:
            return _TRAP_FORUM_TM[family]
    return None


def _apply_trap_forum_tm(
    out: list[dict],
    seen: set[tuple[str, str]],
    tm: int | None,
) -> None:
    """Show forum absolute NPC TM as «Точн. магии»; keep XML acc_mod labeled."""
    if tm is None:
        return
    for row in out:
        if row.get("name") != "Точн. магии":
            continue
        val = row.get("value") or ""
        if val.startswith(("+", "-")) or val != str(tm):
            seen.discard(("Точн. магии", val))
            row["name"] = "Модификатор точн. магии"
            seen.add(("Модификатор точн. магии", val))
    if any(r.get("name") == "Точн. магии" for r in out):
        return
    value = str(tm)
    seen.add(("Точн. магии", value))
    after = {"Срабатывание", "Скор. атаки", "Дальность атаки", "Урон"}
    idx = 0
    for i, r in enumerate(out):
        if r.get("name") in after:
            idx = i + 1
    out.insert(idx, {"name": "Точн. магии", "value": value})


def trap_npc_name(body: str) -> str | None:
    for e in parse_effects(body).values():
        if (e.get("type") or "").lower() == "summontrap":
            name = (e.get("reserved9") or "").strip()
            return name or None
    return None


def trap_unit_skill_candidates(npc_name: str) -> list[str]:
    base = npc_name[:-4] if npc_name.endswith("_NPC") else npc_name
    names: list[str] = []

    def add(n: str) -> None:
        if n and n not in names:
            names.append(n)

    rest = base
    for p in _TRAP_NAME_PREFIXES:
        if rest.startswith(p):
            rest = rest[len(p) :]
            break
    add(rest)
    add(f"RA_{rest}")
    if "StormMine" in rest and "Trap" not in rest:
        mine = rest.replace("StormMine", "StormMineTrap")
        dark = "Dark" in npc_name
        light = "Light" in npc_name
        if dark:
            add(f"RA_Dark_{mine}")
        if light:
            add(f"RA_Light_{mine}")
        add(mine)
        add(f"RA_{mine}")
        add(f"RA_Light_{mine}")
        add(f"RA_Dark_{mine}")
    add(base)
    add(base.replace("RA_Light_", "Light_").replace("RA_Dark_", "Dark_"))
    return names


def resolve_trap_unit_body(
    npc_name: str,
    by_name: dict[str, str],
    player_body: str | None = None,
) -> tuple[str, str] | None:
    """Return (skill_name, body) of the trap unit's trigger skill, not the SummonTrap."""
    for name in trap_unit_skill_candidates(npc_name):
        body = by_name.get(name)
        if not body or body is player_body:
            continue
        fields, _ = parse_skill_meta(body)
        if (fields.get("sub_type") or "").lower() == "summontrap":
            continue
        return name, body
    return None


def _fmt_meters(raw: str) -> str:
    n = float(raw)
    if n == int(n):
        return f"{int(n)} м"
    return f"{n:g} м".replace(".", ",")


def extract_trap(
    body: str,
    desc: str,
    by_name: dict[str, str],
    npcs: dict[str, dict] | None = None,
) -> list[dict]:
    """Combat numbers of the summoned trap unit (NPC + its trigger skill).

    «Точн. магии» is the trap NPC's absolute TM from the 4game forum inspect
    (deepburn, ru-PTS 4.0.2), not XML. reserved11 is rate (100 on every trap).
    Effect acc_mod1+acc_mod2 is a skill modifier — kept as
    «Модификатор точн. магии» when present (only DestructionTrap in this pack).
    """
    npc_name = trap_npc_name(body)
    if not npc_name:
        return []
    fields, _ = parse_skill_meta(body)
    forum_tm = trap_forum_mag_acc(npc_name, fields.get("name") or "")
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    npc = (npcs if npcs is not None else load_npc_by_name()).get(npc_name)
    if npc:
        sens = npc.get("sensory_range")
        if sens and float(sens):
            # NPC detect radius — not the L10N explosion radius.
            _push_hidden(out, seen, "", "Срабатывание", _fmt_meters(sens))
        delay = _int0(npc.get("attack_delay"))
        if delay:
            _push_hidden(out, seen, "", "Скор. атаки", fmt_sec(delay))
        ar = npc.get("attack_range")
        if ar and float(ar):
            _push_hidden(out, seen, "", "Дальность атаки", _fmt_meters(ar))
        for key, label in _NPC_COMBAT_ROWS:
            n = _int0(npc.get(key))
            if n:
                _push_hidden(out, seen, "", label, _signed(n))
    resolved = resolve_trap_unit_body(npc_name, by_name, player_body=body)
    if not resolved:
        _apply_trap_forum_tm(out, seen, forum_tm)
        return out
    _unit_name, unit_body = resolved
    forum_tm = forum_tm or trap_forum_mag_acc(npc_name, _unit_name, fields.get("name") or "")
    unit_stats = parse_block(unit_body)
    unit_rows = [
        row
        for row in extract_hidden(unit_body, desc, stats=unit_stats)
        if row.get("name") != "Дальность"
    ]
    cc_labels = {"Стан"} | {kind[0].capitalize() for kind in CC_TYPES.values()}
    cc_vals = {row.get("value") for row in unit_rows if row.get("name") in cc_labels}
    for row in unit_rows:
        if row.get("name") == "Длительность" and row.get("value") in cc_vals:
            continue
        _push_hidden(out, seen, desc, row.get("name") or "", row.get("value") or "")
    for e in parse_effects(unit_body).values():
        et = (e.get("type") or "").lower()
        if et in _PERIODIC_TICK_TYPES:
            tick = _int0(e.get("reserved9"))
            if tick:
                _push_hidden(out, seen, desc, "Урон за тик", str(tick))
        elif et == "fpatk_instant":
            n = _int0(e.get("reserved2"))
            if n:
                _push_hidden(out, seen, desc, "Урон FP", str(n))
        elif et in {"statup", "statboost", "weaponstatup", "weaponstatboost"}:
            label = stat_ru(e.get("reserved22"))
            n = _int0(e.get("reserved20"))
            if label and label != "?" and n:
                _push_hidden(out, seen, desc, label, _signed(n))
        elem = _ELEMENT_RU.get((e.get("reserved10") or "").lower())
        if elem:
            _push_hidden(out, seen, desc, "Стихия", elem)
        add = (e.get("reserved14") or "").strip()
        add_kind = CC_TYPES.get(add.lower())
        if add_kind:
            add_chance = _int0(e.get("reserved18"))
            add_bounds = duration_bounds_ms(e)
            if 0 < add_chance < 100:
                _push_hidden(out, seen, desc, f"Шанс {add_kind[1]}", f"{add_chance}%")
            if add_bounds:
                label = add_kind[0].capitalize() if add_kind[0] != "стан" else "Стан"
                _push_hidden(out, seen, desc, label, fmt_duration_range(*add_bounds))
    _apply_trap_forum_tm(out, seen, forum_tm)
    return out


def _insert_after_cd(tags: list[str], extra: list[str]) -> list[str]:
    if not extra:
        return tags
    out = list(tags)
    idx = next((i for i, t in enumerate(out) if t.startswith("КД ")), None)
    at = (idx + 1) if idx is not None else min(1, len(out))
    for item in reversed(extra):
        if item not in out:
            out.insert(at, item)
    return out


def with_mag_status_tag(tags: list[str], stats: dict | None) -> list[str]:
    """Keep targeting / CC / mag-status chips. Numeric dumps live in the hidden table."""
    tags = [t for t in tags if t != MAG_STATUS_TAG]
    tags = [
        t
        for t in tags
        if not t.startswith(("MP ", "HP ", "DP ", "каст ", "КД "))
        and not re.fullmatch(r"\d+% MP", t)
        and not re.fullmatch(r"\d+% HP", t)
        and not re.fullmatch(r"\d+ м", t)
    ]
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
    return f"{s:g}".replace(".", ",") + " сек."


def stat_ru(raw: str | None) -> str:
    if not raw:
        return "?"
    return STAT_RU.get(raw) or STAT_RU.get(raw.lower()) or STAT_RU.get(raw[:1].upper() + raw[1:]) or raw


def remain_ms(e: dict[str, str]) -> int:
    return int(e.get("remain2") or 0) + int(e.get("remain1") or 0)


def duration_bounds_ms(e: dict[str, str]) -> tuple[int, int] | None:
    """remain2 is the cap; randomtime is subtracted from it, not a min bound."""
    hi = remain_ms(e)
    if not hi:
        return None
    rand = int(e.get("randomtime") or 0)
    lo = hi - rand if rand else hi
    return (0 if lo < 0 else lo), hi


def _fmt_sec_number(ms: int) -> str:
    s = int(ms) / 1000
    if s == int(s):
        return str(int(s))
    return f"{s:g}".replace(".", ",")


def fmt_duration_range(lo: int, hi: int) -> str:
    if lo == hi:
        return fmt_remain(hi)
    return f"{_fmt_sec_number(lo)}–{_fmt_sec_number(hi)} сек."


def fmt_stats_duration(stats: dict) -> str:
    hi = int(stats.get("duration_ms") or 0)
    lo = int(stats.get("duration_min_ms") or hi)
    return fmt_duration_range(lo, hi)


def format_attr(attr: str, e: dict[str, str]) -> str:
    et = (e.get("type") or "").lower()
    if attr in ("MinDamage", "MaxDamage"):
        lo, hi = phys_damage(e)
        return str(lo if attr == "MinDamage" else hi)
    if attr == "RemainTime":
        ms = remain_ms(e)
        return fmt_remain(ms) if ms else "?"
    if attr == "RandomTime":
        remain = remain_ms(e)
        rand = int(e.get("randomtime") or 0)
        if remain and rand:
            ms = remain - rand
        else:
            ms = rand or remain
        return fmt_remain(ms) if ms else "?"
    if attr == "CheckTime":
        ms = int(e.get("checktime") or 0)
        return fmt_remain(ms) if ms else "?"
    if attr == "SummonTime":
        sec = e.get("reserved4") or ""
        return f"{sec} сек." if sec else "?"
    if attr == "DelayedTime":
        ms = int(e.get("reserved9") or 0)
        return fmt_remain(ms) if ms else "?"
    if attr == "AddDamage":
        return e.get("reserved10") or "?"
    if attr == "AddEffect":
        return e.get("reserved14") or "?"
    if attr == "AddEffectCondition":
        return e.get("reserved18") or e.get("reserved15") or "?"
    if attr == "SignetGrade":
        if et == "signetburst":
            return e.get("reserved8") or "?"
        return e.get("reserved14") or e.get("reserved8") or "?"
    if attr == "ChangeSignetGrade":
        return e.get("reserved10") or "?"
    if attr == "StatName":
        return stat_ru(e.get("reserved13"))
    if attr == "StatName2":
        return stat_ru(e.get("reserved14"))
    if attr == "StatName3":
        return stat_ru(e.get("reserved18"))
    if attr == "Value":
        return e.get("reserved2") or "?"
    if attr == "Value2":
        return e.get("reserved4") or "?"
    if attr == "Value3":
        return e.get("reserved16") or "?"
    if attr == "FixValue":
        return e.get("reserved2") or "?"
    if attr == "RateValue":
        return e.get("reserved4") or "?"
    if attr in ("FixDamage", "FixedDamage", "RateDamage"):
        return e.get("reserved2") or "?"
    if attr in ("Heal", "HealPoint"):
        return e.get("reserved2") or "?"
    if attr == "CheckTimeHeal":
        return e.get("reserved9") or "?"
    if attr == "Damage":
        if et in PERIODIC_DAMAGE_TYPES or e.get("checktime"):
            return e.get("reserved9") or e.get("reserved2") or "?"
        return e.get("reserved2") or e.get("reserved9") or "?"
    if attr == "ConditionProb":
        return e.get("reserved_cond1_prob2") or "?"
    if attr == "Condition":
        raw = e.get("reserved_cond1") or ""
        return CONDITION_RU.get(raw, raw) or "?"
    if attr == "CoverValue":
        return e.get("reserved2") or "?"
    if attr == "ShieldValue":
        return e.get("reserved8") or "?"
    if attr == "Range":
        if et == "protect":
            return e.get("reserved5") or "?"
        return e.get("reserved3") or e.get("reserved5") or "?"
    if attr == "UnitNumber":
        return e.get("reserved4") or "?"
    if attr == "HPHeal":
        if et == "spellatkdrain_instant":
            return e.get("reserved15") or "?"
        return e.get("reserved10") or "?"
    if attr == "MPHeal":
        return e.get("reserved17") or "?"
    if attr == "CastingBonus":
        return e.get("reserved2") or "?"
    if attr == "WeaponCategory":
        raw = (e.get("reserved5") or "").lower()
        return WEAPON_RU.get(raw, e.get("reserved5") or "?")
    if attr == "Count":
        return e.get("reserved9") or "?"
    if attr == "MaxRange":
        return e.get("reserved5") or "?"
    if attr == "Distance":
        return e.get("reserved2") or "?"
    if attr == "Speed":
        return e.get("reserved2") or "?"
    if attr == "AttackType":
        return e.get("reserved5") or "?"
    if attr == "BonusRate":
        return e.get("reserved2") or "?"
    if attr in ("BoostCount", "AttackCount"):
        return e.get("reserved7") or "?"
    if attr == "DispelCount":
        return e.get("reserved2") or "?"
    if attr == "CurrentHPMP":
        return e.get("reserved2") or "?"
    if attr == "EffectArea":
        return e.get("reserved4") or "?"
    if attr == "SubType":
        return e.get("reserved3") or "?"
    if attr == "BonusValue":
        return e.get("reserved4") or e.get("reserved2") or "?"
    if attr == "DeBoostPenalty":
        return e.get("reserved2") or "?"
    return "?"


def otherskill_name(e: dict[str, str]) -> str | None:
    for key in ("reserved17", "reserved1", "reserved9", "reserved6"):
        v = (e.get(key) or "").strip()
        if v and re.search(r"[A-Za-z]", v) and "_" in v:
            return v
    return None


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
            if i >= len(parts):
                return "?"
            nxt = parts[i]
            if nxt not in KNOWN_ATTRS and nxt in by_name:
                _, ctx = parse_skill_meta(by_name[nxt])
                i += 1
                continue
            if nxt == "OtherSkill":
                proc = by_name.get(otherskill_name(e) or "")
                if not proc:
                    return "?"
                _, ctx = parse_skill_meta(proc)
                i += 1
                continue
            if nxt not in KNOWN_ATTRS:
                i += 1
            elif i + 1 < len(parts) and parts[i + 1] in KNOWN_ATTRS:
                # Effect type Heal/MPHeal collides with attribute names.
                i += 1
            if i >= len(parts):
                return "?"
            attr = parts[i]
            if attr == "OtherSkill":
                proc = by_name.get(otherskill_name(e) or "")
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
        val = resolve_placeholder(m.group(1), fields, effects, by_name)
        return "" if val == "?" else val

    text = PLACEHOLDER_RE.sub(repl, tpl).replace("%%", "%")
    text = re.sub(r" +", " ", text).strip()
    # [%RandomTime%]-[%RemainTime%] → "6 сек.-8 сек." → "6–8 сек."
    text = re.sub(
        r"(\d+(?:,\d+)?) сек\.\s*-\s*(\d+(?:,\d+)?) сек\.?",
        r"\1–\2 сек.",
        text,
    )
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
        r'(  (\w+): \{\n    name: ".*?",\n    kind: ".*?",\n    tags: )(\[[^\]]*\])(,\n    desc: )("(?:\\.|[^"\\])*")((?:,\n    params: \[[^\]]*\])?)((?:,\n    hidden: \[[^\]]*\])?)((?:,\n    trap: \[[^\]]*\])?)(,\n    cd:)',
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
            + m.group(7)
            + m.group(8)
            + m.group(9)
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
