# Changelog

All notable changes to DropPoint+ are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Releases are tagged `vX.Y.Z` in git; the canonical version lives in
`droppointplus/__init__.py` (`__version__`).

## [Unreleased]

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
