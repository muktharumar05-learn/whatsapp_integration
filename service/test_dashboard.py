from datetime import datetime
import logging
from Service.dashboard import load_template_and_inject_rows

leads = [
    {
        "mobile_number": "+1234567890",
        "username": "John Doe",
        "conversation_summary": "Interested in product X",
        "sentiment_label": "Positive",
        "sentiment_score": 0.85,
        "last_active": datetime(2025, 12, 4, 12, 30, 0)
    },
    {
        "mobile_number": "+0987654321",
        "username": None,
        "conversation_summary": "Requested pricing info",
        "sentiment_label": "Neutral",
        "sentiment_score": 0.0,
        "last_active": None
    },
    {
        "mobile_number": "+0987654321",
        "username": None,
        "conversation_summary": "Requested pricing info",
        "sentiment_label": "Negative",
        "sentiment_score": -0.8,
        "last_active": None
    }
]

html_output = load_template_and_inject_rows(leads)

with open("test_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html_output)

logging.info("Dashboard HTML generated in test_dashboard.html")