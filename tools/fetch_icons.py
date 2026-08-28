"""Download Aion 4.x assassin/scout skill icons from Aion Codex.

Codex and aidb PNGs are native 40×40 — same art as the 40×40 region inside
client skills.pak 64×64 DDS. There is no 64/128 class-skill pack on Codex.
Prefer tools/generate_all_skills.py copy_icon from the client zip.
"""
from __future__ import annotations

import html
import json
import re
import ssl
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "img" / "skills"
CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 aion-assassin-planner"}

ICON_RE = re.compile(r"/skills/([A-Za-z0-9_.-]+\.png)")
NAME_RE = re.compile(r"<b>([^<]+)</b>")
ROMAN = re.compile(r"\s+[IVXLCDM]+\s*$")

# Planner id -> English names in Aion Codex 4.x / 4.8
ALIASES: dict[str, list[str]] = {
    "ambush": ["Ambush"],
    "roar": ["Fang Strike"],
    "sudden": ["Surprise Attack"],
    "swift": ["Swift Edge"],
    "fang": ["Fangdrop Stab"],
    "cleave": ["Soul Slash"],
    "beastKick": ["Beast Kick"],
    "beastSwipe": ["Beast Swipe"],
    "stigma": ["Rune Carve"],
    "flash": ["Pain Rune"],
    "crush": ["Rune Burst"],
    "dash": ["Dash Attack"],
    "counter": ["Counterattack"],
    "frenzy": ["Sprinting"],
    "dagger": ["Throw Dagger"],
    "ancient": ["Rune Slash"],
    "fog": ["Blinding Burst"],
    "unshock": ["Remove Shock"],
    "illusion": ["Shadow Illusion"],
    "oathDodge": ["Aethertwisting"],
    "stealth": ["Hide"],
    "seeing": ["All-Seeing Eye"],
    "oathSpeed": ["Flurry"],
    "oathAcc": ["Oath of Accuracy"],
    "calc": ["Killer's Eye"],
    "senses": ["Sensory Boost"],
    "shadowStep": ["Shadow Walk"],
    "speedSlash": ["Lightning Slash"],
    "lightning": ["Lightning Slash"],
    "poisonHit": ["Venomous Strike"],
    "complex": ["Sigil Strike"],
    "poisonBlade": ["Apply Poison"],
    "darkStrike": ["Strike of Darkness"],
    "stance": ["Shadow Rage"],
    "calm": ["Calming Whisper"],
    "powder": ["Herb Treatment"],
    "escape": ["Break Away"],
    "spelldodge": ["Spelldodging"],
    "ritual": ["Devotion"],
    "weakspot": ["Clear Focus"],
    "focusedEvasion": ["Focused Evasion"],
    "deadlyFocus": ["Deadly Focus"],
    "deadlyAbandon": ["Deadly Abandon"],
    "searchingEye": ["Searching Eye"],
    "beastScar": ["Beastly Scar"],
    "beastLeap": ["Beast Leap"],
    "needle": ["Needle Rune"],
    "bloodRune": ["Blood Rune"],
    "silenceRune": ["Signet Silence"],
    "assassination": ["Assassination"],
    "weaken": ["Weakening Blow"],
    "crash": ["Crashing Wind Strike"],
    "whirl": ["Whirlwind Slash"],
    "storm": ["Cyclone Slash"],
    "runeReflect": ["Bursting Flame Strike"],
    "agonySlash": ["Agonizing Slash"],
    "dashSlash": ["Dash and Slash"],
    "lethalVenom": ["Apply Lethal Venom"],
    "deadlyPoison": ["Apply Deadly Poison"],
    "venomStrike": ["Venomous Strike"],
    "quickDoom": ["Quickening Doom"],
    "throwShuriken": ["Throw Shuriken"],
    "runeKnife": ["Rune Knife"],
    "eyeWrath": ["Eye of Wrath"],
    "flashSpeed": ["Flash of Speed"],
    "agonyRune": ["Agony Rune"],
    "scoundrel": ["Scoundrel's Bond"],
    "searchStrike": ["Searching Strike"],
    "ripclaw": ["Ripclaw Strike"],
    "crossSlash": ["Cross Slash"],
    "explosiveRebrand": ["Explosive Rebranding"],
    "massacre": ["Massacre"],
    "killingSpree": ["Killing Spree"],
    "blindSide": ["Blind Side"],
    "shadowfall": ["Shadowfall"],
    "shimmerbomb": ["Shimmerbomb"],
    "sideStrike": ["Side Strike"],
    "windWalk": ["Wind Walk"],
    "divineStrike": ["Divine Strike"],
    "hide1": ["Hide"],
    "mpHerb": ["Mana Treatment"],
}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            data = r.read()
            ctype = r.headers.get("Content-Type", "")
        if len(data) < 200 or "text/html" in ctype:
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print("  fail", url, e)
        return False


