"""Planner static files + /api/state for the agent and the Save button.

GET    /api/state   current board + binds
PUT    /api/state   replace whole document
POST   /api/state   same as PUT (UI save)
PATCH  /api/state   partial edit:

  {"race": "asmo"}
  {"class": "ranger"}
  {"multirace": true}
  {"slot": {"tier": "normal", "index": 0, "id": "fog"}}   # id null = clear
  {"bind": {"layer": "combat", "key": "KeyF", "id": "stigma"}}  # id null = unbind
  {"stigmas": {"normal": [...], "greater": [...]}}
  {"binds": {"combat": {"KeyB": null}}}
"""
from __future__ import annotations

import json
import re
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "local-state.json"
PORT = 46462
SLOTS = {"normal": 6, "greater": 6}


def now_ms() -> int:
    return int(time.time() * 1000)


def skill_names() -> dict[str, str]:
    text = (ROOT / "js" / "skills.js").read_text(encoding="utf-8")
    return dict(re.findall(r"^\s+(\w+): \{\s*\n\s*name: \"([^\"]+)\"", text, re.M))


def stigma_tiers() -> dict[str, str]:
    text = (ROOT / "js" / "skills.js").read_text(encoding="utf-8")
    block = re.search(r"const STIGMA_TIER = \{([\s\S]*?)\n\};", text)
    if not block:
        return {}
    return dict(re.findall(r"(\w+):\s*\"(normal|greater)\"", block.group(1)))


def pad_row(row, n: int) -> list:
    src = list(row or [])
    out = []
    for i in range(n):
        val = src[i] if i < len(src) else None
        out.append(val or None)
    return out


CLASSES = {
    "gladiator",
    "templar",
    "assassin",
    "ranger",
    "sorcerer",
    "spiritmaster",
    "cleric",
    "chanter",
}


def empty_bar_slots():
    return [None] * 12


def clean_qb_ref(ref):
    if not isinstance(ref, dict):
        return None
    layer = ref.get("layer")
    key = ref.get("key")
    if layer not in ("combat", "shift", "ctrl"):
        return None
    if not isinstance(key, str) or not key or key in ("KeyW", "KeyS"):
        return None
    return {"layer": layer, "key": key}


def pad_bar_slots(arr):
    src = list(arr or [])
    out = []
    for i in range(12):
        out.append(clean_qb_ref(src[i] if i < len(src) else None))
    return out


def extra_layout(mode):
    try:
        n = int(mode)
    except (TypeError, ValueError):
        n = 0
    m = n if n in (1, 2, 3) else 0
    return m, (90 if m % 2 else 0), (2 if m >= 2 else 1)


def extra_mode_from_rot_rows(rot, rows):
    return extra_layout((0 if rows == 1 else 2) + (1 if rot == 90 else 0))[0]


def read_extra_mode(q, prefix):
    if not isinstance(q, dict):
        return extra_layout(2)[0]
    raw = q.get(prefix + "mode")
    if raw is not None:
        try:
            n = int(raw)
        except (TypeError, ValueError):
            n = None
        if n in (0, 1, 2, 3):
            return n
    rot = 90 if q.get(prefix + "rot") == 90 else 0
    rows = 1 if q.get(prefix + "rows") == 1 else 2
    return extra_mode_from_rot_rows(rot, rows)


def pad_quickbar(q) -> dict:
    extra1mode = 2
    extra2mode = 2
    siderot = 90
    siderows = 1
    bars_src = {}
    if isinstance(q, dict):
        extra1mode = read_extra_mode(q, "extra1")
        extra2mode = read_extra_mode(q, "extra2")
        siderot = 90
        siderows = 1
        if isinstance(q.get("bars"), dict):
            bars_src = q["bars"]
        else:
            bars_src = q
    extra1mode, extra1rot, extra1rows = extra_layout(extra1mode)
    extra2mode, extra2rot, extra2rows = extra_layout(extra2mode)
    bars = {
        "main": pad_bar_slots(bars_src.get("main")),
        "bar2": pad_bar_slots(bars_src.get("bar2")),
        "bar3": pad_bar_slots(bars_src.get("bar3")),
        "extra1": pad_bar_slots(bars_src.get("extra1")),
        "extra2": pad_bar_slots(bars_src.get("extra2")),
        "side": pad_bar_slots(bars_src.get("side")),
    }
    return {
        "extra1mode": extra1mode,
        "extra2mode": extra2mode,
        "extra1rot": extra1rot,
        "extra2rot": extra2rot,
        "extra1rows": extra1rows,
        "extra2rows": extra2rows,
        "siderot": siderot,
        "siderows": siderows,
        "bars": bars,
    }


