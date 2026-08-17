# Changelog

All notable changes to DropPoint+ are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Releases are tagged `vX.Y.Z` in git; the canonical version lives in
`droppointplus/__init__.py` (`__version__`).

## [Unreleased]

## [0.4.0] - 2026-08-17

### Fixed

- The marching drop-zone border animation now stops when a shelf is hidden
  or closed and restarts on show, so no infinite animation timer outlives
  the window — saves CPU on auto-hidden shelves and removes a teardown-crash
  source.
- Smoke tests flush Qt's deferred deletions after every test, guarding the
  historic flaky Ubuntu CI teardown.

### Added

- **Summon-on-drag** — the shelf now appears automatically while you drag
  files, no hotkey or tray click needed:
  - a Windows global mouse hook (`drag_detect.py`) detects a file drag
    anywhere on the desktop (left button + movement + a non-standard drag
    cursor, the signature Explorer/OLE uses) and reveals a shelf at the
    cursor;
  - invisible always-on-top **edge strips** on every screen catch file
    drags at the screen edge and dock the shelf there (a deliberate, 100%
    reliable gesture; idle strips are click-through on Windows so they never
    block the screen edge);
  - the shelf **reuses** an existing idle instance when one exists and only
    spawns when none does, and after the drag ends it **auto-hides** quickly
    and then **closes completely** ~1 s later (unless files were dropped into
    it, in which case it stays open as a normal instance);
  - dropping directly on an edge strip collects the files like a normal
    drop;
  - new **"Show shelf when dragging files"** setting (default on), toggled
    live from Settings; strips work on macOS/Linux too, the anywhere-detector
    is Windows-only (no OS mechanism exists on Wayland).
- **Animated drop-zone border** — the shelf's dashed border now marches
  around the drop zone (marching-ants style), gently while idle and faster
  while a drag hovers (the existing purple glow still pulses on drag-over);
  repaints are quantized so an idle shelf stays cheap.

## [0.3.0] - 2026-08-16

### Added

- **Real live transfer progress** — the copy/move worker now emits byte
  progress every ~0.5 s while bytes stream (plus a final emit), and moves
  report per-item progress, so the shelf's progress bar, speed and ETA update
  during the transfer instead of jumping 0 → 100 % at the end.
- **History window** — a new clock button on the shelf header opens a
  full History panel listing the last 10 instances and their collected files
  (the tray's History submenu stays as the quick view).
- **Shared dark panel chrome** (`widgets/panel_mixin.py`) — the Settings and
  History windows now use the same frameless, translucent, rounded design as
  the shelf, with a draggable header and close button.
- **Settings dialog restyled** to match the shelf design language: dark
  inputs, purple focus rings, primary Apply button, footer toast.
- **Phase 4 packaging** — a reproducible PyInstaller spec, a Windows NSIS
  installer script, a Linux AppImage build script, a GitHub Actions matrix
  (test + build on Windows/macOS/Linux) and a first pytest smoke suite.

### Fixed

- Settings/History windows opened **below** the always-on-top shelf and were
  unreachable: the panels now carry `WindowStaysOnTopHint` when "Always on
  top" is enabled (and respect it when disabled).
- **Tray Quit did nothing**: the Quit action is now kept by an explicit
  reference (`setContextMenu` takes no ownership) and the quit is deferred
  one event-loop turn so the native Windows tray menu cannot swallow it.
- **Packaged exe failed to boot** with `attempted relative import with no
  known parent package`: a root `launcher.py` entry point imports the package
  absolutely, and the PyInstaller spec uses it.

## [0.2.0] - 2026-08-10

### Added

- **COPY / MOVE to a chosen destination** — the footer gains **COPY** (filled)
  and **MOVE** (outline) actions that open a destination picker, so collected
  files can be transferred without leaving the shelf:
  - `destination_dialog.py` — the picker lists **FAVORITES** (Desktop /
    Downloads / Documents / Pictures + user-pinned folders) and **RECENT**
    destinations, filters them live as you type, accepts a typed folder
    path directly, and offers a Browse… chooser.
  - `TransferWorker` (QThread) — copy and move run off the UI thread with
    byte-level progress (`done / total`), live speed and ETA; duplicates at
    the destination are auto-renamed (`file (1).ext`), never overwritten.
  - The shelf shows a progress overlay (bar + detail line + **Cancel**),
    then a success panel with **Open destination** / **Done**.
  - Favourites and recent destinations persist in the config
    (`favorites`, `recent_destinations` keys).
  - Cancel is cooperative: completed items stay transferred, the rest stay
    in the collection.

### Fixed

- Scrolled collection rows painted over the `COLLECTION / N items` header and
  the bottom hint: rows now live in a masked viewport clipped to the band
  between the two labels.

## [0.1.1] - 2026-08-10

### Fixed

- Collection list scrolled only one way with smooth-scroll mice: fractional
  wheel notches (e.g. +/-40 instead of +/-120) truncated upward scrolling to
  zero. Wheel deltas are now scaled in a single division, so up and down
  scroll symmetrically.

### Changed

- Folder rows in the collection list no longer show a size — only files do.
- README, migration plan and the package docstring now point at the upstream
  GameGodS3/DropPoint repository instead of the removed local
  `Droppoint-old/` folder.

## [0.1.0] - 2026-08-10

First milestone — the complete core DropPoint workflow, rebuilt from scratch
in PySide6 (Qt6) as a single native process (no Electron, no renderer, no IPC).

### Added

- **Floating drop-zone shelf** (360×450, frameless, draggable, always-on-top)
  replicating the `empty_drop_zone` mockup: brand header, dashed drop zone that
  glows purple while dragging, footer with a live item count, dark Material-3
  theme from a single `colors.py` token module.
- **Drag-in / drag-out**: collect multiple files and folders from Explorer,
  drag the whole collection out to any destination — copy (default) or move.
- **Move mode**: sources are deleted on a background `QThread` worker with a
  live progress overlay; per-file failures are logged, never fatal.
- **Collection list view** (holding state): `COLLECTION / N items` roster with
  per-row type icon, name, size and ✕ remove; wheel + touchpad scrolling with a
  scroll indicator.
- **Clear all** button (footer) and `Esc` shortcut to empty the shelf.
- **Multi-instance**: spawn extra shelves with the global shortcut
  (Shift+Capslock default, reconfigurable live from Settings).
- **System tray** with menu and history submenu (last drops).
- **Settings dialog** (gear on the shelf or tray): drag action, shortcut,
  always-on-top, spawn on launch, open at cursor, debug logging.
- **Instance history** persisted to `%APPDATA%`.
- **GPL-3.0-or-later licensing** with attribution to the original DropPoint
  developers (see README).

### Changed

- Window made draggable (global-coordinate drag, no painted shadow) and sized
  to the design mockup.
- Hint text and collection roster layouts fixed for the 360×450 window.

### Fixed

- Crash on close-button click (`Internal C++ object already deleted`) — the
  header buttons now emit last and consume the event.
- Non-smooth window drag (was using window-local positions).
- Stale rows in the collection list after Clear all.
