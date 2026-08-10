# DropPoint+

> **Make Drag 'n' Drop easier** — a modern, lightweight rebuild of
> [DropPoint](https://github.com/GameGodS3/DropPoint) in **Python + PySide6 (Qt6)**.

DropPoint+ is a desktop utility for collecting files and folders through
drag-and-drop, then quickly copying or moving them to a destination — without
tiling two windows side-by-side. It keeps the exact workflow of the original:
summon a small floating shelf, drop files in, drag them out where you want
them — even across virtual desktops and over fullscreen apps.

Works on **Windows**, **Linux** and **macOS**.

---

## Why DropPoint+? (DropPoint already exists)

DropPoint is a great little app — a single developer's idea that works, used
by thousands. So why rebuild it from scratch?

**1. The original went quiet.** DropPoint's last commit was July 2023, with
several open issues and planned features that never shipped: **move mode**
(delete sources after drag-out), **configurable shortcuts** (the old one was
hard-coded to `Shift+Capslock` and needed a restart to change), and the
**instance history** feature that existed but was disabled due to a broken
relative-path bug.

**2. It deserved a lighter engine.** The original bundles Electron — a full
Chromium + Node runtime — to render a 200×200 window. DropPoint+ is a single
native process built on **PySide6 (Qt6)**: dramatically smaller, faster to
start, and it drops the entire web surface (`nodeIntegration`, preload,
IPC, contextBridge) by construction — one whole class of security issues
simply cannot exist.

**3. The backlog became the feature set.** DropPoint+ implements what the
original planned but never landed:

| DropPoint backlog | Status in DropPoint+ |
|---|---|
| Move mode (#9/#45) | ✅ delete sources after a completed drag-out, on a background thread with progress |
| Configurable shortcuts (#52/#42) | ✅ any shortcut, re-registered live without restart |
| Instance file history | ✅ re-enabled, stable `%APPDATA%` path, tray History submenu |
| Fixed 200×200 non-draggable window | ✅ 360×450 draggable shelf |

**4. A fresh UI.** DropPoint+ follows a modern dark design system (from the
project's own `ui design/` briefs) — a compact floating window with a header,
a dashed drop zone that highlights when you drag over it, and a live item
counter.

In short: **DropPoint+ is a from-scratch, GPL-compliant continuation of
DropPoint's idea** — same soul, new engine, and the features the community
kept asking for.

---

## Features

- **Floating shelf windows** — frameless, translucent, always-on-top,
  multi-instance, and **draggable** (grab the header or the empty area)
- **Drag files in** from anywhere, **drag them back out** anywhere — across
  virtual desktops and fullscreen apps
- **Copy or Move** — `drag_action` setting; move mode deletes sources on a
  background worker thread with a progress bar on the shelf
- **Configurable global hotkey** (`Shift+Capslock` by default on
  Windows/Linux, `Shift+Tab` on macOS) — live-rebinding from Settings
- **System tray** — New Instance / Settings / Quit + **History** submenu
  (last 5 drops)
- **Settings gear right on the shelf**, plus a schema-driven Settings dialog:
  spawn on launch, always on top, open at cursor, shortcut behaviour, drag
  action, debug
- **Collection list view** — the holding state becomes a `COLLECTION / N
  items` roster: per-row type icon, name, size, and **✕ remove**; scrolls
  with wheel or touchpad once it overflows
- **Clear all** button in the footer (and `Esc`) to empty the shelf
- Per-file-type icons, dark Material-inspired theme with all colors
  centralized in `colors.py`
- Clean **MVVM** architecture: `View → ViewModel → Service`, dependency
  injection, event-driven signals, background operations off the UI thread

## Usage

1. Press the hotkey (or tray → New Instance) to open a shelf.
2. **Drag files/folders in** from any app — they collect on the shelf.
   Duplicates are skipped; the footer shows the item count.
3. Go to your destination and **drag them out** of the shelf.
   - Hold **Shift** at the destination to force a move, **Ctrl** to force a
     copy (Explorer behavior).
   - With **Drag-out behaviour = Move**, sources are deleted after the drop
     (progress bar shown); Esc cancels and keeps the shelf.
4. **Esc** clears the shelf; **✕** closes it; the gear opens Settings.

## Requirements

- Python 3.12+ (3.14 recommended; PySide6 6.8+ ships cp314 wheels)

## Run it (development)

```bash
git clone <this-repo>
cd DroppointPlus
python -m venv .venv
# Windows (bash):  source .venv/Scripts/activate
# Windows (cmd):   .venv\Scripts\activate
# macOS / Linux:   source .venv/bin/activate
pip install -r requirements.txt
python -m droppointplus
```

## Project layout

```
droppointplus/
├── main.py              # entry point
├── app_config.py        # schema + defaults + ConfigManager
├── colors.py            # design tokens — the one place every colour lives
├── file_service.py      # drag mechanics + background delete worker (infrastructure)
├── shelf_view_model.py  # shelf state + orchestration (application)
├── shelf_window.py      # the shelf widget — pure View
├── windows.py           # WindowManager: instance registry + toggle/spawn
├── tray.py              # system tray + History submenu
├── hotkey.py            # global hotkey (native Win32 ctypes)
├── settings_dialog.py   # schema-driven settings
├── icons.py             # file-type icons (assets reused from DropPoint)
├── history.py           # instance history (re-enabled, fixed path)
├── widgets/             # reusable DropZone, FileCard, ProgressWidget
└── resources/icons/     # assets reused from the original project
```

The full migration plan (Electron → Qt6) lives in
[`MIGRATION_PLAN.md`](MIGRATION_PLAN.md). The original Electron codebase is
the behavioural reference, upstream at
[GameGodS3/DropPoint](https://github.com/GameGodS3/DropPoint).

## Versioning

DropPoint+ follows [Semantic Versioning](https://semver.org/) (SemVer):
`MAJOR.MINOR.PATCH`.

- `MAJOR` — incompatible/breaking changes
- `MINOR` — backwards-compatible features
- `PATCH` — backwards-compatible fixes

Releases are tagged `vX.Y.Z` in git and listed in
[`CHANGELOG.md`](CHANGELOG.md) (Keep a Changelog format). The canonical
version is the `__version__` attribute in `droppointplus/__init__.py`;
`pyproject.toml` reads it dynamically, so there is exactly one place to
bump.

---

## Credits

DropPoint+ would not exist without the original project. All credit for the
**idea, the workflow, the icon assets, and the initial concept** goes to its
original creator:

- **Sudev Suresh Sreedevi** ([GameGodS3](https://github.com/GameGodS3),
  sudevssuresh@gmail.com) — the brilliant mind behind
  [DropPoint](https://github.com/GameGodS3/DropPoint). Buy him a coffee:
  [buymeacoffee.com/sudev](https://www.buymeacoffee.com/sudev)
- **Ajay Krishna KV** ([AJAYK-01](https://github.com/AJAYK-01)) — CI/CD and
  releases for the original DropPoint
- **Fluent icons from [Icons8](https://icons8.com)** — file-type icon assets
  reused in DropPoint+
- Project inspired by the macOS app [Dropover](https://dropoverapp.com)

DropPoint+ is a **from-scratch rewrite**: none of the original source code
was copied, but its feature set, workflow, and icon assets are carried over
under the same GPL license — with thanks and full attribution above.

## License

**GPL-3.0-or-later.** DropPoint+ is a derivative work of the original
DropPoint project (GPL-3.0-or-later) and must stay under the same license.
The icon assets in `resources/icons/` are reused from DropPoint under that
license. See [`LICENSE`](LICENSE).
