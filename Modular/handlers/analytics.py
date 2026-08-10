"""Daily metrics and behavioral analytics handler."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, ClassVar, Dict, List

import numpy as np

from core_sys import db
from handlers import ActionHandler


class AnalyticsHandler(ActionHandler):
    """Handles daily check-ins, metrics, and behavioral analytics."""

    actions: ClassVar[dict[str, str]] = {
        "manage_analytics": "manage_analytics",
    }

    def manage_analytics(self, req: dict[str, Any]) -> str:
        sub = req.get("sub")
        if sub == "save_daily_checkin":
            return self._save_daily_checkin(req)
        if sub == "get_daily_checkin":
            return self._get_daily_checkin(req)
        if sub == "get_metrics_range":
            return self._get_metrics_range(req)
        if sub == "get_correlations":
            return self._get_correlations(req)
        if sub == "get_insights":
            return self._get_insights(req)
        return json.dumps({"error": "Unknown analytics sub-action"})

    def _save_daily_checkin(self, req: dict[str, Any]) -> str:
        """Save or update daily check-in data."""
        try:
            date = req.get("date", datetime.now().date().isoformat())
            sleep_hours = float(req.get("sleep_hours") or 0)
            sleep_quality = int(req.get("sleep_quality") or 0)  # 1-5
            energy_level = int(req.get("energy_level") or 0)  # 1-5
            mood_tags = req.get("mood_tags", [])  # List of strings
            stress_level = int(req.get("stress_level") or 0)  # 1-5
            notes = req.get("notes", "")

            # Upsert
            db.c.execute(
                """INSERT INTO daily_metrics (uuid, modified_at, date, sleep_hours, sleep_quality, energy_level, mood_tags, stress_level, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                   sleep_hours=excluded.sleep_hours,
                   sleep_quality=excluded.sleep_quality,
                   energy_level=excluded.energy_level,
                   mood_tags=excluded.mood_tags,
                   stress_level=excluded.stress_level,
                   notes=excluded.notes,
                   modified_at=excluded.modified_at""",
                (
                    __import__("uuid").uuid4().hex,
                    datetime.now().isoformat(),
                    date,
                    sleep_hours,
                    sleep_quality,
                    energy_level,
                    json.dumps(mood_tags),
                    stress_level,
                    notes,
                ),
            )
            db.safe_commit()
            return json.dumps({"status": "saved", "date": date})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _get_daily_checkin(self, req: dict[str, Any]) -> str:
        """Get daily check-in for a specific date."""
        date = req.get("date", datetime.now().date().isoformat())
        db.c.execute(
            "SELECT date, sleep_hours, sleep_quality, energy_level, mood_tags, stress_level, notes FROM daily_metrics WHERE date = ?",
            (date,),
        )
        row = db.c.fetchone()
        if row:
            return json.dumps({
                "date": row[0],
                "sleep_hours": row[1],
                "sleep_quality": row[2],
                "energy_level": row[3],
                "mood_tags": json.loads(row[4]) if row[4] else [],
                "stress_level": row[5],
                "notes": row[6],
            })
        return json.dumps({"date": date, "sleep_hours": 0, "sleep_quality": 0, "energy_level": 0, "mood_tags": [], "stress_level": 0, "notes": ""})

    def _get_metrics_range(self, req: dict[str, Any]) -> str:
        """Get metrics for a date range."""
        start_date = req.get("start_date", (datetime.now() - timedelta(days=30)).date().isoformat())
        end_date = req.get("end_date", datetime.now().date().isoformat())
        
        db.c.execute(
            """SELECT date, sleep_hours, sleep_quality, energy_level, mood_tags, stress_level, notes
               FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date""",
            (start_date, end_date),
        )
        metrics = [
            {
                "date": r[0],
                "sleep_hours": r[1],
                "sleep_quality": r[2],
                "energy_level": r[3],
                "mood_tags": json.loads(r[4]) if r[4] else [],
                "stress_level": r[5],
                "notes": r[6],
            }
            for r in db.c.fetchall()
        ]
        return json.dumps({"metrics": metrics})

    def _get_correlations(self, req: dict[str, Any]) -> str:
        """Calculate correlations between metrics and productivity."""
        days = int(req.get("days", 30))
        end_date = datetime.now().date()
        start_date = (end_date - timedelta(days=days)).isoformat()
        
        # Get daily metrics
        db.c.execute(
            """SELECT date, sleep_hours, sleep_quality, energy_level, stress_level
               FROM daily_metrics WHERE date >= ? ORDER BY date""",
            (start_date,),
        )
        metrics_rows = db.c.fetchall()
        
        # Get daily productivity (pomodoro hours)
        db.c.execute(
            """SELECT date(timestamp), SUM(actual_duration)/60.0
               FROM pomodoro_sessions 
               WHERE type='Work' AND date(timestamp) >= ?
               GROUP BY date(timestamp)""",
            (start_date,),
        )
        productivity_rows = {r[0]: r[1] for r in db.c.fetchall()}
        
        if len(metrics_rows) < 3:
            return json.dumps({"correlations": {}, "message": "Need at least 3 days of data"})
        
        # Build aligned arrays
        dates = []
        sleep_hours = []
        sleep_quality = []
        energy_level = []
        stress_level = []
        productivity = []
        
        for row in metrics_rows:
            date = row[0]
            dates.append(date)
            sleep_hours.append(row[1] or 0)
            sleep_quality.append(row[2] or 0)
            energy_level.append(row[3] or 0)
            stress_level.append(row[4] or 0)
            productivity.append(productivity_rows.get(date, 0))
        
        # Calculate correlations using numpy
        correlations = {}
        if len(sleep_hours) >= 3:
            correlations["sleep_hours_vs_productivity"] = float(np.corrcoef(sleep_hours, productivity)[0, 1])
            correlations["sleep_quality_vs_productivity"] = float(np.corrcoef(sleep_quality, productivity)[0, 1])
            correlations["energy_vs_productivity"] = float(np.corrcoef(energy_level, productivity)[0, 1])
            correlations["stress_vs_productivity"] = float(np.corrcoef(stress_level, productivity)[0, 1])
            correlations["sleep_hours_vs_energy"] = float(np.corrcoef(sleep_hours, energy_level)[0, 1])
            correlations["sleep_quality_vs_stress"] = float(np.corrcoef(sleep_quality, stress_level)[0, 1])
        
        return json.dumps({
            "correlations": correlations,
            "data_points": len(dates),
            "date_range": f"{start_date} to {end_date}"
        })

    def _get_insights(self, req: dict[str, Any]) -> str:
        """Generate behavioral insights based on correlations and patterns."""
        days = int(req.get("days", 30))
        corr_result = json.loads(self._get_correlations({"days": days}))
        correlations = corr_result.get("correlations", {})
        
        insights = []
        
        # Sleep insights
        sleep_prod = correlations.get("sleep_hours_vs_productivity", 0)
        if sleep_prod > 0.3:
            insights.append({
                "type": "positive",
                "title": "Sleep Boosts Productivity",
                "description": f"Strong correlation ({sleep_prod:.2f}) between sleep hours and focus time. Prioritize 7-8 hours.",
                "metric": "sleep_hours",
                "correlation": sleep_prod
            })
        elif sleep_prod < -0.3:
            insights.append({
                "type": "negative",
                "title": "Oversleeping May Reduce Focus",
                "description": f"Negative correlation ({sleep_prod:.2f}) suggests too much sleep correlates with less productivity.",
                "metric": "sleep_hours",
                "correlation": sleep_prod
            })
        
        # Energy insights
        energy_prod = correlations.get("energy_vs_productivity", 0)
        if energy_prod > 0.3:
            insights.append({
                "type": "positive",
                "title": "Energy Drives Focus",
                "description": f"High energy levels strongly correlate with productivity ({energy_prod:.2f}). Schedule deep work when energy peaks.",
                "metric": "energy_level",
                "correlation": energy_prod
            })
        
        # Stress insights
        stress_prod = correlations.get("stress_vs_productivity", 0)
        if stress_prod < -0.3:
            insights.append({
                "type": "warning",
                "title": "Stress Reduces Productivity",
                "description": f"High stress correlates with lower focus ({stress_prod:.2f}). Consider stress management techniques.",
                "metric": "stress_level",
                "correlation": stress_prod
            })
        
        # Sleep quality insights
        sleep_qual_prod = correlations.get("sleep_quality_vs_productivity", 0)
        if sleep_qual_prod > 0.3:
            insights.append({
                "type": "positive",
                "title": "Sleep Quality Matters",
                "description": f"Better sleep quality correlates with more focus ({sleep_qual_prod:.2f}). Focus on sleep hygiene.",
                "metric": "sleep_quality",
                "correlation": sleep_qual_prod
            })
        
        # Mood pattern insights
        db.c.execute(
            """SELECT mood_tags FROM daily_metrics WHERE date >= ? AND mood_tags IS NOT NULL AND mood_tags != '[]'""",
            (start_date,),
        )
        mood_rows = db.c.fetchall()
        mood_counts = {}
        for row in mood_rows:
            try:
                tags = json.loads(row[0])
                for tag in tags:
                    mood_counts[tag] = mood_counts.get(tag, 0) + 1
            except:
                pass
        
        if mood_counts:
            top_mood = max(mood_counts, key=mood_counts.get)
            insights.append({
                "type": "info",
                "title": f"Dominant Mood: {top_mood.capitalize()}",
                "description": f"Most frequent mood tag in last {days} days: '{top_mood}' ({mood_counts[top_mood]} times)",
                "metric": "mood",
                "data": mood_counts
            })
        
        return json.dumps({"insights": insights, "correlations": correlations})