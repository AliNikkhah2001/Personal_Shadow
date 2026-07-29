
---

## 📁 **Project Structure & Documentation**

### 1. Create a detailed `README.md`

Create this file in your project root:

```markdown
# 🧠 Mind Palace OS

A cross-platform productivity and knowledge management system with GitHub-based synchronization.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

## 📋 Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Sync & Sharing](#sync--sharing)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

Mind Palace OS is an all-in-one productivity suite that combines:
- **Focus Timer** with distraction detection
- **Knowledge Management** (notes, flashcards, quizzes)
- **Habit Tracking** with streak monitoring
- **Goal Architecture** with cascading objectives
- **GitHub Sync** for cross-device data sharing

Built with **PyQt6** frontend and **React/JSX** for the UI, it provides a native desktop experience with web-like responsiveness.

## ✨ Features

### 🕐 Focus & Productivity
- **Pomodoro Timer** with work/break sessions
- **Automatic Session Queue** with auto-advance
- **Vision Tracker** (face detection for attention)
- **Quiet Mode** (disable webcam, sounds, speech)
- **App Monitoring** (detect distracting applications)
- **Session History** with analytics

### 📚 Knowledge Management
- **Markdown Notes** with live preview
- **Flashcards** with spaced repetition
- **Quiz Engine** with JSON import
- **Course Organization** with folders and colors

### 🎯 Goals & Habits
- **Cascading Goals** with sub-goals
- **Habit Matrix** with 7-day tracking
- **Progress Dashboard** with metrics
- **Contribution Heatmap** (GitHub-style)

### 🔄 Sync & Sharing
- **GitHub-based Sync** (data only, not code)
- **Cross-device Merging** (UUID-based conflict resolution)
- **File Sharing** (mapped folders)
- **Automatic Backups** (hourly)
- **Export/Import** (ZIP with JSON)

## 🚀 Installation

### Prerequisites
- Python 3.12 or higher
- Git
- GitHub account (for sync features)

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/AliNikkhah2001/MindPalaceOS.git
cd MindPalaceOS

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python main.py
```

### Development Installation

```bash
# Install with development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run with debug output
python main.py --debug
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# GitHub Personal Access Token (required for sync)
GITHUB_TOKEN=ghp_your_token_here

# Optional: Override default settings
# MUTE_SOUNDS=true
# QUIET_MODE=false
```

### Settings

The app stores settings in `config.json`:

```json
{
  "sync_enabled": true,
  "sync_repo_url": "https://github.com/username/data-repo.git",
  "sync_interval": 3600,
  "quiet_mode": false,
  "mute_sounds": true,
  "app_monitoring_enabled": false
}
```

### GitHub Token Setup

1. Go to [GitHub Settings → Tokens](https://github.com/settings/tokens)
2. Generate a **classic token** with `repo` scope
3. Copy the token (starts with `ghp_`)
4. Add to `.env` file as `GITHUB_TOKEN`

## 🎮 Usage

### Main Interface

```
┌─────────────┬─────────────────────────────────────────────┐
│  Navigation │           Main Content Area                │
│             │                                             │
│  Dashboard  │  - Global Progress                        │
│  Focus Hub  │  - Contribution Heatmap                  │
│  Goals      │  - Habit Matrix                          │
│  Habits     │  - Notes / Flashcards / Quizzes          │
│  Notes      │                                             │
│  Settings   │                                             │
└─────────────┴─────────────────────────────────────────────┘
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New Note |
| `Ctrl+S` | Save Current |
| `Ctrl+F` | Search |
| `Ctrl+Q` | Quiet Mode Toggle |
| `Space` | Start/Pause Timer |

### Sync Workflow

1. **Initial Setup**
   - Create a private GitHub repository for data
   - Add `GITHUB_TOKEN` to `.env`
   - Enable sync in Settings

2. **Auto-Sync**
   - Syncs every hour (configurable)
   - Merges data from all devices
   - Preserves all notes, habits, goals

3. **Manual Sync**
   - Click "Sync Now" in Settings
   - Pulls remote changes, merges, pushes local

## 🔄 Sync & Sharing

### Repository Structure

The data repository contains:

```
data-repo/
├── sync_data.json          # Master database (all records)
├── files/                  # Shared files
│   ├── device-001/         # Device-specific files
│   ├── device-002/
│   └── shared/             # Shared across devices
└── .gitignore              # Ensures only data is synced
```

### Merge Strategy

- **UUID-based** conflict resolution
- **Modified_at** timestamp comparison (newer wins)
- **Never deletes** data (only adds/updates)
- **Preserves** notes, habits, goals across devices

## 💻 Development

### Project Structure

```
MindPalaceOS/
├── main.py                 # Main application
├── shadow_os_cache/        # Cached web assets
├── shadow_venv/            # Virtual environment
├── config.json             # User settings
├── second_brain.db         # SQLite database
├── requirements.txt        # Dependencies
├── README.md              # This file
├── .env                   # Environment variables
└── .gitignore             # Git ignore rules
```

### Code Architecture

```
┌─────────────────────────────────────────────────────┐
│                   MindPalaceWebOS (Main Window)     │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────────────────┐  │
│  │   React UI  │  │   SystemBridge (Python)     │  │
│  │  (JSX/Babel)│◄─┤   - State Management        │  │
│  │             │  │   - Database Operations      │  │
│  │  Dashboard  │  │   - Sync Manager            │  │
│  │  Focus Hub  │  │   - Vision Tracker          │  │
│  │  Notes      │  │   - Sound/Speech            │  │
│  │  Settings   │  │                             │  │
│  └─────────────┘  └─────────────────────────────┘  │
│                          │                          │
│                          ▼                          │
│              ┌─────────────────────┐               │
│              │   SQLite Database   │               │
│              │   (second_brain.db) │               │
│              └─────────────────────┘               │
└─────────────────────────────────────────────────────┘
```

### Debugging

```bash
# Run with debug output
python main.py --debug

# Check database
sqlite3 second_brain.db .tables

# Test sync connection
python test_git.py
```

## 🤝 Contributing

### Git Workflow

```bash
# 1. Create a feature branch
git checkout -b feature/your-feature-name

# 2. Make changes and commit
git add .
git commit -m "feat: Add your feature description"

# 3. Push and create PR
git push -u origin feature/your-feature-name
```

### Commit Message Convention

```
type(scope): description

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation
- style: Code style
- refactor: Code refactor
- test: Tests
- chore: Maintenance
```

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with PyQt6 and React
- Icons from Font Awesome
- Fonts from Google Fonts

---

**Made with ❤️ for productivity**
```

---
