"""Parse aidb.ru assassin skill tree: active, max rank only."""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "tools" / "aidb.htm"
OUT_JSON = ROOT / "tools" / "aidb_skills.json"
ICON_DIR = ROOT / "img" / "skills"
BASE = "https://aidb.ru/"
CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 aion-assassin-planner"}

ROMAN = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12,
}
RANK_RE = re.compile(r"\s+([IVX]+)\s*$")
LEVEL_RE = re.compile(r"Уровень\s+(\d+)")


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.level = 0
        self.in_row = False
        self.cell = 0
        self.rows: list[dict] = []
        self.cur: dict | None = None
        self.buf: list[str] = []
        self.in_td = False
        self.in_em = False
        self.in_name_a = False

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "a" and ad.get("name", "").startswith("level_"):
            try:
                self.level = int(ad["name"].split("_")[1])
            except ValueError:
                pass
        if tag == "tr" and self.level:
            self.in_row = True
            self.cell = -1
            self.cur = {
                "level": self.level,
                "icon": "",
                "name": "",
                "en": "",
                "type": "",
                "cost": "",
                "cast": "",
                "cd": "",
                "stigma": False,
                "ancient": False,
                "race": None,
                "skill_id": None,
            }
        if tag == "td" and self.in_row:
            self.cell += 1
            self.in_td = True
            self.buf = []
        if tag == "img" and self.in_row and self.cell == 0:
            src = ad.get("src", "")
            if "item_icon" in src:
                self.cur["icon"] = src.split("/")[-1]
        if tag == "a" and self.in_row and self.cell == 1:
            href = ad.get("href", "")
            m = re.search(r"id=(\d+)", href.replace("%5F", "_"))
            if m and "skill" in href:
                self.cur["skill_id"] = int(m.group(1))
                self.in_name_a = True
        if tag == "em" and self.in_row:
            self.in_em = True
        if tag == "u" and self.in_row:
            self.cur["stigma"] = True

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_name_a = False
        if tag == "em":
            self.in_em = False
        if tag == "td" and self.in_td:
            text = " ".join("".join(self.buf).split())
            if self.cell == 2:
                self.cur["type"] = text
            elif self.cell == 3:
                self.cur["cost"] = text
            elif self.cell == 4:
                self.cur["cast"] = text
            elif self.cell == 5:
                self.cur["cd"] = text
            self.in_td = False
        if tag == "tr" and self.in_row:
            self.in_row = False
            if self.cur and self.cur.get("name") and self.cur.get("type"):
                self.rows.append(self.cur)
            self.cur = None

    def handle_data(self, data):
        if not self.cur:
            return
        if self.in_name_a:
            self.cur["name"] += data
            return
        if self.in_em and self.cell == 1:
            self.cur["en"] += data
            return
        if self.in_td:
            self.buf.append(data)
            if "Асмодиан" in data:
                self.cur["race"] = "asmo"
            if "Элийц" in data:
                self.cur["race"] = "elyos"


def split_rank(name: str) -> tuple[str, int]:
    name = re.sub(r"^\[Древняя стигма\]\s*", "", name.strip())
    m = RANK_RE.search(name)
    if not m:
        return name, 1
    return name[: m.start()].strip(), ROMAN.get(m.group(1), 1)


def parse() -> list[dict]:
    html = HTML_PATH.read_text(encoding="cp1251")
    p = TableParser()
    p.feed(html)
    best: dict[str, dict] = {}
    for row in p.rows:
        if row["type"] != "Активный":
            continue
        name = " ".join(row["name"].split())
        en = " ".join(row["en"].split())
        base, rank = split_rank(name)
        en_base, _ = split_rank(en) if en else (en, 1)
        if not base or base in ("#", "Название"):
            continue
        rec = {
            **row,
            "name": name,
            "en": en,
            "base": base,
            "en_base": en_base,
            "rank": rank,
            "ancient": base.startswith("[") or "Древняя" in name or "Ancestral" in en,
        }
        key = (base, rec["race"] or "")
        prev = best.get(key)
        if prev is None or (rank, rec["level"]) >= (prev["rank"], prev["level"]):
            best[key] = rec
    return [best[k] for k in sorted(best, key=lambda x: (best[x]["level"], best[x]["base"]))]


def download_icon(filename: str, dest: Path) -> bool:
    url = BASE + "uploads/item_icon/" + filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
            data = r.read()
            ctype = r.headers.get("Content-Type", "")
        if len(data) < 80 or "html" in ctype:
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print("fail", filename, e)
        return False


def main() -> None:
    skills = parse()
    OUT_JSON.write_text(json.dumps(skills, ensure_ascii=False, indent=2), encoding="utf-8")
    print("max active", len(skills))
    for s in skills:
        mark = " STIGMA" if s["stigma"] else ""
        race = f" [{s['race']}]" if s["race"] else ""
        print(f"L{s['level']:02} R{s['rank']:02} {s['base']:42} {s['cd']:10} {s['en_base']:28} {s['icon']}{mark}{race}")


if __name__ == "__main__":
    main()
