# Aion 4.6 — раскладка клавиш / keybind planner

Статический планировщик клавиш и панелей для **Aion Origin 4.6** (уровень 65).  
Static keybind and HUD planner for **Aion Origin 4.6** (level 65).

---

## Русский

Планировщик для восьми классов: **гладиатор, страж, убийца, стрелок, волшебник, заклинатель, целитель, чародей**.

Вкладки: **Раскладка** (клавиатура и мышь), **Панели** (HUD как в клиенте), **Стигмы**. Старт пустой: бинды и стигмы не подставляются.

### Запуск

```bash
python tools/serve.py
```

Обычно: [http://127.0.0.1:46462/](http://127.0.0.1:46462/)

Нужен Python 3. Нужны файлы приложения: `index.html`, `css/`, `js/`, `img/`.

**Сохранить** пишет состояние на сервер (`local-state.json`, в git не входит) и в `localStorage`. **Поделиться** копирует ссылку с раскладкой в URL.

### Данные клиента

Имена, статы и иконки умений взяты из клиента Origin (`skills.pak` и связанные пакеты). Регенерация `js/skills.js` — локально, через распаковку в `tools/encdec/` (этот каталог в репозиторий не кладут).


---

## English

Planner for eight classes: **Gladiator, Templar, Assassin, Ranger, Sorcerer, Spiritmaster, Cleric, Chanter**.

Tabs: **Раскладка** (keyboard and mouse), **Панели** (in-game-style HUD), **Стигмы**. The board starts empty: no invented default binds or stigma presets.

### Run

```bash
python tools/serve.py
```

Typical URL: [http://127.0.0.1:46462/](http://127.0.0.1:46462/)

Python 3. Serve the app files: `index.html`, `css/`, `js/`, `img/`.

**Сохранить** writes state to the server (`local-state.json`, gitignored) and `localStorage`. **Поделиться** copies a share URL with the layout encoded.

### Client data

Skill names, combat stats, and icons come from the Origin client (`skills.pak` and related packs). Regenerating `js/skills.js` is a local step that unpacks into `tools/encdec/` (not committed).

