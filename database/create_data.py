import logging
from contextlib import asynccontextmanager
# ✅ Change: Import the getter function instead of the variable
from database.initdb import get_pool 

@asynccontextmanager
async def get_db_conn():
    """
    Yield a database connection from the shared pool.
    """
    # ✅ Change: Get the live pool instance inside the call
    pool = get_pool()
    
    if pool is None:
        raise RuntimeError("❌ DB pool is not initialized")

    async with pool.connection() as conn:
        yield conn

# -----------------------
#   Insert Lead
# -----------------------
async def insert_lead(
    client,
    phone_number,
    username,
    summary,
    sentiment_label,
    sentiment_score,
):
    try:
        async with get_db_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO leads (
                        client,
                        phone_number,
                        username,
                        summary,
                        sentiment_label,
                        sentiment_score,
                        is_contacted
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                    """,
                    (
                        client,
                        phone_number,
                        username,
                        summary,
                        sentiment_label,
                        sentiment_score,
                    ),
                )
            await conn.commit()

        logging.info(f"✅ Lead saved to DB for: {phone_number}")

    except Exception as e:
        logging.error(f"❌ Failed to save lead to DB: {e}")
        raise

# -----------------------
#   Patch Lead Sentiment
# -----------------------
async def patch_lead_sentiment(
    phone_number: str,
    summary: str,
    sentiment_label: str,
    sentiment_score: float,
):
    query = """
        UPDATE leads
        SET
            summary = %s,
            sentiment_label = %s,
            sentiment_score = %s
        WHERE id = (
            SELECT id
            FROM leads
            WHERE phone_number = %s
            ORDER BY created_at DESC
            LIMIT 1
        );
    """

    try:
        async with get_db_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    (summary, sentiment_label, sentiment_score, phone_number),
                )
            await conn.commit()

        logging.info(f"✅ Patched sentiment for {phone_number}")

    except Exception as e:
        logging.error(f"❌ Patch failed: {e}")
        raise

# -----------------------
#   Insert Customers
# -----------------------
async def insert_customers(
    phone,
    password_hash,
    url,
    location,
):
    try:
        async with get_db_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO customers (
                        phone_number,
                        password_hash,
                        website_url,
                        location
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (phone, password_hash, url, location),
                )
            await conn.commit()

        logging.info(f"✅ Customer saved to DB: {phone}")

    except Exception as e:
        logging.error(f"❌ Failed to save customer to DB: {e}")
        raise