"""Fetch aidb.ru skill_info pages: description, range, CD, crowd-control states."""
from __future__ import annotations

import json
import re
import ssl
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_skills import NAME_TO_ID, cd_short, js_str
from client_skill_stats import MAG_STATUS_TAG, load_cached_stats, maybe_fill_desc, with_stats

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "tools" / "aidb_skills.json"
DETAILS_PATH = ROOT / "tools" / "aidb_details.json"
SKILLS_JS = ROOT / "js" / "skills.js"
BASE = "https://aidb.ru/?aion=skill_info&id="
CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 aion-assassin-planner"}

SCOUT_IDS = {
    3512: "fastReturn",
    1801: "returnHome",
    572: "focusedEvasion",
    1803: "bandage",
    577: "ritual",
}

POTIONS = {
    "curePotion": {
        "desc": "Снимает негативные эффекты.",
        "range": "на себя",
        "cd": "10 с",
        "cc": [],
    },
    "recoverySerum": {
        "desc": "Восстанавливает 1940 HP и 1680 MP.",
        "range": "на себя",
        "cd": "10 с",
        "cc": [],
    },
    "manaSerum": {
        "desc": "Восстанавливает 3450 MP. За очки бездны.",
        "range": "на себя",
        "cd": "10 с",
        "cc": [],
    },
    "lifeSerum": {
        "desc": "Восстанавливает 3680 HP. За очки бездны.",
        "range": "на себя",
        "cd": "10 с",
        "cc": [],
    },
}

FIELD_RE = re.compile(r"<b>([^<]+):&nbsp;</b></td><td[^>]*>(.*?)</td>", re.S)
RANGE_RES = [
    re.compile(r"радиус действия:\s*(\d+)\s*м", re.I),
    re.compile(r"в радиусе\s*(\d+)\s*м", re.I),
    re.compile(r"на расстоянии\s*(\d+)\s*м", re.I),
]


def extract_range(desc: str, target: str) -> str:
    for rx in RANGE_RES:
        m = rx.search(desc or "")
        if m:
            return f"{m.group(1)} м"
    t = (target or "").lower()
    if "персонаж" in t:
        return "на себя"
    return "ближний"


def extract_cc(desc: str) -> list[str]:
    text = desc or ""
    if re.search(
        r"снимает со своего|отменяет все наложенн|сопротивляемость к|сопротивление оглуш",
        text,
        re.I,
    ):
        return []
    found: list[str] = []
    if re.search(r"оглушает|оглушить", text, re.I):
        found.append("Стан")
    if re.search(r"опрокидывает", text, re.I):
        found.append("Опрокидывание")
    if re.search(r"отталкивает|отбрасывает", text, re.I):
        found.append("Отталкивание")
    if re.search(r"накладывает на нее воздушные оковы|накладывает на неё воздушные оковы", text, re.I):
        found.append("Воздушные оковы")
    elif re.search(r"накладывает на нее оковы|накладывает на неё оковы", text, re.I):
        found.append("Оковы")
    if re.search(r"немот", text, re.I):
        found.append("Немота")
    if re.search(r"состояние spin|(?<![а-яА-Я])вращает", text, re.I):
        found.append("Вращение")
    return found


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return " ".join(text.split())


def parse_fields(html: str) -> dict[str, str]:
    out = {}
    for m in FIELD_RE.finditer(html):
        out[m.group(1).strip()] = strip_html(m.group(2))
    return out


def fetch_html(skill_id: int) -> str:
    req = urllib.request.Request(BASE + str(skill_id), headers=UA)
    last_err = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
                return r.read().decode("cp1251", errors="replace")
        except Exception as e:
            last_err = e
            time.sleep(0.4)
    raise RuntimeError(f"id={skill_id}: {last_err}")


def parse_page(html: str) -> dict:
    fields = parse_fields(html)
    desc = fields.get("Описание") or ""
    target = fields.get("Цель") or ""
    cd_raw = fields.get("Время перезарядки") or ""
    return {
        "desc": desc,
        "target": target,
        "cd": cd_short(cd_raw) if cd_raw else "",
        "range": extract_range(desc, target),
        "cc": extract_cc(desc),
        "category": fields.get("Категория") or "",
    }


def id_map() -> dict[int, str]:
    mapping = dict(SCOUT_IDS)
    rows = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for rec in rows:
        sid = NAME_TO_ID.get(rec["base"])
        if not sid or not rec.get("skill_id"):
            continue
        if sid == "slayerForm":
            sid = "slayerElyos" if rec.get("race") == "elyos" else "slayerAsmo"
        mapping[int(rec["skill_id"])] = sid
    return mapping


def load_details() -> dict:
    if DETAILS_PATH.exists():
        return json.loads(DETAILS_PATH.read_text(encoding="utf-8"))
    return {}


def refresh_derived(details: dict) -> dict:
    for page in details.values():
        page["range"] = extract_range(page.get("desc") or "", page.get("target") or "")
        page["cc"] = extract_cc(page.get("desc") or "")
    DETAILS_PATH.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    return details


def fetch_all() -> dict:
    mapping = id_map()
    details = load_details()
    missing = [i for i in mapping if mapping[i] not in details]
    print("need fetch", len(missing), "cached", len(details))
    if missing:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(fetch_html, i): i for i in missing}
            for fut in as_completed(futs):
                skill_id = futs[fut]
                sid = mapping[skill_id]
                try:
                    page = parse_page(fut.result())
                    page["skill_id"] = skill_id
                    details[sid] = page
                    print("ok", sid, page["range"], page["cd"], ",".join(page["cc"]) or "-")
                except Exception as e:
                    print("FAIL", sid, skill_id, e)
    return refresh_derived(details)


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


def apply_safe(details: dict) -> None:
    text = SKILLS_JS.read_text(encoding="utf-8")
    missing = []
    client_stats = load_cached_stats()

    def repl(m: re.Match) -> str:
        sid, name, kind = m.group(1), m.group(2), m.group(3)
        src = details.get(sid) or POTIONS.get(sid)
        if not src:
            missing.append(sid)
            return m.group(0)
        desc = with_stats(maybe_fill_desc(sid, src["desc"]), client_stats.get(sid))
        cd = src["cd"] or "—"
        st = client_stats.get(sid) or {}
        tags = skill_tags(
            src.get("range") or "ближний",
            src.get("cd") or "",
            src.get("cc") or [],
            bool(st.get("mag_status")),
        )
        tag_js = ", ".join(js_str(t) for t in tags)
        return (
            f"  {sid}: {{\n"
            f"    name: {js_str(name)},\n"
            f"    kind: {js_str(kind)},\n"
            f"    tags: [{tag_js}],\n"
            f"    desc: {js_str(desc)},\n"
            f"    cd: {js_str(cd)},"
        )

    new, n = re.subn(
        r"  (\w+): \{\s*name: \"([^\"]+)\",\s*kind: \"([^\"]+)\",\s*tags: \[.*?\],\s*desc: \".*?\",\s*cd: \"[^\"]+\",",
        repl,
        text,
        flags=re.S,
    )
    if missing:
        print("kept old (no aidb)", ", ".join(missing))
    SKILLS_JS.write_text(new, encoding="utf-8")
    print("updated skills", n, SKILLS_JS)


def main() -> None:
    details = fetch_all()
    apply_safe(details)


if __name__ == "__main__":
    main()
