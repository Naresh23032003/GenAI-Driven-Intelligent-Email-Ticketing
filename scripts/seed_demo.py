import argparse
import json
import random
import sqlite3
from datetime import datetime, timedelta

CREATE_TABLE_SQL = """
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

# JSON matching email_processor.py:19-95
ISSUE_DICTIONARY_JSON = """
{
  "Customer Support": [
    "Delayed response from support team",
    "Rude or unhelpful interaction",
    "Repeated follow-ups with no resolution",
    "Incorrect information provided by agent",
    "Unable to reach support via call or email"
  ],
  "Last-Mile Delivery": [
    "Delivery delayed or missed",
    "Delivery agent unreachable",
    "Delivered to wrong address",
    "Package left unattended",
    "Damaged during delivery",
    "Failed delivery but marked delivered"
  ],
  "Line Haul Operations": [
    "Transit delay between hubs",
    "Truck breakdown affecting ETA",
    "Shipment held at hub",
    "Inter-hub misrouting",
    "In-transit package lost"
  ],
  "Warehouse Operations": [
    "Item missing in package",
    "Wrong item packed",
    "Package not dispatched from warehouse",
    "Barcode/scanning errors",
    "Inventory mismatch reported",
    "Order packed but not picked up"
  ],
  "Returns and Refunds": [
    "Return request not processed",
    "Refund delayed",
    "Pickup for return not scheduled",
    "Wrong item collected during return",
    "Dispute over refund amount"
  ],
  "Billing & Finance": [
    "Overcharged on invoice",
    "Wrong billing address",
    "Duplicate billing for same order",
    "Credit not reflected",
    "Payment gateway error",
    "Missing or delayed invoice"
  ],
  "Tech Support": [
    "App crash during checkout",
    "Cannot track order via app",
    "Login/authentication issues",
    "Order not showing in dashboard",
    "API integration failure (for B2B)"
  ],
  "Customs and Clearance": [
    "Customs delay at destination",
    "Missing KYC or invoice",
    "Package held due to restricted item",
    "Incorrect HS code used",
    "Duties/taxes not paid or unclear"
  ],
  "Security & Risk": [
    "Package tampered/stolen",
    "Suspicious activity on account",
    "Driver behavior concern",
    "Fraudulent order attempt",
    "Repeated delivery to blacklisted address"
  ],
  "Sales & Accounts": [
    "SLA breach reported by client",
    "Pickup commitment not honored",
    "Pricing mismatch for client account",
    "Unassigned account manager",
    "Request for rate revision"
  ]
}
"""

POSITIVE_SUBJECTS = [
    "Great service and prompt delivery",
    "Thank you for the quick resolution",
    "Wonderful support from the courier",
    "Excellent experience with FedEx delivery",
    "Appreciation for courteous delivery agent",
    "Smooth and seamless return process",
    "Impressive handling of our shipment",
    "Outstanding customer support experience",
]

POSITIVE_BODIES = [
    "I just wanted to drop a note saying thank you for delivering my shipment ahead of time!",
    "The courier driver was exceptionally polite and careful with our fragile package. Much appreciated!",
    "Customer service quickly resolved my question about the delivery schedule. Keep up the good work!",
    "Our entire team is grateful for the timely logistics support provided during our product launch.",
    "The package arrived safely in pristine condition. Excellent handling and communication throughout.",
]

CLOSED_REPLIES = [
    "Thank you for contacting us. We have investigated the issue and resolved it as requested.",
    "Our operations team has addressed this matter and confirmed the update. Please let us know if anything else is needed.",
    "A full credit adjustment has been applied to your account. We apologize for any inconvenience caused.",
    "The delivery status has been rectified and your local hub has been notified.",
    "Thank you for the positive feedback! We are always delighted to assist you.",
]


def seed_database(db_path: str, seed: int = 42, count: int = 60) -> None:
    rng = random.Random(seed)
    categories_dict = json.loads(ISSUE_DICTIONARY_JSON)
    categories_list = list(categories_dict.keys())

    # Reference baseline anchor for 14 days time span:
    base_time = datetime(2025, 1, 15, 12, 0, 0)

    # Deterministic generation:
    # 60 fake tickets across 10 categories, mixed positive and negative, mixed open and closed.
    # Out of 60 tickets, let's have ~15 positive and ~45 negative (with balanced coverage across all 10 categories).
    num_positive = 15
    num_negative = count - num_positive

    # We ensure negative tickets cover each of the 10 categories evenly first, then distribute remaining
    category_assignments = list(categories_list)
    # Remaining negative tickets:
    for _ in range(num_negative - len(categories_list)):
        category_assignments.append(rng.choice(categories_list))
    rng.shuffle(category_assignments)

    tickets_data = []

    # Prepare positive tickets
    for i in range(num_positive):
        sender = f"customer{i + 1:02d}@example.com"
        subject = rng.choice(POSITIVE_SUBJECTS)
        body = rng.choice(POSITIVE_BODIES)
        sentiment = "Positive"
        issue_cat = "No action required"
        spec_issue = "No action required"
        status = rng.choice(["open", "closed"])
        reply = rng.choice(CLOSED_REPLIES) if status == "closed" else None
        # Spread timestamps over the last 14 days
        offset_seconds = rng.randint(0, 14 * 24 * 3600)
        timestamp = (base_time - timedelta(seconds=offset_seconds)).strftime("%Y-%m-%d %H:%M:%S")

        tickets_data.append({
            "timestamp": timestamp,
            "sender": sender,
            "subject": subject,
            "body": body,
            "sentiment": sentiment,
            "issue_category": issue_cat,
            "specific_issue": spec_issue,
            "status": status,
            "reply": reply,
        })

    # Prepare negative tickets
    for i in range(num_negative):
        sender = f"customer{num_positive + i + 1:02d}@example.com"
        category = category_assignments[i]
        specific_issue = rng.choice(categories_dict[category])
        subject = f"Issue regarding {specific_issue.lower()}"
        body = f"Hello support team, I am encountering an issue with my shipment: {specific_issue}. Please address this as soon as possible."
        sentiment = "Negative"
        status = rng.choice(["open", "closed"])
        reply = rng.choice(CLOSED_REPLIES) if status == "closed" else None
        offset_seconds = rng.randint(0, 14 * 24 * 3600)
        timestamp = (base_time - timedelta(seconds=offset_seconds)).strftime("%Y-%m-%d %H:%M:%S")

        tickets_data.append({
            "timestamp": timestamp,
            "sender": sender,
            "subject": subject,
            "body": body,
            "sentiment": sentiment,
            "issue_category": category,
            "specific_issue": specific_issue,
            "status": status,
            "reply": reply,
        })

    # Shuffle the ticket list deterministically so order isn't all positive then all negative
    rng.shuffle(tickets_data)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)

    for item in tickets_data:
        cursor.execute(
            """
            INSERT INTO tickets (timestamp, sender, subject, body, sentiment, issue_category, specific_issue, status, reply)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["timestamp"],
                item["sender"],
                item["subject"],
                item["body"],
                item["sentiment"],
                item["issue_category"],
                item["specific_issue"],
                item["status"],
                item["reply"],
            ),
        )

    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Seed demo database with deterministic fake tickets.")
    parser.add_argument("--db", default="demo.db", help="Path to sqlite database file (default: demo.db)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    seed_database(args.db, seed=args.seed)
    print(f"✅ Demo database successfully seeded at {args.db}")


if __name__ == "__main__":
    main()
