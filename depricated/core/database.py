import sqlite3

class DatabaseManager:
    def __init__(self, db_name="second_brain.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.c = self.conn.cursor()
        self.setup()
        
    def setup(self):
        self.c.executescript('''
            CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, task TEXT, is_done BOOLEAN, quadrant TEXT);
            CREATE TABLE IF NOT EXISTS pomodoro_sessions (id INTEGER PRIMARY KEY, course TEXT, duration INTEGER, actual_duration INTEGER, timestamp TEXT, type TEXT, distractions INTEGER DEFAULT 0, timelapse_path TEXT);
            CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT, timestamp TEXT);
            CREATE TABLE IF NOT EXISTS flashcards (id INTEGER PRIMARY KEY, course TEXT, front TEXT, back TEXT);
            CREATE TABLE IF NOT EXISTS saved_quizzes (id INTEGER PRIMARY KEY, title TEXT, course TEXT, filepath TEXT);
            CREATE TABLE IF NOT EXISTS exams (id INTEGER PRIMARY KEY, course TEXT, score INTEGER, total INTEGER, date TEXT);
            CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, course TEXT, duration INTEGER, type TEXT, list_order INTEGER, distractions TEXT, worked REAL, timelapse_path TEXT, start_time TEXT);
            CREATE TABLE IF NOT EXISTS starred_questions (id INTEGER PRIMARY KEY, course TEXT, question TEXT, data_json TEXT);
            CREATE TABLE IF NOT EXISTS course_targets (course TEXT PRIMARY KEY, target_hours REAL);
            
            -- NEW: Cascading Goals & Habit Matrix
            CREATE TABLE IF NOT EXISTS life_goals (id INTEGER PRIMARY KEY, parent_id INTEGER, title TEXT, target_hours REAL, category TEXT, deadline TEXT, status TEXT);
            CREATE TABLE IF NOT EXISTS habits (id INTEGER PRIMARY KEY, name TEXT, type TEXT);
            CREATE TABLE IF NOT EXISTS habit_logs (id INTEGER PRIMARY KEY, habit_id INTEGER, date TEXT, value TEXT);
        ''')
        # Migrations
        migrations = [
            "ALTER TABLE courses ADD COLUMN target_hours REAL DEFAULT 0",
            "ALTER TABLE pomodoro_sessions ADD COLUMN distraction_data TEXT"
        ]
        for mig in migrations:
            try: self.c.execute(mig)
            except: pass
        self.conn.commit()

db = DatabaseManager()
