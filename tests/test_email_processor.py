import sqlite3
import json
from email.message import EmailMessage

import pytest

import email_processor
from email_processor import classify_email, extract_json, extract_email_content, process_email


class DummyChain:
    def __init__(self, return_value):
        self.return_value = return_value
        self.invoked_with = []

    def invoke(self, inputs):
        self.invoked_with.append(inputs)
        return self.return_value


def test_classify_email_issue_returns_not_json(monkeypatch):
    monkeypatch.setattr(email_processor, "chain_sentiment", DummyChain("negative"))
    monkeypatch.setattr(email_processor, "chain_issue", DummyChain("not json"))

    result = classify_email("s", "b")
    assert result == ("Negative", "Uncategorized", "Could not classify")


def test_classify_email_sentiment_positive_variations(monkeypatch):
    monkeypatch.setattr(email_processor, "chain_sentiment", DummyChain("Positive."))
    dummy_issue = DummyChain("irrelevant")
    monkeypatch.setattr(email_processor, "chain_issue", dummy_issue)

    result = classify_email("Great service!", "Thank you for the quick delivery.")
    assert result[0] == "Positive"
    assert result == ("Positive", "No action required", "No action required")
    # Issue chain should not be invoked for positive sentiment
    assert len(dummy_issue.invoked_with) == 0


@pytest.mark.parametrize("sentiment_str", ["positive", "Positive", " positive \n", "positive: highly satisfied"])
def test_classify_email_positive_starts_with(monkeypatch, sentiment_str):
    monkeypatch.setattr(email_processor, "chain_sentiment", DummyChain(sentiment_str))
    result = classify_email("s", "b")
    assert result == ("Positive", "No action required", "No action required")


def test_classify_email_valid_json(monkeypatch):
    monkeypatch.setattr(email_processor, "chain_sentiment", DummyChain("negative"))
    valid_json_response = json.dumps({
        "issue_category": "Last-Mile Delivery",
        "specific_issue": "Delivered to wrong address"
    })
    monkeypatch.setattr(email_processor, "chain_issue", DummyChain(valid_json_response))

    result = classify_email("Wrong package", "Delivered somewhere else")
    assert result == ("Negative", "Last-Mile Delivery", "Delivered to wrong address")


def test_classify_email_valid_json_with_surrounding_text(monkeypatch):
    monkeypatch.setattr(email_processor, "chain_sentiment", DummyChain("Negative."))
    issue_output = (
        "Here is the classification JSON:\n"
        '{"issue_category": "Billing & Finance", "specific_issue": "Overcharged on invoice"}\n'
        "Hope this helps!"
    )
    monkeypatch.setattr(email_processor, "chain_issue", DummyChain(issue_output))

    result = classify_email("Invoice query", "Overcharged")
    assert result == ("Negative", "Billing & Finance", "Overcharged on invoice")


def test_classify_email_invalid_json_inside_braces(monkeypatch):
    monkeypatch.setattr(email_processor, "chain_sentiment", DummyChain("negative"))
    monkeypatch.setattr(email_processor, "chain_issue", DummyChain("{ invalid json content }"))

    result = classify_email("s", "b")
    assert result == ("Negative", "Uncategorized", "Could not classify")


def test_classify_email_empty_json(monkeypatch):
    monkeypatch.setattr(email_processor, "chain_sentiment", DummyChain("negative"))
    monkeypatch.setattr(email_processor, "chain_issue", DummyChain("{}"))

    result = classify_email("s", "b")
    assert result == ("Negative", "Uncategorized", "Could not classify")


def test_extract_json():
    # Surround with markdown or preamble
    text = 'Some preamble\n{"issue_category": "Tech Support", "specific_issue": "App crash"}\nsome postscript'
    extracted = extract_json(text)
    assert extracted == '{"issue_category": "Tech Support", "specific_issue": "App crash"}'

    # No JSON present
    assert extract_json("No json here at all") is None
    assert extract_json("") is None


def test_extract_email_content_non_multipart():
    msg = EmailMessage()
    msg["Subject"] = "Test Subject"
    msg["From"] = "sender@example.com"
    msg.set_content("Hello, this is a plain text email.")

    from_, subject, body = extract_email_content(msg)
    assert from_ == "sender@example.com"
    assert subject == "Test Subject"
    assert body.strip() == "Hello, this is a plain text email."


def test_extract_email_content_multipart():
    msg = EmailMessage()
    msg["Subject"] = "Multipart Subject"
    msg["From"] = "alice@example.com"
    msg.add_alternative("Plain body content", subtype="plain")
    msg.add_alternative("<p>HTML body content</p>", subtype="html")

    from_, subject, body = extract_email_content(msg)
    assert from_ == "alice@example.com"
    assert subject == "Multipart Subject"
    assert "Plain body content" in body


def test_process_email_with_unparseable_output(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    # Initialize tickets database matching db.py
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

    # Stub chain_sentiment and chain_issue to return unparseable model output
    monkeypatch.setattr(email_processor, "chain_sentiment", DummyChain("negative"))
    monkeypatch.setattr(email_processor, "chain_issue", DummyChain("unparseable model output"))

    process_email("user@example.com", "Broken delivery", "My box was crushed.")

    # Check database content
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute("SELECT sender, subject, body, sentiment, issue_category, specific_issue FROM tickets")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 1
    sender, subject, body, sentiment, issue_category, specific_issue = rows[0]
    assert sender == "user@example.com"
    assert subject == "Broken delivery"
    assert body == "My box was crushed."
    assert sentiment == "Negative"
    assert issue_category == "Uncategorized"
    assert specific_issue == "Could not classify"
