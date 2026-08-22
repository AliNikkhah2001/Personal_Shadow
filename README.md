# 🕵️‍♂️ Sherlock Holmes Mind Palace

A cross-platform productivity, deductive analytics, and 3D spatial knowledge management system.

![Version](https://img.shields.io/badge/version-2.2.0-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![React](https://img.shields.io/badge/react-18.0+-61dafb)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Ruff](https://img.shields.io/badge/linter-ruff-orange)

## 📋 Table of Contents
- [Overview](#-overview)
- [Changelog](#-changelog)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Current Features](#-current-features)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Development](#-development)
- [Testing](#-testing)
- [Roadmap](#-roadmap)

## 🔎 Overview

The **Sherlock Holmes Mind Palace** is the ultimate convergence of a "Second Brain" and the "Method of Loci." Built with a lightning-fast **PyQt6** backend and a glassmorphism **React/JSX** frontend, it acts as a centralized operating system for your intellectual and physical life.

It is designed to seamlessly track your focus, map your knowledge spatially, analyze your behavioral data deductively, and synchronize perfectly across all your devices using peer-to-peer GitHub node architectures.

## 📝 Changelog

### v2.2.0 — Unified Sync, 3D Bookshelf, Markdown Studio & FileSharing Hardening
- **Timer — clock freeze fixed**: `_handle_stop_timer` now resets `time_left` to `total_time` (was `0`), display no longer stuck at `00:00` after stop; queue status cleared only for running sessions (`bridge/session.py:171`).
- **Timeline — distractions vs pauses**: Overlays now use type-colored hatched bars + white borders (orange=App, red=Camera, yellow=Manual) and a legend; visible on both live and history tracks (`frontend/scripts/components/timer.js`).
- **3D Bookshelf tab**: Ported Mint **Complete Shelf** (Three.js r160, 19 procedural hardcovers) to vanilla JS under `frontend/shelf/`; iframe view with `importmap` via jsDelivr, cached `three.module.js`/`three.min.js` + addons via splash-screen, `outputEncoding→outputColorSpace`/`sRGBEncoding→SRGBColorSpace` compat, nav tab `Bookshelf` (`frontend/shelf/*`, `frontend/scripts/app.js:386`).
- **Markdown Studio tab**: New `Markdown Editor` with live preview (markdown-it + footnote/table plugins, cached at startup), split/edit/preview modes, open/save `.md`, **Save as HTML** (self-contained) and **Save as PDF** (print dialog) (`frontend/scripts/components/markdown-editor.js`, `frontend/index.html`).
- **FileSharing — unified view**: `get_merged_folder_hierarchy` merges local + all remote device trees recursively, `devices[]` per node, friendly display names (`MindPalace Library` vs raw path), single merged entry per folder name via `get_network_folders()` (`handlers/filesharing.py:38`, `sync_manager.py:680`, `frontend/scripts/components/filesharing.js:176`).
- **FileSharing — stability**: Guarded `node.devices||[]`, `networkNodes&&`, fixed `_merge_trees` dropping local-only children, fixed duplicate `_merge_child` dead-code, hardened `_build_tree` to `max_depth=2/3` + `OSError/RecursionError` guards and `has_more` flag to kill infinite spinner (`handlers/filesharing.py:150`).
- **FileSharing — progress UX**: `get_merged_folder_hierarchy` now depth-limited, tree loading spinner (`treeLoading`), clone progress bar (`isCloning` + `get_sync_progress` polling every 1s), unified `Mapped Folders` + `Network Folders` with device dots (`frontend/scripts/components/filesharing.js:64`).
- **Sync — auto-clone & master election**: New `_is_database_empty()`, `_auto_clone_from_master()` and `_ensure_cluster_master()` so a fresh device with empty DB auto-clones from `cluster_state.json` master on first `sync()`; master promoted automatically if missing (`sync_manager.py:312`).
- **Sync — observable progress**: All sync paths (`_sync_thread`, `_hard_clone_thread`, `_force_sync_thread`) now update `bridge.sync_status`/`sync_progress_value`/`sync_message` for UI polling; `get_sync_progress` action added; indentation bug in `_resolve_clone_target` fixed (`handlers/sync.py:18`, `sync_manager.py:342`).
- **Infra — splash cache**: `three.module.js`/`three.min.js`/`OrbitControls`/`RoundedBoxGeometry` + `markdown-it*` now pre-cached at startup (no CDN on tab click); removed redundant `three.min.js` inline fallbacks (`main.py:75`, `frontend/shelf/shelf.html:10`).
- **Tests**: 72/72 passing (`test_filesharing_*` + `test_init_pipeline`).

### v2.1.1 — Crash Fixes, File Sync Overhaul, 86/86 Tests Passing
- **App startup crash fixed**: Removed WSL git hooks (`post-commit`, `post-checkout`, `post-merge`, `pre-push`) that caused `#!/bin/sh` errors on Windows; `_init_git_lfs` now skips hook installation on Windows; `auto_sync` wrapped in try/except so sync errors no longer crash the app.
- **Circular goal infinite loop fixed**: Goal with `parent_id` pointing to itself caused `get_flat_goals()` to hang forever; added `visited` set guards in both `get_flat_goals()` and `get_descendant_titles()`.
- **File sync restructured**: `sync_files()` now mirrors local `MindPalace_Library` directly under `files/` (no device_id prefix); `_clean_old_device_folders()` removes legacy nested folders; `_sync_thread` and `_force_sync_thread` now call `sync_files()` so manual/force syncs also push shared files.
- **FileSharing tab**: New dedicated File Sharing sidebar view with mapped folders, file hierarchy tree, changelog with device-colored indicators, goal assignment, network nodes, retention policy, and sync status bar (`frontend/scripts/components/filesharing.js`).
- **FileSharing handler**: `FileSharingHandler` with actions for folder hierarchy, changelog, goal binding, retention policy (`handlers/filesharing.py`).
- **Comprehensive test suite (86 tests)**: DB schema (17), handler dispatch (27), sync sandboxed (13), full workflow integration (13), frontend JSX compilation (16).
- **Calorie vision submodule**: Pushed to `https://github.com/AliNikkhah2001/calorie_vision`; webserver on port 5000 with drag-and-drop upload, batch analysis, bounding boxes, macros breakdown.

### v2.1.0 — Advanced FileSharing & K-Cluster Removal
- K-Cluster peer nodes section and Cluster Topology/Master promote section removed from settings.
- Config default repo URL changed to `MindPalaceData.git`.

### v2.0.0 — Steady State: Init, Goals, and Sync locked down
This release consolidates the modular rewrite and the goal/sync feature trains into a single known-stable version.

**Goal hours & progress (all-time, per-goal)**
- `_handle_init` now returns **all-time studied hours per goal** (not today-only), so a session logged any day counts toward cumulative goal targets (`bridge/actions.py`).
- Studied-hour aggregation fully supports **cascading goals**: child hours roll up into parents, and course names stored as full hierarchy paths (`"Work > Eco: Business Proposal"`) now count toward both the leaf goal and its parent (`bridge/runtime.py`).
- Goal lookups in aggregation replaced linear re-scans with O(1) title→id / id→parent maps.
- Dashboard goal charts (last-7-days progress + weekly breakdown) match sessions against a goal title **or any path segment** via the new `courseMatchesGoal` helper (`frontend/scripts/components/dashboard.js`).

**Dashboard performance**
- Removed the per-second clock-feed round trip that was re-rendering the whole app every tick; the analog clock now updates its hand via direct DOM mutation, cutting CPU/memory churn on the dashboard.

**Init pipeline & data integrity**
- End-to-end init handshake regression suite: goals, habits, habit logs, and the 28×7 heatmap return with **no `error` key**.
- Time-based heatmap buckets verified under a frozen clock: intensity (0–4) scales with daily hours and lands in the correct day/week column.
- New regression tests: hierarchy-path course → leaf + parent hours; all-time init payload hours.

**Previous milestones already on `main`**
- Modular handler architecture (10 handlers + core dispatcher), sync rewrite (sandboxed multi-device suite, force-sync, hard-clone), calorie/object/depth vision estimation (MiDaS + VLM downloaders), studiedHours 0% fix, grid dashboard with drag-and-drop widgets, and markdown/check-in overflow fixes.

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    React Frontend (frontend/)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │Dashboard │ │  Timer   │ │  Health  │ │  Settings/Notes  │  │
│  │  Goals   │ │  PDF     │ │  Quiz    │ │  Flashcards      │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
│       └─────────────┴────────────┴────────────────┘             │
│                         │ api.js                                │
└─────────────────────────┼───────────────────────────────────────┘
                          │ QWebChannel
┌─────────────────────────┼───────────────────────────────────────┐
│                   Backend (Python/PyQt6)                         │
│                         │                                       │
│              ┌──────────▼──────────┐                            │
│              │   SystemBridge      │                            │
│              │   (dispatcher)      │                            │
│              └──────────┬──────────┘                            │
│                         │                                       │
│    ┌────────────────────┼────────────────────┐                  │
│    │                    │                    │                  │
│    ▼                    ▼                    ▼                  │
│ ┌──────────┐    ┌──────────────┐    ┌──────────────┐           │
│ │ Handlers │    │ Core Modules │    │  UI Widgets  │           │
│ │  (12)    │    │              │    │              │           │
│ │•Nutrition│    │•core_sys     │    │•overlay      │           │
│ │•Health   │    │•core_logger  │    │•pdf_editor   │           │
│ │•Habit    │    │•vision_track │    │•timelapse    │           │
│ │•Flashcard│    │•sync_manager │    │              │           │
│ │•Goal     │    │•horology     │    │              │           │
│ │•Note     │    │              │    │              │           │
│ │•Queue    │    │              │    │              │           │
│ │•Sync     │    │              │    │              │           │
│ │•Analytics│    │              │    │              │           │
│ │•FoodDet  │    │              │    │              │           │
│ │•Wallpaper│    │              │    │              │           │
│ │•FileShare│    │              │    │              │           │
│ └──────────┘    └──────────────┘    └──────────────┘           │
│                                                                 │
│              ┌──────────────┐                                   │
│              │  SQLite DB   │                                   │
│              │ second_brain │                                   │
│              └──────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Handler Dispatch Flow

```
Frontend request (JSON)
    │
    ▼
SystemBridge.request(payload)
    │
    ├──► _dispatch(action, req) ──► handlers[i].handle(action, req)
    │      │
    │      ├── NutritionHandler.handle() → manage_nutrition
    │      ├── HealthHandler.handle()    → manage_health, save_body_scan
    │      ├── HabitHandler.handle()     → manage_habit
    │      ├── FlashcardHandler.handle() → manage_flashcard, manage_quiz
    │      ├── GoalHandler.handle()      → manage_goal
    │      ├── NoteHandler.handle()      → manage_note
    │      ├── QueueHandler.handle()     → manage_queue
    │      ├── SyncHandler.handle()      → sync_now, hard_clone, force_sync
    │      ├── AnalyticsHandler.handle() → get_correlations, insights
│      ├── FoodDetectionHandler      → food detection, calorie vision
│      ├── WallpaperHandler.handle() → save_wallpaper
│      └── FileSharingHandler        → folder hierarchy, changelog, goal binding
    │
    └──► _core_action_handlers[action](req)
           │
           ├── _handle_init, _handle_start_timer, _handle_stop_timer
           ├── _handle_save_settings, _handle_export_data
           └── ... (35+ core actions)
```

## 📁 Project Structure

```
Modular/
│
├── 📄 main.py                          # Application entry point (190 lines)
├── 📄 system_bridge.py                 # Central backend dispatcher (1556 lines, 12 handlers)
├── 📄 core_sys.py                      # Config + Database management (156 lines)
├── 📄 core_logger.py                   # Logging framework (54 lines)
├── 📄 sync_manager.py                  # Git-based multi-device sync (605 lines)
├── 📄 vision_tracker.py                # OpenCV attention tracking (209 lines)
├── 📄 horology.py                      # Analog clock rendering (102 lines)
├── 📄 health_parser.py                 # OCR body scan parser (88 lines)
├── 📄 dependency_checker.py            # Dependency diagnostics (78 lines)
├── 📄 migrate_db.py                    # Database migration utility (53 lines)
├── 📄 library.py                       # PDF library widget (303 lines)
├── 📄 native_pdf_editor.py             # Standalone PDF editor (334 lines)
│
├── 📁 bridge/                         # Core dispatch + runtime services
│   ├── __init__.py
│   ├── actions.py                     # Init pipeline, history, heatmap export
│   ├── runtime.py                     # Runtime services (heatmap, studied hours)
│   ├── session.py                     # Session persistence
│   ├── sync_data.py                   # Sync data export helpers
│   └── media.py                       # Media handling helpers
│
├── 📁 handlers/                        # Domain action handlers
│   ├── __init__.py                     # Base ActionHandler class
│   ├── nutrition.py                    # Ingredients, recipes, composite foods
│   ├── health.py                       # Health profiles, logs, foods, activities
│   ├── habit.py                        # Habit definitions, daily logging
│   ├── flashcard.py                    # Flashcards, quizzes
│   ├── goal.py                         # Cascading goals
│   ├── note.py                         # Notes CRUD
│   ├── queue.py                        # Focus queue management
│   ├── sync.py                         # Device synchronization
│   └── filesharing.py                  # Shared folder hierarchy, changelog, goal binding
│
├── 📁 ui/                              # Reusable UI components
│   ├── __init__.py                     # Package exports
│   ├── overlay.py                      # Timer overlay widget
│   ├── pdf_editor.py                   # PDF editor window
│   └── timelapse.py                    # Timelapse dialog
│
├── 📁 frontend/                        # React frontend
│   ├── index.html                      # HTML shell (entry point)
│   ├── styles/
│   │   └── main.css                    # All CSS styles (glassmorphism)
│   ├── shelf/                          # 3D Bookshelf (Mint Complete Shelf port)
│   │   ├── shelf.html / shelf-engine.js / cover-art.js / book-motion.js / catalog.js
│   │   └── shelf-styles.css            # Three.js r160, importmap, procedural covers
│   └── scripts/
│       ├── utils.js                    # Utility functions (Jalali calendar)
│       ├── api.js                      # Backend API communication layer
│       ├── app.js                      # Main App component + routing (Bookshelf + Markdown routes)
│       └── components/
│           ├── dashboard.js            # Dashboard, calendar, metrics
│           ├── timer.js                # Pomodoro timer, timeline, queue (hatched distractions)
│           ├── goals.js                # Goals, habits, day summary
│           ├── pdf-viewer.js           # PDF library with annotations
│           ├── library.js              # Quiz engine, flashcards
│           ├── notes.js                # Markdown notes editor
│           ├── markdown-editor.js      # Markdown Studio (live preview, HTML/PDF export)
│           ├── health.js               # Health, nutrition, fitness
│           ├── settings.js             # Application settings
│           └── filesharing.js          # File sharing, merged hierarchy, progress bar
│
├── 📁 tests/                           # Test suite (86+ tests, 72 in filesharing+init core)
│   ├── __init__.py
│   ├── test_backend.py                 # Backend config/DB/dispatch tests (22)
│   ├── test_init_pipeline.py           # End-to-end init + time-based heatmap suite (12)
│   ├── test_startup.py                 # Startup integration smoke test
│   ├── test_sync_sandboxed.py          # Sandboxed multi-device sync suite
│   ├── test_sync_multi_machine.py      # Multi-machine sync scenarios
│   ├── test_runtime_features.py        # Food, blob, timer, wallpaper tests
│   ├── test_filesharing_db.py          # Config bindings, retention, DB schema (17)
│   ├── test_filesharing_handlers.py    # Handler dispatch, hierarchy + merged tree (27)
│   ├── test_filesharing_sync.py        # Sandboxed device, git push/pull (13)
│   ├── test_filesharing_integration.py # Full workflow, synthetic laptop/phone (13)
│   └── test_filesharing_frontend.py    # JSX compilation, routing, bridge reg (16)
│
├── 📁 tools/                           # Utilities
│   ├── data_import.py                  # API data importer
│   ├── download_*.py                   # Model / dataset downloaders
│   ├── evaluate_calorie_vision.py      # Calorie vision evaluation
│   └── _run_sync_tests.py              # Sync suite runner (per-class timeouts)
│
├── 📄 requirements.txt                 # Python dependencies
├── 📄 pyproject.toml                   # Ruff linter/formatter config
├── 📄 config.json                      # Application settings
│
├── 📁 calorie_vision_submodule/        # Calorie vision estimation (submodule → github.com/AliNikkhah2001/calorie_vision)
│   ├── app.py                          # Flask webserver (port 5000)
│   ├── calorie_tracker.py              # Main tracker logic
│   ├── opencv_calorie_estimator.py     # OpenCV-based calorie estimation
│   └── size_estimator.py              # MiDaS depth-based size estimation
```

### File Size Guidelines
- **Max 500 lines** per module (except complex UI components)
- **Max 850 lines** for frontend view components
- **Single responsibility** per file
- **Clear naming** convention

## ✨ Current Features

### 🕐 Focus & Productivity Hub
- **24-Hour Absolute Timeline:** Infinite-scroll daily Gantt chart mapping every minute
- **Vision Tracker Engine:** OpenCV-powered face and eye presence detection
- **Distraction Memory:** Pinpoint recording of exact distraction moments
- **Focus Queue:** Queue of sessions with auto-advance

### 📚 Knowledge Management
- **Native PDF Editor:** High-DPI rendering, text highlighting, annotations
- **3D Bookshelf — Complete Shelf:** 19 procedural hardcovers on a continuous Three.js shelf; drag/scroll/arrow browsing + orbit/zoom inspect; cached for offline (`frontend/shelf/`).
- **Markdown Studio:** Live-preview editor (markdown-it, footnote/table), split/edit/preview, open/save `.md`, export HTML/PDF.
- **Markdown Notes:** Rich notes with LaTeX, code blocks, images
- **Flashcards & Quiz:** Spaced repetition study tools
- **Library:** PDF library with sync across devices

### 🎯 Goals & Health
- **Cascading Goals:** Infinite sub-goal mapping with deadlines
- **Health Engine:** Caloric projections, nutrition tracking
- **Habit Matrix:** 7-day rolling contribution heatmaps
- **Nutrition:** Ingredients, recipes, composite foods

### 🔄 Distributed Sync
- **Peer-to-Peer Database:** Master-wins + last-write-wins merging, soft-delete via `deleted_uuids`, auto-clone on empty DB, `cluster_state.json` master election (`sync_manager.py`).
- **Git-Based Sync:** Multi-device sync via GitHub + Git LFS; observable progress (`sync_progress`/`sync_status`) on splash and FileSharing tab.
- **Shared Network Folders:** Mirrors local folders into sync repo (`files/MindPalace_Library`), auto-sync across devices; merged `files/` tree.
- **File Sharing:** Unified merged hierarchy (one entry per folder, not per device), device-colored dots, friendly names, depth-limited tree, progress bar on clone/sync, changelog & retention.

### 🎨 UI/UX
- **Glassmorphism Design:** Modern translucent panels
- **Timeline — Colored Distractions:** Hatched overlays with legend (App/Camera/Manual) on live + history tracks.
- **Timer — Freeze Fix:** Clock resets to full duration on stop, not `00:00`.
- **Analog Clock:** Customizable overlay with complications
- **Jalali Calendar:** Persian calendar support
- **Dark Theme:** Full dark mode with accent colors

## 🚀 Installation

### Prerequisites
- Python 3.12 or higher
- Git
- GitHub account (for distributed sync)
- Webcam (optional, for attention tracking)

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/AliNikkhah2001/Personal_Shadow.git
cd Personal_Shadow/Modular

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # On macOS/Linux: source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python main.py
```

### Environment Variables
Create a `.env` file in the project root:
```
GITHUB_TOKEN = your_github_personal_access_token
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `module 'cv2' has no attribute 'CascadeClassifier'` | OpenCV 5.x removed legacy cascades; the app now falls back to motion detection |
| `ModuleNotFoundError: No module named 'machineid'` | Install with `pip install py-machineid` |
| `Port 5050 already in use` | Another instance is running or port is occupied; kill the process or change port |
| `Git sync fails` | Verify `GITHUB_TOKEN` is set and has repo permissions |

## ⚙️ Configuration

Settings are stored in `config.json` and editable via the Settings UI:

| Category | Settings |
|----------|----------|
| **UI** | Font, colors, clock style, panel opacity |
| **Vision** | Detection mode, sample interval, sensitivity |
| **Sound** | Distraction sounds, mute toggles |
| **Sync** | Repo URL, interval, local paths |
| **Health** | Age, height, weight, gender, activity level |

## 🛠️ Development

### Code Quality
This project uses [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check code
python -m ruff check .

# Fix issues
python -m ruff check --fix .

# Format code
python -m ruff format .
```

### Adding a New Handler
1. Create a new file in `handlers/`
2. Subclass `ActionHandler`
3. Define `actions` mapping
4. Register in `SystemBridge._init_handlers()`

```python
from handlers import ActionHandler


class MyNewHandler(ActionHandler):
    actions = {
        "my_action": "handle_my_action",
    }

    def handle_my_action(self, req):
        # Process the request
        return json.dumps({"status": "ok"})
```

### Database Schema
SQLite database (`second_brain.db`) with 22 tables:
- `courses`, `pomodoro_sessions`, `cascading_goals`
- `habits`, `habit_logs`, `flashcards`, `quizzes`
- `notes`, `health_profile`, `health_logs`
- `custom_foods`, `custom_activities`, `health_plans`
- `ingredients`, `composite_foods`, `recipe_ingredients`
- `focus_queue`, `activity_logs`, `deleted_uuids`
- `food_logs`, `daily_metrics`, `wallpapers`

## 🧪 Testing

The suite uses `unittest` (no third-party runner required). 86 tests total. Naming convention: `test_*.py` with classes.

```bash
# Core backend (config, DB, dispatch, timeline config)
python -m unittest tests.test_backend

# Init pipeline regression: the full init handshake (goals, habits, heatmap)
python -m unittest tests.test_init_pipeline

# Startup integration smoke test
python tests/test_startup.py

# File sharing suite (86 tests: DB, handlers, sync, integration, frontend)
python -m pytest tests/test_filesharing_db.py tests/test_filesharing_handlers.py tests/test_filesharing_sync.py tests/test_filesharing_integration.py tests/test_filesharing_frontend.py -v
```

The test suite verifies:
- **All module imports work correctly** (`test_startup.py`)
- **Database connections, queries, config management, handler dispatch, timeline config** (`test_backend.py`)
- **End-to-end init pipepline** — `_handle_init` returns goals, habits, habit_logs and a 28×7 heatmap with **no `error` key** (regression, `test_init_pipeline.py`)
- **Time-based logic** — per-goal studied-hour aggregation rolls child goals into parents and honours `date_filter`; heatmap intensity (0–4) scales with daily hours and maps to the correct 28-day/week column using a frozen clock (`test_init_pipeline.py`)
- **Multi-device sync** — sandboxed export/merge/conflict/deletion/settings/force-sync/hard-clone/edge cases, plus multi-machine timeline sync (`test_sync_sandboxed.py`, `test_sync_multi_machine.py`)
- **File sharing** — config bindings, retention config, DB schema integrity, handler dispatch, folder hierarchy, changelog, goal binding, retention policies, sandboxed device sync, git push/pull, 3-device chain, full workflow integration, synthetic laptop/phone/desktop scenario, JSX Babel compilation, app.js routing, settings cleanup, bridge registration (`test_filesharing_*.py` — 86 tests)

## 🗺️ Roadmap

### Phase 1: Timeline & Hub Refinement
- [x] UI configuration for Timeline start/end hours
- [x] Wire past timeline sessions to fetch distraction data (+ hatched colored overlays with legend)
- [x] Clock freeze fix on session stop (reset to `total_time`)
- [x] Visual "Planned vs. Actual" duration mapping
- [ ] Trigger TimelapseDialog from timeline clicks

### Phase 2: Advanced Nutrition & Fasting
- [x] Expand SQLite schema for ingredients/recipes
- [x] Python ingestion script for food datasets
- [x] Custom Recipe Builder UI
- [x] OpenCV calorie estimation from images

### Phase 3: Behavioral Analytics
- [x] Daily Check-in modal (Sleep, Energy, Mood)
- [x] Pandas/NumPy correlation backend
- [x] Chart.js correlation graphs
- [ ] Automated PDF Life Reports

### Phase 4: Visual Photo Diary
- [ ] Focus Snap capture on 60m+ sessions
- [ ] Chronicle Vault masonry gallery
- [ ] Polaroid indicators in calendar

### Phase 5: Focus Firewall
- [ ] OS hosts file backup/overwrite
- [ ] Blacklist/Whitelist UI
- [ ] Tie to Pomodoro states

### Phase 6: 3D Mind Palace
- [x] Three.js 3D Grand Library — **Complete Shelf** (19 volumes, drag/browse/inspect, cached)
- [ ] SQLite-to-3D book mapping
- [ ] Raycasting for book interaction
- [ ] Trophy Hall for habit streaks

### Phase 7: Markdown Studio (v2.2.0 new)
- [x] Live-preview editor (markdown-it + footnote/table, cached at startup)
- [x] Split/edit/preview modes, open/save `.md`, export HTML/PDF

## 📄 License

Private project. All rights reserved.

## 🤝 Contributing

This is a personal project. For suggestions or issues, please open a GitHub issue.
