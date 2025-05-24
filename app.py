import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import smtplib
from email.message import EmailMessage
from streamlit_option_menu import option_menu
import plotly.express as px

# ------------------------
# Configs
# ------------------------
EMAIL_ACCOUNT = "geet6216@gmail.com"
EMAIL_PASSWORD = "fbqp quyj arfv opxr" 
DB_PATH = "tickets.db"

# Updated customer issues dictionary (only used for sidebar navigation)
customer_issues = {
    "Customer Support": [],
    "Last-Mile Delivery": [],
    "Line Haul Operations": [],
    "Warehouse Operations": [],
    "Returns and Refunds": [],
    "Billing & Finance": [],
    "Tech Support": [],
    "Customs and Clearance": [],
    "Security & Risk": [],
    "Sales & Accounts": []
}

# ------------------------
# Helper Functions
# ------------------------
def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def load_tickets():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM tickets", conn)
    conn.close()
    # Convert timestamp to datetime and add a date column for time series analysis
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date
    return df

def update_ticket_status(ticket_id, reply_text):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET status = ?, reply = ? WHERE id = ?", ("closed", reply_text, ticket_id))
    conn.commit()
    conn.close()

def send_reply(to_email, subject, body):
    msg = EmailMessage()
    msg["Subject"] = f"Re: {subject}"
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        smtp.send_message(msg)

# ------------------------
# Sidebar Navigation
# ------------------------
st.set_page_config(page_title="Email Ticket Dashboard", layout="wide")

with st.sidebar:
    selected_page = option_menu(
        menu_title=None,
        options=["🏠 Home"] + list(customer_issues.keys()),
        icons=["house", "people", "box", "truck", "robot", "envelope", "user-check", "shield", "bar-chart"],
        menu_icon="cast",
        default_index=0,
        orientation="vertical",
        styles={
            "container": {"padding": "0!important"},
            "icon": {"color": "gray", "font-size": "16px"},
            "nav-link": {
                "font-size": "14px",
                "text-align": "left",
                "margin": "2px",
                "padding": "6px 8px",
            },
            "nav-link-selected": {"background-color": "#ff4b4b", "color": "white"},
        }
    )

df = load_tickets()

# ------------------------
# Home Page
# ------------------------
if selected_page == "🏠 Home":
    st.title("📈 General Ticket Stats")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Mails", len(df))
    col2.metric("Positive", len(df[df["sentiment"] == "Positive"]))
    col3.metric("Negative", len(df[df["sentiment"] == "Negative"]))
    col4.metric("Open Tickets", len(df[df["status"] == "open"]))

    st.subheader("📊 Issue Category Breakdown")
    # Bar chart for issue categories
    issue_counts = df["issue_category"].value_counts().reset_index()
    issue_counts.columns = ["Issue Category", "Count"]
    fig_bar = px.bar(issue_counts, x="Issue Category", y="Count", title="Tickets by Issue Category")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("🟢 Sentiment Distribution")
    sentiment_counts = df["sentiment"].value_counts().reset_index()
    sentiment_counts.columns = ["Sentiment", "Count"]
    fig_pie = px.pie(sentiment_counts, names="Sentiment", values="Count", title="Sentiment Distribution", hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("📅 Ticket Volume Over Time")
    # Group by date to see ticket volume
    time_series = df.groupby("timestamp").size().reset_index(name="Count")
    fig_line = px.line(time_series, x="timestamp", y="Count", title="Tickets Over Time")
    st.plotly_chart(fig_line, use_container_width=True)

    st.subheader("📬 Recent Tickets")
    st.dataframe(df.sort_values(by="timestamp", ascending=False).head(10))

# ------------------------
# Issue Category Specific Pages
# ------------------------
else:
    st.title(f"👥 {selected_page} Tickets")
    team_df = df[df["issue_category"] == selected_page].sort_values(by="timestamp", ascending=False)

    col1, col2 = st.columns(2)
    col1.metric("Total Tickets", len(team_df))
    col2.metric("Open Tickets", len(team_df[team_df["status"] == "open"]))

    st.subheader("📌 Open Tickets")
    open_df = team_df[team_df["status"] == "open"]
    for _, row in open_df.iterrows():
        with st.expander(f"🔹 [{row['timestamp'].strftime('%Y-%m-%d %H:%M')}] {row['subject']}"):
            st.markdown(f"**From:** {row['sender']}")
            st.markdown(f"**Body:** {row['body']}")
            st.markdown(f"**Sentiment:** {row['sentiment']}")
            st.markdown(f"**Specific Issue:** {row['specific_issue']}")
            reply_text = st.text_area(f"✍️ Your Reply (Ticket ID: {row['id']})", key=f"reply_{row['id']}")
            if st.button("✅ Send & Close Ticket", key=f"close_{row['id']}"):
                try:
                    send_reply(row["sender"], row["subject"], reply_text)
                    update_ticket_status(row["id"], reply_text)
                    st.success("Ticket closed and email sent ✅")
                    st.experimental_rerun()
                except Exception as e:
                    pass

    st.subheader("📁 Closed Tickets")
    closed_df = team_df[team_df["status"] == "closed"]
    st.dataframe(closed_df[["timestamp", "sender", "subject", "specific_issue", "reply"]])
