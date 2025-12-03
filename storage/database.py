import psycopg2
import os

DB_URL = os.getenv("DATABASE_URL")  # e.g., postgres://user:pass@host:port/dbname

def init_db():
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id SERIAL PRIMARY KEY,
                    mobile_number TEXT,
                    username TEXT,
                    summary TEXT,
                    sentiment_label TEXT,
                    sentiment_score REAL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()

def save_lead_to_db(mobile_number, username, summary, sentiment_label, sentiment_score):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO leads (mobile_number, username, summary, sentiment_label, sentiment_score)
                VALUES (%s, %s, %s, %s, %s)
            """, (mobile_number, username, summary, sentiment_label, sentiment_score))
        conn.commit()
