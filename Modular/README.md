# 🕵️‍♂️ Sherlock Holmes Mind Palace

A cross-platform productivity, deductive analytics, and 3D spatial knowledge management system.

![Version](https://img.shields.io/badge/version-2.0.0--beta-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![React](https://img.shields.io/badge/react-18.0+-61dafb)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Ruff](https://img.shields.io/badge/linter-ruff-orange)

## 📋 Table of Contents
- [Overview](#-overview)
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
│ │  (11)    │    │              │    │              │           │
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
    │      └── WallpaperHandler.handle() → save_wallpaper
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
├── 📄 system_bridge.py                 # Central backend dispatcher (1556 lines)
├── 📄 core_sys.py                      # Config + Database management (156 lines)
├── 📄 core_logger.py                   # Logging framework (54 lines)
├── 📄 sync_manager.py                  # Git-based multi-device sync (421 lines)
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
│   └── sync.py                         # Device synchronization
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
│   └── scripts/
│       ├── utils.js                    # Utility functions (Jalali calendar)
│       ├── api.js                      # Backend API communication layer
│       ├── app.js                      # Main App component + routing
│       └── components/
│           ├── dashboard.js            # Dashboard, calendar, metrics
│           ├── timer.js                # Pomodoro timer, timeline, queue
│           ├── goals.js                # Goals, habits, day summary
│           ├── pdf-viewer.js           # PDF library with annotations
│           ├── library.js              # Quiz engine, flashcards
│           ├── notes.js                # Markdown notes editor
│           ├── health.js               # Health, nutrition, fitness
│           └── settings.js             # Application settings
│
├── 📁 tests/                           # Test suite
│   ├── __init__.py
│   ├── test_backend.py                 # Backend config/DB/dispatch tests (22)
│   ├── test_init_pipeline.py           # End-to-end init + time-based heatmap suite (9)
│   ├── test_startup.py                 # Startup integration smoke test
│   ├── test_sync_sandboxed.py          # Sandboxed multi-device sync suite
│   ├── test_sync_multi_machine.py      # Multi-machine sync scenarios
│   └── test_runtime_features.py        # Food, blob, timer, wallpaper tests
│
├── 📁 tools/                           # Utilities
│   ├── data_import.py                  # API data importer
│   ├── download_*.py                   # Model / dataset downloaders
│   ├── evaluate_calorie_vision.py      # Calorie vision evaluation
│   └── _run_sync_tests.py              # Sync suite runner (per-class timeouts)
│
├── 📄 requirements.txt                 # Python dependencies
├── 📄 pyproject.toml                   # Ruff linter/formatter config
└── 📄 config.json                      # Application settings
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
- **Markdown Notes:** Rich notes with LaTeX, code blocks, images
- **Flashcards & Quiz:** Spaced repetition study tools
- **Library:** PDF library with sync across devices

### 🎯 Goals & Health
- **Cascading Goals:** Infinite sub-goal mapping with deadlines
- **Health Engine:** Caloric projections, nutrition tracking
- **Habit Matrix:** 7-day rolling contribution heatmaps
- **Nutrition:** Ingredients, recipes, composite foods

### 🔄 Distributed Sync
- **Peer-to-Peer Database:** Last-Write-Wins conflict resolution
- **Git-Based Sync:** Multi-device synchronization via GitHub
- **Shared Network Drives:** Auto-sync files across devices

### 🎨 UI/UX
- **Glassmorphism Design:** Modern translucent panels
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

The suite uses `unittest` (no third-party runner required). Naming convention: `test_*.py` with classes.

```bash
# Core backend (config, DB, dispatch, timeline config)
python -m unittest tests.test_backend

# Init pipeline regression: the full init handshake (goals, habits, heatmap)
# plus time-based heatmap/studied-hours logic with frozen clocks
python -m unittest tests.test_init_pipeline

# Startup integration smoke test (runs on import, asserts DB + 22 tables)
python tests/test_startup.py

# Runtime feature tests (food detection, sync blob encoding, timer tick,
# wallpaper blob round-trip) — module-level test functions
python tools/_run_sync_tests.py   # sync suite runner with per-class timeouts
```

The test suite verifies:
- **All module imports work correctly** (`test_startup.py`)
- **Database connections, queries, config management, handler dispatch, timeline config** (`test_backend.py`)
- **End-to-end init pipepline** — `_handle_init` returns goals, habits, habit_logs and a 28×7 heatmap with **no `error` key** (regression, `test_init_pipeline.py`)
- **Time-based logic** — per-goal studied-hour aggregation rolls child goals into parents and honours `date_filter`; heatmap intensity (0–4) scales with daily hours and maps to the correct 28-day/week column using a frozen clock (`test_init_pipeline.py`)
- **Multi-device sync** — sandboxed export/merge/conflict/deletion/settings/force-sync/hard-clone/edge cases, plus multi-machine timeline sync (`test_sync_sandboxed.py`, `test_sync_multi_machine.py`; run via `tools/_run_sync_tests.py` — real-git classes may hang on Windows)

## 🗺️ Roadmap

### Phase 1: Timeline & Hub Refinement
- [x] UI configuration for Timeline start/end hours
- [x] Wire past timeline sessions to fetch distraction data
- [ ] Trigger TimelapseDialog from timeline clicks
- [x] Visual "Planned vs. Actual" duration mapping

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
- [ ] Three.js 3D Grand Library
- [ ] SQLite-to-3D book mapping
- [ ] Raycasting for book interaction
- [ ] Trophy Hall for habit streaks

## 📄 License

Private project. All rights reserved.

## 🤝 Contributing

This is a personal project. For suggestions or issues, please open a GitHub issue.
