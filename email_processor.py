import imaplib
import email
from email.header import decode_header
import sqlite3
import time
import json
import re
from datetime import datetime

from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

# Email credentials and server settings
EMAIL_ACCOUNT = "geet6216@gmail.com"
EMAIL_PASSWORD = "fbqp quyj arfv opxr" 
IMAP_SERVER = "imap.gmail.com"

# Provided issue dictionary
issue_dictionary = """
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

# Escape curly braces so that they are treated as literal text in the prompt template
escaped_issue_dictionary = issue_dictionary.replace("{", "{{").replace("}", "}}")

# Build the issue classification prompt template
template_issue = (
    "You are a helpful assistant at FedEx. Your task is to classify the following customer email into one of the issue categories and specific issues listed below.\n\n"
    "Use the following issue dictionary:\n"
    + escaped_issue_dictionary +
    "\n\n"
    "Return only the JSON object with no additional commentary. The JSON should be in the following format:\n"
    "{{{{\"issue_category\": \"<Chosen category>\", \"specific_issue\": \"<Chosen specific issue>\"}}}}\n\n"
    "Email Subject: {subject}\n"
    "Email Body: {body}\n\n"
    "Your classification:"
)

# Build the sentiment analysis prompt template
template_sentiment = (
    "You are a helpful assistant at FedEx. Your task is to determine if the following customer email is positive (e.g. an appreciation or compliment email) or negative (a complaint that requires attention).\n\n"
    "Return only one word: either 'positive' or 'negative'.\n\n"
    "Email Subject: {subject}\n"
    "Email Body: {body}\n\n"
    "Your answer:"
)

# Initialize the LLM model
model = OllamaLLM(model="llama3.1")

# Create prompt chains for sentiment analysis and issue classification
prompt_sentiment = ChatPromptTemplate.from_template(template_sentiment)
chain_sentiment = prompt_sentiment | model

prompt_issue = ChatPromptTemplate.from_template(template_issue)
chain_issue = prompt_issue | model

# Function to extract the first JSON object from a string using regex
def extract_json(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group()
    return None

# Classify the email by first checking sentiment and then classifying the issue if negative
def classify_email(subject, body):
    # Step 1: Check sentiment
    sentiment_result = chain_sentiment.invoke({"subject": subject, "body": body})
    sentiment = sentiment_result.strip().lower()
    print("Sentiment result:", sentiment)
    if sentiment == "positive":
        # Positive emails (e.g. appreciation) require no further action.
        return "Positive", "No action required","No action required"
    else:
        # Step 2: Classify issue for negative emails
        result = chain_issue.invoke({"subject": subject, "body": body})
        print("Raw classification output:", result)
        json_str = extract_json(result)
        if json_str:
            try:
                classification = json.loads(json_str)
                return (
                    "Negative",
                    classification.get("issue_category", "Uncategorized"),
                    classification.get("specific_issue", "Could not classify")
                )
            except Exception as e:
                print("JSON parsing error:", e)
        return "Uncategorized", "Could not classify"

# Function to extract email content from an IMAP message
def extract_email_content(msg):
    subject, encoding = decode_header(msg["Subject"])[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding or "utf-8", errors="ignore")
    from_ = msg.get("From")
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode(errors="ignore")
                except:
                    pass
                break
    else:
        try:
            body = msg.get_payload(decode=True).decode(errors="ignore")
        except:
            pass

    return from_, subject, body

# Function to process a single email and store it in the SQLite database
def process_email(from_, subject, body):
    senti, issue_category, specific_issue = classify_email(subject, body)
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tickets (timestamp, sender, subject, body, sentiment, issue_category, specific_issue)
        VALUES (?, ?, ?, ?, ?, ?,?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        from_,
        subject,
        body[:500],
        senti,
        issue_category,
        specific_issue
    ))
    conn.commit()
    conn.close()
    print(f"✅ Stored: {subject[:30]}...")

# Function to check for new emails via IMAP and process them
def check_email():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")
        _, messages = mail.search(None, "UNSEEN")
        for e_id in messages[0].split():
            _, data = mail.fetch(e_id, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            from_, subject, body = extract_email_content(msg)
            process_email(from_, subject, body)
        mail.logout()
    except Exception as e:
        print("❌ Error:", e)

if __name__ == "__main__":
    print("📬 Email processor started...")
    while True:
        check_email()
        time.sleep(6)  # Adjust the interval as needed
