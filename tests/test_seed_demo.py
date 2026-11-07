import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

from scripts.seed_demo import CREATE_TABLE_SQL, ISSUE_DICTIONARY_JSON, seed_database


def test_schema_matches_db_definition(tmp_path):
    # Create DB using db.py's CREATE statement
    db_actual_path = tmp_path / "actual.db"
    conn_actual = sqlite3.connect(db_actual_path)
    cur_actual = conn_actual.cursor()
    cur_actual.execute("""
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
    cur_actual.execute("PRAGMA table_info(tickets)")
    columns_actual = cur_actual.fetchall()
    conn_actual.close()

    # Create DB using seed_demo's CREATE_TABLE_SQL
    db_seed_path = tmp_path / "seed.db"
    conn_seed = sqlite3.connect(db_seed_path)
    cur_seed = conn_seed.cursor()
    cur_seed.execute(CREATE_TABLE_SQL)
    cur_seed.execute("PRAGMA table_info(tickets)")
    columns_seed = cur_seed.fetchall()
    conn_seed.close()

    # Verify column definitions (name, type, notnull, default_value, pk) match
    assert [col[1:] for col in columns_actual] == [col[1:] for col in columns_seed]


def test_seed_demo_creates_60_rows(tmp_path):
    db_file = tmp_path / "demo.db"
    seed_database(str(db_file), seed=42)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM tickets")
    (count,) = cur.fetchone()
    conn.close()

    assert count == 60


def test_determinism_same_seed(tmp_path):
    db_file1 = tmp_path / "demo1.db"
    db_file2 = tmp_path / "demo2.db"

    seed_database(str(db_file1), seed=42)
    seed_database(str(db_file2), seed=42)

    conn1 = sqlite3.connect(db_file1)
    conn2 = sqlite3.connect(db_file2)

    rows1 = conn1.cursor().execute("SELECT * FROM tickets ORDER BY id").fetchall()
    rows2 = conn2.cursor().execute("SELECT * FROM tickets ORDER BY id").fetchall()

    conn1.close()
    conn2.close()

    assert len(rows1) == 60
    assert rows1 == rows2


def test_sender_address_strictly_example_com(tmp_path):
    db_file = tmp_path / "demo.db"
    seed_database(str(db_file), seed=42)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT sender FROM tickets")
    senders = [r[0] for r in cur.fetchall()]
    conn.close()

    assert len(senders) == 60
    for s in senders:
        assert s.endswith("@example.com")


def test_sentiment_status_and_category_coverage(tmp_path):
    db_file = tmp_path / "demo.db"
    seed_database(str(db_file), seed=42)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT sentiment, issue_category, specific_issue, status, timestamp FROM tickets")
    rows = cur.fetchall()
    conn.close()

    sentiments = {r[0] for r in rows}
    assert "Positive" in sentiments
    assert "Negative" in sentiments

    statuses = {r[3] for r in rows}
    assert "open" in statuses
    assert "closed" in statuses

    dict_categories = json.loads(ISSUE_DICTIONARY_JSON)

    for sentiment, category, specific_issue, status, timestamp_str in rows:
        if sentiment == "Positive":
            assert category == "No action required"
            assert specific_issue == "No action required"
        else:
            assert category in dict_categories
            assert specific_issue in dict_categories[category]

        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        # Ensure timestamp is a valid datetime within reasonable bounds
        assert dt <= datetime(2025, 1, 15, 12, 0, 0)
        assert dt >= datetime(2025, 1, 15, 12, 0, 0) - timedelta(days=14, seconds=5)


def test_cli_execution(tmp_path):
    db_file = tmp_path / "cli_demo.db"
    res = subprocess.run(
        [sys.executable, "scripts/seed_demo.py", "--db", str(db_file), "--seed", "42"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.returncode == 0
    assert "Demo database successfully seeded" in res.stdout

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT count(*), sum(status='open') FROM tickets")
    count, open_count = cur.fetchone()
    conn.close()

    assert count == 60
    assert open_count > 0
