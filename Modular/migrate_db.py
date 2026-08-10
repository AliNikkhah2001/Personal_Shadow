import sqlite3
import uuid
from datetime import datetime


def migrate_database():
    print("🔍 Scanning database for missing Sync UUIDs...")
    conn = sqlite3.connect("second_brain.db")
    c = conn.cursor()

    # All tables that require syncing
    tables = [
        "courses", "pomodoro_sessions", "cascading_goals", "habits",
        "habit_logs", "flashcards", "quizzes", "focus_queue", "queue", "notes",
        "health_profile", "health_logs", "custom_foods", "custom_activities", "health_plans"
    ]

    # Dynamically fetch tables that actually exist in your DB
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [r[0] for r in c.fetchall()]

    for table in tables:
        if table not in existing_tables:
            continue

        c.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in c.fetchall()]

        # 1. Add columns if missing
        if "uuid" not in columns:
            try:
                print(f"  -> Adding sync tracking to '{table}'...")
                c.execute(f"ALTER TABLE {table} ADD COLUMN uuid TEXT UNIQUE")
                c.execute(f"ALTER TABLE {table} ADD COLUMN modified_at TEXT")
            except Exception as e:
                print(f"  [!] Error altering {table}: {e}")

        # 2. Populate old data with new UUIDs
        c.execute(f"SELECT id FROM {table} WHERE uuid IS NULL")
        rows = c.fetchall()
        if rows:
            print(f"  -> Generating UUIDs for {len(rows)} legacy rows in '{table}'...")
            for r in rows:
                new_uuid = uuid.uuid4().hex
                now = datetime.now().isoformat()
                c.execute(f"UPDATE {table} SET uuid=?, modified_at=? WHERE id=?", (new_uuid, now, r[0]))

    conn.commit()
    conn.close()
    print("\n✅ Migration complete! Your entire database is now 100% Sync-ready.")

if __name__ == "__main__":
    migrate_database()
