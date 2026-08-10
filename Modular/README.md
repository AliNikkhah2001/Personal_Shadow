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

### Backend (Python/PyQt6)
The backend uses a **handler-based architecture** for clean separation of concerns:

```
React Frontend (index.html)
    │
    ▼
QWebChannel (JavaScript ↔ Python bridge)
    │
    ▼
SystemBridge (dispatcher)
    │
    ├──► Domain Handlers (handlers/)
    │    ├── NutritionHandler    → Ingredients, recipes, composite foods
    │    ├── HealthHandler       → Profiles, logs, foods, activities
    │    ├── HabitHandler        → Habit definitions, daily logging
    │    ├── FlashcardHandler    → Flashcards, quizzes
    │    ├── GoalHandler         → Cascading goals
    │    ├── NoteHandler         → Notes CRUD
    │    ├── QueueHandler        → Focus queue management
    │    └── SyncHandler         → Device synchronization
    │
    ├──► Core Modules
    │    ├── core_sys.py         → ConfigManager, DatabaseManager
    │    ├── core_logger.py      → Logging framework
    │    ├── vision_tracker.py   → OpenCV face/eye detection
    │    ├── sync_manager.py     → Git-based multi-device sync
    │    └── horology.py         → Analog clock rendering
    │
    └──► UI Components (ui/)
         ├── overlay.py          → Timer overlay widget
         ├── pdf_editor.py       → Advanced PDF editor window
         └── timelapse.py        → Timelapse playback dialog
```

### Frontend (React/Tailwind)
The frontend is organized into modular components:

```
frontend/
├── index.html                  → HTML shell with script loading
├── styles/main.css             → All CSS styles (glassmorphism)
└── scripts/
    ├── utils.js                → Utility functions (Jalali calendar, etc.)
    ├── api.js                  → Backend API communication layer
    ├── app.js                  → Main App component + routing
    └── components/
        ├── dashboard.js        → Dashboard, calendar, metrics
        ├── timer.js            → Pomodoro timer, timeline, queue
        ├── goals.js            → Goals, habits, day summary
        ├── pdf-viewer.js       → PDF library with annotations
        ├── library.js          → Quiz engine, flashcards
        ├── notes.js            → Markdown notes editor
        ├── health.js           → Health, nutrition, fitness
        └── settings.js         → Application settings
```

## 📁 Project Structure

```
Modular/
├── main.py                      # Application entry point
├── system_bridge.py             # Central backend dispatcher
├── core_sys.py                  # Config + Database management
├── core_logger.py               # Logging framework
├── sync_manager.py              # Git-based multi-device sync
├── vision_tracker.py            # OpenCV attention tracking
├── horology.py                  # Analog clock rendering
├── health_parser.py             # OCR body scan parser
├── dependency_checker.py        # Dependency diagnostics
├── migrate_db.py                # Database migration utility
├── library.py                   # PDF library widget
├── native_pdf_editor.py         # Standalone PDF editor
│
├── handlers/                    # Domain action handlers
│   ├── __init__.py              # Base ActionHandler class
│   ├── nutrition.py             # Ingredients, recipes
│   ├── health.py                # Health profiles, logs
│   ├── habit.py                 # Habit tracking
│   ├── flashcard.py             # Flashcards, quizzes
│   ├── goal.py                  # Cascading goals
│   ├── note.py                  # Notes management
│   ├── queue.py                 # Focus queue
│   └── sync.py                  # Device synchronization
│
├── ui/                          # Reusable UI components
│   ├── __init__.py              # Package exports
│   ├── overlay.py               # Timer overlay widget
│   ├── pdf_editor.py            # PDF editor window
│   └── timelapse.py             # Timelapse dialog
│
├── frontend/                    # React frontend
│   ├── index.html               # HTML shell
│   ├── styles/main.css          # CSS styles
│   └── scripts/                 # JavaScript modules
│       ├── utils.js             # Utilities
│       ├── api.js               # API layer
│       ├── app.js               # Main App
│       └── components/          # View components
│
├── tests/                       # Test suite
│   └── test_backend.py          # Backend tests
│
├── tools/                       # Utilities
│   └── data_import.py           # API data importer
│
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Ruff linter/formatter config
└── config.json                  # Application settings
```

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
SQLite database (`second_brain.db`) with 16+ tables:
- `courses`, `pomodoro_sessions`, `cascading_goals`
- `habits`, `habit_logs`, `flashcards`, `quizzes`
- `notes`, `health_profile`, `health_logs`
- `custom_foods`, `custom_activities`, `health_plans`
- `ingredients`, `composite_foods`, `recipe_ingredients`
- `focus_queue`, `activity_logs`, `deleted_uuids`

## 🧪 Testing

```bash
# Run all tests
python tests/test_backend.py

# Run with pytest (if installed)
pytest tests/
```

The test suite verifies:
- All module imports work correctly
- Database connections and queries
- Configuration management
- Handler dispatch pattern

## 🗺️ Roadmap

### Phase 1: Timeline & Hub Refinement
- [ ] UI configuration for Timeline start/end hours
- [ ] Wire past timeline sessions to fetch distraction data
- [ ] Trigger TimelapseDialog from timeline clicks
- [ ] Visual "Planned vs. Actual" duration mapping

### Phase 2: Advanced Nutrition & Fasting
- [ ] Expand SQLite schema for ingredients/recipes
- [ ] Python ingestion script for food datasets
- [ ] Custom Recipe Builder UI
- [ ] OpenCV calorie estimation from images

### Phase 3: Behavioral Analytics
- [ ] Daily Check-in modal (Sleep, Energy, Mood)
- [ ] Pandas/NumPy correlation backend
- [ ] Chart.js correlation graphs
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
