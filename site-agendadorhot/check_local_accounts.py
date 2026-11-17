import sqlite3
from pathlib import Path

db_path = Path(r"C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler\data\scheduler.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT id, phone, first_name, username, is_active FROM telegram_accounts")
for r in cur.fetchall():
    print(r)
conn.close()
