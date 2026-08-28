"""Build js/skills.js from aidb.ru (assassin-only, legacy).

Prefer tools/generate_all_skills.py — it reads Origin client XML for all 4.6 classes.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from pathlib import Path

from parse_aidb import download_icon, parse
from client_skill_stats import MAG_STATUS_TAG, load_cached_stats, maybe_fill_desc, with_stats

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "img" / "skills"
OUT_JS = ROOT / "js" / "skills.js"
DATA_JS = ROOT / "js" / "data.js"
DETAILS_PATH = ROOT / "tools" / "aidb_details.json"

GREATER = {
    "Beastly Scar",
    "Agonizing Slash",
    "Apply Lethal Venom",
    "Lightning Slash",
    "Agony Rune",
    "Dash and Slash",
    "Explosive Burst",
    "Sensory Boost",
    "Signet Silence",
    "Quickening Doom",
}

# aidb Russian max-rank name -> stable id
NAME_TO_ID = {
    "Маскировка тени": "shadowHide",
    "Точный расчет": "calc",
    "Клятва скорости": "oathSpeed",
    "Клятва уклонения": "oathDodge",
    "Поиск слабых мест": "weakspot",
    "Обостренное восприятие": "searchingEye",
    "Применение смертельных ядов": "deadlyPoison",
    "Клятва точности": "oathAcc",
    "Покров сумрака": "windWalk",
    "Маскировка": "stealth",
    "Око гнева": "eyeWrath",
    "Туманная завеса": "fog",
    "Просветление": "seeing",
    "Снятие шока": "unshock",
    "Теневая иллюзия": "flashSpeed",
    "Боевая готовность": "spelldodge",
    "Стойка налетчика": "stance",
    "Теневой шаг": "shadowStep",
    "Готовность": "deadlyAbandon",
    "Воспламенение клейма тьмы": "darknessRune",
    "Воспламенение клейма черного пекла": "runeSwipe",
    "Вспышка клейма небес": "divineRune",
    "Вспышка клейма света": "radiantRune",
    "Цепь уклонений": "evasiveBoost",
    "Обострение чувств": "senses",
    "Усмирение": "calm",
    "Клык зверя": "fang",
    "Убийство": "assassination",
    "Штурмовая стойка": "deadlyFocus",
    "Бросок сюрикена": "throwShuriken",
    "Прыжок зверя": "beastLeap",
    "Стремительный удар": "swift",
    "Крестообразный надрез": "crossSlash",
    "Нанесение древнего клейма": "ancient",
    "Режущая атака": "dash",
    "Удар небес": "divineStrike",
    "Удар тьмы": "darkStrike",
    "Блистательная вспышка": "explosiveBurst",
    "Бросок кинжала": "dagger",
    "Восстановление MP": "mpHerb",
    "Вспышка иссушающего клейма": "bloodRune",
    "Вспышка клейма молчания": "silenceRune",
    "Лечение травами": "powder",
    "Падение в тень": "shadowfall",
    "Подлый удар": "weaken",
    "Внезапная атака": "sudden",
    "Вспышка клейма": "flash",
    "Нанесение клейма": "stigma",
    "Распятие": "killingSpree",
    "Атака ядом": "poisonHit",
    "Всеобщее истребление": "massacre",
    "Кинжал Байзела": "vaizelDirk",
    "Кинжал Триниэль": "trinielDirk",
    "Небесный плен": "bindingRune",
    "Отражение клейма": "runeReflect",
    "Перевоплощение: Убийца": "slayerForm",
    "Ураганная мощь": "whirl",
    "Засада": "ambush",
    "Обратный порез": "sideStrike",
    "Падение": "crash",
    "Контратака": "counter",
    "Рассекающий удар": "cleave",
    "Спасение": "escape",
    "Обратный урон": "encirclingStrike",
    "Отравленный клинок": "poisonBlade",
    "Порох": "lethalVenom",
    "Рассекающая молния": "lightning",
    "Рев зверя": "roar",
    "Стремительный рассекающий удар": "agonySlash",
    "Удар зверя": "beastKick",
    "Чудовищный шрам": "beastScar",
    "Бросок зверя": "beastSwipe",
    "Вспышка особого клейма": "needle",
    "Клинок обморока": "quickDoom",
    "Крученый удар": "spiralSlash",
    "Нанесение клейма на расстоянии": "runeKnife",
    "Подлый набег": "blindSide",
    "Разрушение клейма": "crush",
    "Вспышка сложного клейма": "agonyRune",
    "Кровоточащий порез": "dashSlash",
    "Нанесение сложного клейма": "complex",
    "Обратный сокрушительный удар": "searchStrike",
    "Приветствие тени": "illusion",
    "Штормовая мощь": "storm",
    "Быстрое возвращение": "fastReturn",
    "Возвращение": "returnHome",
    "Концентрация на уклонении": "focusedEvasion",
    "Перевязка": "bandage",
    "Ритуал": "ritual",
}

OLD_DESC = {}
OLD_KIND = {}
OLD_TAGS = {}


def load_old() -> None:
    for path in (OUT_JS, DATA_JS):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(
            r"  (\w+): \{\s*name: \"([^\"]+)\",\s*kind: \"([^\"]+)\",\s*tags: \[([^\]]*)\],\s*desc: \"([^\"]*)\",",
            text,
        ):
            sid = m.group(1)
            if sid not in OLD_KIND:
                OLD_KIND[sid] = m.group(3)
                OLD_DESC[sid] = m.group(5)
                OLD_TAGS[sid] = re.findall(r"\"([^\"]+)\"", m.group(4))



def infer_kind(rec: dict, sid: str) -> str:
    if sid in OLD_KIND:
        return OLD_KIND[sid]
    if rec["stigma"]:
        return "stigma"
    name = rec["base"]
    if name in ("Снятие шока", "Приветствие тени", "Спасение"):
        return "panic"
    if name in ("Точный расчет", "Поиск слабых мест", "Штурмовая стойка", "Цепь уклонений"):
        return "buff"
    if "Перевоплощение" in name or "Кинжал" in name and rec.get("race"):
        return "burst"
    if name in ("Маскировка", "Маскировка тени", "Просветление", "Усмирение", "Лечение травами", "Восстановление MP", "Покров сумрака", "Возвращение", "Быстрое возвращение", "Перевязка"):
        return "utility"
    if name in ("Ритуал", "Концентрация на уклонении"):
        return "buff"
    return "combat"


def cd_short(cd: str) -> str:
    cd = cd.replace(" сек.", " с").replace("сек.", "с")
    if cd in ("0 с", "0 сек."):
        return "мгновенно"
    return cd


def js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def roman(n: int) -> str:
    table = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    return table[n] if n < len(table) else str(n)


def skill_tags(range_: str, cd: str, cc: list[str], mag_status: bool = False) -> list[str]:
    tags = []
    if range_:
        tags.append(range_)
    if cd:
        tags.append(f"КД {cd}")
    tags.extend(cc)
    if mag_status:
        tags.append(MAG_STATUS_TAG)
    return tags


def main() -> None:
    load_old()
    DETAILS = {}
    if DETAILS_PATH.exists():
        DETAILS = json.loads(DETAILS_PATH.read_text(encoding="utf-8"))
    CLIENT_STATS = load_cached_stats()
    rows = parse()
    skills: dict[str, dict] = {}
    stigma_tier: dict[str, str] = {}
    skill_race: dict[str, str] = {}

    for rec in rows:
        base = rec["base"]
        sid = NAME_TO_ID.get(base)
        if not sid:
            print("UNMAPPED", base)
            continue
        if sid == "slayerForm":
            sid = "slayerElyos" if rec["race"] == "elyos" else "slayerAsmo"
        if rec["race"]:
            skill_race[sid] = rec["race"]
        if rec["stigma"]:
            en = rec["en_base"]
            stigma_tier[sid] = "greater" if en in GREATER or base in {
                "Чудовищный шрам",
                "Стремительный рассекающий удар",
                "Порох",
                "Рассекающая молния",
                "Вспышка сложного клейма",
                "Кровоточащий порез",
                "Блистательная вспышка",
                "Обострение чувств",
                "Вспышка клейма молчания",
                "Клинок обморока",
            } else "normal"

        en = rec["en_base"] if rec["en_base"] not in ("", "no_name") else ""
        details = DETAILS.get(sid)
        cd = cd_short(rec["cd"])
        client_stats = CLIENT_STATS.get(sid)
        if details:
            desc = with_stats(
                maybe_fill_desc(
                    sid,
                    details.get("desc") or ((f"{en}. " if en else "") + f"Ранг {roman(rec['rank'])}, ур. {rec['level']}."),
                ),
                client_stats,
            )
            tags = skill_tags(
                details.get("range") or "ближний",
                details.get("cd") or cd,
                details.get("cc") or [],
                bool((client_stats or {}).get("mag_status")),
            )
            if details.get("cd"):
                cd = details["cd"]
        else:
            desc = with_stats(
                maybe_fill_desc(
                    sid,
                    OLD_DESC.get(sid) or ((f"{en}. " if en else "") + f"Ранг {roman(rec['rank'])}, ур. {rec['level']}."),
                ),
                client_stats,
            )
            tags = skill_tags("ближний", cd, [], bool((client_stats or {}).get("mag_status")))

        skills[sid] = {
            "name": base,
            "kind": infer_kind(rec, sid),
            "tags": tags,
            "desc": desc,
            "cd": cd,
            "icon_file": rec["icon"],
            "rank": rec["rank"],
            "level": rec["level"],
        }
        dest = ICON_DIR / f"{sid}.png"
        ok = download_icon(rec["icon"], dest)
        print(("ok" if ok else "FAIL"), sid, rec["icon"], rec["base"])

    extra_items = {
        "curePotion": {
            "name": "Сильное зелье исцеления",
            "kind": "utility",
            "tags": ["на себя", "КД 10 с"],
            "desc": "Снимает негативные эффекты.",
            "cd": "10 с",
            "icon": "icon_item_potion_cure01a.png",
        },
        "recoverySerum": {
            "name": "Редкое зелье восстановления VI",
            "kind": "utility",
            "tags": ["на себя", "КД 10 с"],
            "desc": "Восстанавливает 1940 HP и 1680 MP.",
            "cd": "10 с",
            "icon": "icon_item_potion_hpmp03_5.png",
        },
        "manaSerum": {
            "name": "Чудесное зелье маны IV",
            "kind": "utility",
            "tags": ["на себя", "КД 10 с"],
            "desc": "Восстанавливает 3450 MP. За очки бездны.",
            "cd": "10 с",
            "icon": "icon_item_potion_mp04_3.png",
        },
        "lifeSerum": {
            "name": "Особое зелье жизни IV",
            "kind": "utility",
            "tags": ["на себя", "КД 10 с"],
            "desc": "Восстанавливает 3680 HP. За очки бездны.",
            "cd": "10 с",
            "icon": "icon_item_potion_hp04_3.png",
        },
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
    }
    for sid, item in extra_items.items():
        icon = item.pop("icon", None)
        if sid not in skills:
            skills[sid] = item
        dest = ICON_DIR / f"{sid}.png"
        if icon and not dest.exists():
            download_icon(icon, dest)

    # write JS
    lines = ["const SKILLS = {"]
    for sid, s in skills.items():
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
    for sid, tier in stigma_tier.items():
        lines.append(f"  {sid}: {js_str(tier)},")
    lines.append("};")
    lines.append("")
    lines.append("const SKILL_RACE = {")
    for sid, race in skill_race.items():
        lines.append(f"  {sid}: {js_str(race)},")
    lines.append("};")
    lines.append("")
    lines.append('const BASIC_SKILLS = new Set(["autoAttack", "weaponSwap"]);')
    OUT_JS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", OUT_JS, "skills", len(skills), "stigmas", len(stigma_tier))


if __name__ == "__main__":
    main()