def normalize(data: dict) -> dict:
    names = skill_names()
    stigmas = data.get("stigmas") or {}
    normal = pad_row(stigmas.get("normal"), SLOTS["normal"])
    greater = pad_row(stigmas.get("greater"), SLOTS["greater"])
    binds = data.get("binds") or {}
    race = "elyos" if data.get("race") == "elyos" else "asmo"
    cls = data.get("class") if data.get("class") in CLASSES else "assassin"
    by_class = data.get("byClass") if isinstance(data.get("byClass"), dict) else {}
    return {
        "class": cls,
        "race": race,
        "multirace": bool(data.get("multirace")),
        "stigmas": {"normal": normal, "greater": greater},
        "stigmaNames": {
            "normal": [names.get(i) if i else None for i in normal],
            "greater": [names.get(i) if i else None for i in greater],
        },
        "binds": {
            "combat": dict(binds.get("combat") or {}),
            "shift": dict(binds.get("shift") or {}),
            "ctrl": dict(binds.get("ctrl") or {}),
        },
        "quickbar": pad_quickbar(data.get("quickbar")),
        "byClass": by_class,
        "updatedAt": int(data.get("updatedAt") or now_ms()),
        "source": data.get("source") or "api",
    }


def read_state() -> dict | None:
    if not STATE.exists():
        return None
    try:
        return normalize(json.loads(STATE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return None


def write_state(data: dict) -> dict:
    out = normalize(data)
    STATE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def can_put(sid: str | None, tier: str) -> bool:
    if not sid:
        return True
    need = stigma_tiers().get(sid)
    if not need:
        return False
    if need == "greater":
        return tier == "greater"
    return True


def apply_patch(cur: dict, patch: dict) -> dict:
    data = json.loads(json.dumps(cur))
    if "race" in patch:
        data["race"] = patch["race"]
    if "class" in patch:
        data["class"] = patch["class"]
    if "multirace" in patch:
        data["multirace"] = bool(patch["multirace"])
    if "stigmas" in patch:
        src = patch["stigmas"] or {}
        if "normal" in src:
            data["stigmas"]["normal"] = pad_row(src["normal"], SLOTS["normal"])
        if "greater" in src:
            data["stigmas"]["greater"] = pad_row(src["greater"], SLOTS["greater"])
    if "binds" in patch:
        for layer in ("combat", "shift", "ctrl"):
            if layer not in (patch["binds"] or {}):
                continue
            layer_map = data["binds"].setdefault(layer, {})
            for key, sid in (patch["binds"][layer] or {}).items():
                if sid:
                    layer_map[key] = sid
                else:
                    layer_map.pop(key, None)
    if "quickbar" in patch:
        data["quickbar"] = pad_quickbar(patch["quickbar"])
    slot = patch.get("slot")
    if slot:
        tier = slot.get("tier")
        index = int(slot.get("index", -1))
        if tier not in SLOTS or not 0 <= index < SLOTS[tier]:
            raise ValueError("bad slot")
        sid = slot.get("id") or None
        if sid and not can_put(sid, tier):
            raise ValueError(f"{sid} cannot go in {tier} slot")
        if sid:
            for t in SLOTS:
                row = data["stigmas"][t]
                data["stigmas"][t] = [None if x == sid else x for x in row]
        data["stigmas"][tier][index] = sid
    bind = patch.get("bind")
    if bind:
        layer = bind.get("layer")
        key = bind.get("key")
        if layer not in ("combat", "shift", "ctrl") or not key:
            raise ValueError("bad bind")
        sid = bind.get("id") or None
        layer_map = data["binds"].setdefault(layer, {})
        if sid:
            for k, v in list(layer_map.items()):
                if v == sid:
                    del layer_map[k]
            layer_map[key] = sid
        else:
            layer_map.pop(key, None)
    data["updatedAt"] = now_ms()
    data["source"] = patch.get("source") or "api"
    return data


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def send_json(self, payload, code=200):
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def api_path(self) -> str:
        return urlparse(self.path).path.rstrip("/")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        if self.api_path() != "/api/state":
            super().do_GET()
            return
        try:
            data = read_state()
            if data is None:
                self.send_json({"empty": True}, 404)
                return
            self.send_json(data)
        except Exception:
            import traceback

            traceback.print_exc()
            self.send_json({"error": "internal"}, 500)

    def do_PUT(self):
        self.write_body()

    def do_POST(self):
        self.write_body()

    def write_body(self):
        if self.api_path() != "/api/state":
            self.send_error(404)
            return
        try:
            incoming = self.read_json()
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json({"error": "invalid json"}, 400)
            return
        incoming.setdefault("updatedAt", now_ms())
        incoming.setdefault("source", "ui")
        out = write_state(incoming)
        print("saved", STATE.name, out.get("source"), flush=True)
        self.send_json(out)

    def do_PATCH(self):
        if self.api_path() != "/api/state":
            self.send_error(404)
            return
        try:
            patch = self.read_json()
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json({"error": "invalid json"}, 400)
            return
        cur = read_state()
        if cur is None:
            cur = normalize({"source": "api"})
        try:
            nxt = apply_patch(cur, patch)
        except (ValueError, TypeError, KeyError) as e:
            self.send_json({"error": str(e)}, 400)
            return
        out = write_state(nxt)
        print("patch", STATE.name, flush=True)
        self.send_json(out)

    def log_message(self, fmt, *args):
        path = args[0] if args else ""
        if "/api/state" in str(path):
            super().log_message(fmt, *args)


def main() -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"http://127.0.0.1:{PORT}/  GET/PUT/PATCH /api/state -> {STATE}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
