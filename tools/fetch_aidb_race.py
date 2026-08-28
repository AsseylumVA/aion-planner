"""Download aidb.ru class trees and extract racial skill tags.

aidb encodes race as:
  class tree name cell: <i>Только для Элийцев</i> / <i>Только для Асмодиан</i>
  skill_info field:     Раса: Только для Элийцев / Только для Асмодиан

Origin client_skill_learns often says All for these (multirace server).
Learned-skill filter uses this map, not Origin XML.
"""
from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_aidb import TableParser

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "tools" / "aidb_race.json"
CACHE_DIR = ROOT / "tools" / "aidb_trees"
BASE = "https://aidb.ru/"
CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 aion-assassin-planner"}

# Specs + base classes (shared early skills). Gunner/bard/artist omitted.
CLASS_PAGES = [
    "warrior",
    "gladiator",
    "templar",
    "scout",
    "ranger",
    "assassin",
    "mage",
    "sorcerer",
    "spiritmaster",
    "priest",
    "cleric",
    "chanter",
]


def fetch_html(name: str, force: bool = False) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CACHE_DIR / f"{name}.htm"
    if dest.exists() and dest.stat().st_size > 1000 and not force:
        return dest.read_text(encoding="cp1251", errors="replace")
    url = f"{BASE}{name}_skills_aion.htm"
    req = urllib.request.Request(url, headers=UA)
    last_err = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
                data = r.read()
            dest.write_bytes(data)
            return data.decode("cp1251", errors="replace")
        except Exception as e:
            last_err = e
            time.sleep(0.4)
    raise RuntimeError(f"{name}: {last_err}")


def parse_tree(html: str) -> dict[int, str]:
    p = TableParser()
    p.feed(html)
    out: dict[int, str] = {}
    for row in p.rows:
        sid = row.get("skill_id")
        race = row.get("race")
        if sid and race:
            out[int(sid)] = race
    return out


def collect_race_map(force: bool = False) -> dict[int, str]:
    by_id: dict[int, str] = {}
    for name in CLASS_PAGES:
        html = fetch_html(name, force=force)
        part = parse_tree(html)
        print(f"  {name:16} racial ids {len(part)}")
        for sid, race in part.items():
            prev = by_id.get(sid)
            if prev and prev != race:
                print("CONFLICT", sid, prev, race)
            by_id[sid] = race
        if force:
            time.sleep(0.15)
    return by_id


def write_race_json(by_id: dict[int, str]) -> dict:
    payload = {
        "source": "https://aidb.ru/{class}_skills_aion.htm",
        "note": "Раса from class-tree «Только для Элийцев/Асмодиан»; skill_info has the same Раса field.",
        "by_id": {str(k): v for k, v in sorted(by_id.items())},
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def fetch_and_write(force: bool = False) -> dict[int, str]:
    print("fetching aidb class trees…")
    by_id = collect_race_map(force=force)
    write_race_json(by_id)
    elyos = sum(1 for v in by_id.values() if v == "elyos")
    asmo = sum(1 for v in by_id.values() if v == "asmo")
    print("wrote", OUT_JSON, "ids", len(by_id), "elyos", elyos, "asmo", asmo)
    return by_id


def load_aidb_race() -> dict[int, str]:
    if not OUT_JSON.exists():
        return fetch_and_write()
    data = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    raw = data.get("by_id", data)
    return {int(k): v for k, v in raw.items() if v in ("elyos", "asmo")}


def main() -> None:
    force = "--force" in sys.argv
    fetch_and_write(force=force)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
