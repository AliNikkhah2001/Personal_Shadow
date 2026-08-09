# 🕵️‍♂️ Sherlock Holmes Mind Palace

A cross-platform productivity, deductive analytics, and 3D spatial knowledge management system. 

![Version](https://img.shields.io/badge/version-2.0.0--beta-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![React](https://img.shields.io/badge/react-18.0+-61dafb)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

## 📋 Table of Contents
- [Overview](#-overview)
- [Current Features](#-current-features)
- [🗺️ Master Action Plan & Progress](#-master-action-plan--progress)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Sync & Architecture](#-sync--architecture)
- [Contributing](#-contributing)

## 🔎 Overview

The **Sherlock Holmes Mind Palace** is the ultimate convergence of a "Second Brain" and the "Method of Loci." Built with a lightning-fast **PyQt6** backend and a glassmorphism **React/JSX** frontend, it acts as a centralized operating system for your intellectual and physical life. 

It is designed to seamlessly track your focus, map your knowledge spatially, analyze your behavioral data deductively, and synchronize perfectly across all your devices using peer-to-peer GitHub node architectures.

## ✨ Current Features

### 🕐 Focus & Productivity Hub
- **24-Hour Absolute Timeline:** Infinite-scroll daily Gantt chart mapping out every minute of your day.
- **Vision Tracker Engine:** OpenCV-powered hardware acceleration tracking face and eye presence to ensure absolute attention.
- **Distraction Memory:** Pinpoint recording of the exact second you lost focus (App, Camera, or Manual) embedded directly into your timeline.

### 📚 Knowledge Management & Library
- **Native High-DPI PDF Editor:** Continuous virtual scrolling, lazy-loading, and true PDF Text Matrix highlighting via PyMuPDF.
- **Markdown Meta-Annotation:** Inject rich markdown notes (Code blocks, LaTeX, Images) directly into PDF coordinates.
- **Flashcards & Quiz Engine:** JSON-based study tools with spaced repetition mechanics.

### 🎯 Goals & Health
- **Cascading Goal Architecture:** Infinite sub-goal mapping with integrated deadlines.
- **Health Engine:** Caloric deficit projections and basic logging.
- **Habit Matrix:** 7-day rolling GitHub-style contribution heatmaps.

### 🔄 Distributed Sync Network
- **Peer-to-Peer Database Nodes:** True Last-Write-Wins (LWW) conflict-free database merging across Windows, Mac, and Linux.
- **Shared Network Drives:** Map local directories to auto-sync files across your personal device fleet.

---

## 🗺️ Master Action Plan & Progress

Our development roadmap is strictly phased to ensure modular stability. 

### Phase 1: The Timeline & Hub Refinement
- [ ] Add UI configuration for Timeline start/end hours and pixel scaling.
- [ ] Wire past timeline sessions to fetch exact distraction JSON.
- [ ] Trigger `TimelapseDialog` securely from timeline clicks.
- [ ] Visually map "Planned vs. Actual" duration inside timeline blocks.

### Phase 2: Advanced Nutrition & Fasting Engine
- [ ] Expand SQLite schema (`ingredients`, `composite_foods`, `recipe_ingredients`, `food_logs`).
- [ ] Build Python ingestion script for standard/Persian food datasets (SAMAR).
- [ ] UI: Add/Edit/Remove ingredients with support for local image paths/icons.
- [ ] UI: Custom Recipe Builder (mixing ingredients to auto-calculate total macros).
- [ ] *Future Scope: Calculating calories natively from OpenCV image vision.*

### Phase 3: "Quantified Self" Behavioral Analytics
- [ ] Implement "Daily Check-in" React modal (Sleep, Energy, Mood tags).
- [ ] Establish `daily_metrics` SQLite table.
- [ ] Build Pandas/NumPy Python backend for data correlation.
- [ ] Render "Behavioral Insights" and Chart.js correlation graphs on Dashboard.
- [ ] Automated PDF "Life Reports" (Weekly/Monthly/Yearly).

### Phase 4: The Chronicle (Visual Photo Diary)
- [ ] Modify OpenCV Tracker to capture "Focus Snaps" upon completing flawless 60m+ sessions.
- [ ] Save snaps locally to `memories/` directory.
- [ ] Inject polaroid indicators into `DualCalendar` React component.
- [ ] Build the "Chronicle Vault" masonry gallery view for browsing daily photos.

### Phase 5: The Focus Firewall (Network Blocking)
- [ ] Python utility to backup and overwrite OS `/etc/hosts` or Windows equivalent.
- [ ] Build Blacklist/Whitelist UI in Settings tab.
- [ ] Tie network execution strictly to Pomodoro Start/Stop/Pause states.

### Phase 6: The 3D Mind Palace (Method of Loci)
- [ ] Inject `three.js` and `@react-three/fiber` into WebEngine.
- [ ] Render 3D "Grand Library" with bookshelves.
- [ ] Map SQLite `courses` and `notes` to generate physical 3D interactive books.
- [ ] Implement Raycasting: Clicking a 3D book seamlessly opens the 2D Markdown Editor.
- [ ] Build 3D "Trophy Hall" mapping habit streaks to glowing artifacts.

---

## 🚀 Installation

### Prerequisites
- Python 3.12 or higher
- Git
- GitHub account (for distributed sync)

### Quick Start

```bash
# 1. Clone the repository
git clone [https://github.com/AliNikkhah2001/MindPalaceOS.git](https://github.com/AliNikkhah2001/MindPalaceOS.git)
cd MindPalaceOS

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python main.py