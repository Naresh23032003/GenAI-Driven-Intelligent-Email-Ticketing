import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import streamlit_option_menu
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
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
        """
    )
    conn.commit()
    conn.close()


def test_env_example_contains_all_config_variables():
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    keys = {
        line.split("=", 1)[0].strip()
        for line in env_example.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert {
        "EMAIL_ACCOUNT",
        "EMAIL_PASSWORD",
        "IMAP_SERVER",
        "DB_PATH",
        "OLLAMA_MODEL",
    }.issubset(keys)


def test_no_hardcoded_password_or_fedex_in_app_and_processor():
    for filename in ("app.py", "email_processor.py"):
        content = (REPO_ROOT / filename).read_text(encoding="utf-8")
        assert "password" not in content
        assert "FedEx" not in content


def test_db_py_uses_db_path_env_var(tmp_path):
    db_file = tmp_path / "custom_tickets.db"
    env = os.environ.copy()
    env["DB_PATH"] = str(db_file)

    res = subprocess.run(
        [sys.executable, str(REPO_ROOT / "db.py")],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.returncode == 0
    assert db_file.exists()

    conn = sqlite3.connect(db_file)
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    conn.close()
    assert "tickets" in tables


def test_email_processor_reads_env_vars(tmp_path):
    db_file = tmp_path / "proc_tickets.db"
    env = os.environ.copy()
    env.update(
        {
            "EMAIL_ACCOUNT": "support@example.com",
            "EMAIL_PASSWORD": "app-secret-value",
            "IMAP_SERVER": "imap.example.com",
            "DB_PATH": str(db_file),
            "OLLAMA_MODEL": "llama3.2",
        }
    )

    code = (
        "import json, email_processor as ep; "
        "print(json.dumps({"
        "'EMAIL_ACCOUNT': ep.EMAIL_ACCOUNT, "
        "'EMAIL_PASSWORD': ep.EMAIL_PASSWORD, "
        "'IMAP_SERVER': ep.IMAP_SERVER, "
        "'DB_PATH': ep.DB_PATH, "
        "'OLLAMA_MODEL': ep.OLLAMA_MODEL, "
        "'model': ep.model.model"
        "}))"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    import json

    values = json.loads(res.stdout.strip())
    assert values == {
        "EMAIL_ACCOUNT": "support@example.com",
        "EMAIL_PASSWORD": "app-secret-value",
        "IMAP_SERVER": "imap.example.com",
        "DB_PATH": str(db_file),
        "OLLAMA_MODEL": "llama3.2",
        "model": "llama3.2",
    }


def test_requirements_has_safe_langchain_core_pin():
    lines = [
        line.strip()
        for line in (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    packages = {}
    for line in lines:
        match = re.match(r"^([A-Za-z0-9_.-]+)(==|>=)(.+)$", line)
        assert match, f"Expected pinned requirement line, got: {line}"
        packages[match.group(1).lower()] = (match.group(2), match.group(3))

    for required in (
        "streamlit",
        "pandas",
        "plotly",
        "streamlit-option-menu",
        "langchain-ollama",
        "langchain-core",
    ):
        assert required in packages, f"Missing {required} in requirements.txt"

    _, lc_version = packages["langchain-core"]
    parsed = tuple(int(part) for part in lc_version.split(".")[:3])
    assert parsed >= (0, 3, 81), f"langchain-core must be >= 0.3.81, got {lc_version}"


def test_dashboard_send_and_close_ticket_reduces_open_count(tmp_path, monkeypatch):
    db_file = tmp_path / "dashboard.db"
    _init_db(db_file)

    conn = sqlite3.connect(db_file)
    conn.executemany(
        """
        INSERT INTO tickets
            (timestamp, sender, subject, body, sentiment, issue_category, specific_issue, status, reply)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "2026-11-20 10:00:00",
                "alice@example.com",
                "Delayed response",
                "Still waiting on my ticket.",
                "Negative",
                "Customer Support",
                "Delayed response from support team",
                "open",
                None,
            ),
            (
                "2026-11-20 09:00:00",
                "bob@example.com",
                "Follow up",
                "Need an update on order #123.",
                "Negative",
                "Customer Support",
                "Repeated follow-ups with no resolution",
                "open",
                None,
            ),
            (
                "2026-11-19 08:00:00",
                "carol@example.com",
                "Resolved case",
                "Issue already handled.",
                "Negative",
                "Customer Support",
                "Unable to reach support via call or email",
                "closed",
                "Thanks for reaching out.",
            ),
        ],
    )
    conn.commit()
    conn.close()

    sent_messages = []

    class DummySMTP:
        def __init__(self, host, port):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, user, pwd):
            self.creds = (user, pwd)

        def send_message(self, msg):
            sent_messages.append(msg)

    import smtplib

    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("EMAIL_ACCOUNT", "agent@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "test-pass")
    monkeypatch.setattr(smtplib, "SMTP_SSL", DummySMTP)
    monkeypatch.setattr(
        streamlit_option_menu,
        "option_menu",
        lambda *args, **kwargs: "Customer Support",
    )

    at = AppTest.from_file(str(REPO_ROOT / "app.py"))
    at.run()

    assert not at.exception
    metrics_before = {m.label: m.value for m in at.metric}
    assert metrics_before["Total Tickets"] == "3"
    assert metrics_before["Open Tickets"] == "2"

    at.text_area[0].input("We have resolved your issue.").run()
    at.button[0].click().run()

    assert not at.exception
    metrics_after = {m.label: m.value for m in at.metric}
    assert metrics_after["Total Tickets"] == "3"
    assert metrics_after["Open Tickets"] == "1"

    assert len(sent_messages) == 1
    assert sent_messages[0]["To"] == "alice@example.com"
    assert sent_messages[0]["Subject"] == "Re: Delayed response"

    conn = sqlite3.connect(db_file)
    open_count = conn.execute(
        "SELECT count(*) FROM tickets WHERE status = 'open'"
    ).fetchone()[0]
    closed_row = conn.execute(
        "SELECT status, reply FROM tickets WHERE sender = 'alice@example.com'"
    ).fetchone()
    conn.close()

    assert open_count == 1
    assert closed_row == ("closed", "We have resolved your issue.")
