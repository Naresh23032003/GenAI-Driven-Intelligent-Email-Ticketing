import sqlite3

conn = sqlite3.connect("tickets.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    sender TEXT,
    subject TEXT,
    body TEXT,
    sentiment TEXT,
    issue_category TEXT,
    specific_issue TEXT,
    status TEXT DEFAULT 'open',
    reply TEXT
)
""")

conn.commit()
conn.close()
print("✅ Database initialized successfully.")