def parse_rows(payload: dict) -> list[tuple[int, str, str, int]]:
    rows = payload.get("aaData") or []
    out = []
    for row in rows:
        sid = int(row[0])
        icon = (ICON_RE.findall(str(row[1])) or [""])[0]
        name = (NAME_RE.findall(str(row[2])) or [""])[0]
        try:
            lvl = int(row[3])
        except Exception:
            lvl = 0
        if name and icon:
            out.append((sid, name, icon, lvl))
    return out


def base_name(name: str) -> str:
    return ROMAN.sub("", html.unescape(name)).strip()


def collect() -> dict[str, tuple[str, int, int]]:
    """base english name -> (icon filename, skill id, level). Keep highest level."""
    urls = [
        "https://aioncodex.com/query.php?a=skills&type=assassin&l=4x&sl=1",
        "https://aioncodex.com/query.php?a=skills&type=assassin&slot=active&l=4x&sl=1",
        "https://aioncodex.com/query.php?a=skills&type=assassin&slot=stigma&l=4x&sl=1",
        "https://aioncodex.com/query.php?a=skills&type=scout&l=4x&sl=1",
        "https://aioncodex.com/query.php?a=skills&type=assassin&l=48&sl=1",
        "https://aioncodex.com/query.php?a=skills&type=scout&l=48&sl=1",
    ]
    best: dict[str, tuple[str, int, int]] = {}
    for url in urls:
        print("fetch", url)
        try:
            payload = fetch_json(url)
        except Exception as e:
            print("  skip", e)
            continue
        rows = parse_rows(payload)
        print("  rows", len(rows))
        for sid, name, icon, lvl in rows:
            key = base_name(name).lower()
            prev = best.get(key)
            if prev is None or lvl >= prev[2]:
                best[key] = (icon, sid, lvl)
    return best


def main() -> None:
    catalog = collect()
    print("\nunique names", len(catalog))
    for k in sorted(catalog):
        icon, sid, lvl = catalog[k]
        print(f"{k:42} lv{lvl:3} {sid:6} {icon}")

    data_js = (ROOT / "js" / "data.js").read_text(encoding="utf-8").split("const COMBOS")[0]
    ids = re.findall(r"^  ([a-zA-Z][a-zA-Z0-9]+): \{", data_js, re.M)

    extras = {
        "mpHerb": "https://aioncodex.com/items/icon_item_potion_mp03.png",
        "curePotion": "https://aidb.ru/uploads/item_icon/icon_item_potion_cure01a.png",
        "recoverySerum": "https://aidb.ru/uploads/item_icon/icon_item_potion_hpmp03_5.png",
        "manaSerum": "https://aidb.ru/uploads/item_icon/icon_item_potion_mp04_3.png",
        "lifeSerum": "https://aidb.ru/uploads/item_icon/icon_item_potion_hp04_3.png",
    }

    mapped: dict[str, str] = {}
    missing: list[str] = []
    for sid in ids:
        aliases = ALIASES.get(sid, [])
        hit = None
        for alias in aliases:
            hit = catalog.get(alias.lower())
            if hit:
                break
        if not hit and aliases:
            # fuzzy contains
            for alias in aliases:
                for name, row in catalog.items():
                    if alias.lower() in name or name in alias.lower():
                        hit = row
                        break
                if hit:
                    break
        if hit:
            mapped[sid] = hit[0]
        else:
            missing.append(sid)

    print("\nMAPPED", len(mapped), "MISSING", missing)

    OUT.mkdir(parents=True, exist_ok=True)
    local: dict[str, str] = {}
    for sid, icon in mapped.items():
        dest = OUT / f"{sid}.png"
        url = extras.get(sid, f"https://aioncodex.com/skills/{icon}")
        if dest.exists() and dest.stat().st_size > 200:
            local[sid] = f"img/skills/{sid}.png"
            continue
        ok = download(url, dest)
        print(("ok" if ok else "MISS"), sid, icon)
        if ok:
            local[sid] = f"img/skills/{sid}.png"

    (ROOT / "tools" / "icon_map.json").write_text(
        json.dumps({"mapped": mapped, "local": local, "missing": missing}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("saved", len(local), "files to", OUT)


if __name__ == "__main__":
    main()
