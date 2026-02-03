import logging
from contextlib import asynccontextmanager
from database import initdb  # Import the module

@asynccontextmanager
async def get_db_conn():
    """
    Yield a database connection from the shared pool.
    We use initdb.get_pool() to access the internal _pool safely.
    """
    try:
        # ✅ FIX: Call get_pool() instead of accessing .pool directly
        pool = initdb.get_pool()
        
        async with pool.connection() as conn:
            yield conn
    except Exception as e:
        logging.error(f"❌ Database pool error: {e}")
        raise

# -----------------------
#   Fetch All Leads for a Client  
# -----------------------

async def fetch_all_leads(client: str):
    try:
        async with get_db_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 
                        id, 
                        phone_number, 
                        username, 
                        summary,      
                        sentiment_label, 
                        sentiment_score, 
                        created_at as last_active
                    FROM leads
                    WHERE client = %s
                    ORDER BY id DESC
                    """,
                    (client,), 
                )

                rows = await cur.fetchall()
                return rows 

    except Exception as e:
        logging.error(f"Failed to retrieve leads from DB: {e}")
        raise

# -----------------------
#   Fetch User by Username
# -----------------------

async def fetch_user_by_username(username: str):
    try:
        async with get_db_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, phone_number, password_hash FROM customers WHERE phone_number = %s",
                    (username,),
                )
                row = await cur.fetchone()
                
                # ✅ Convert the tuple to a dict so user["password_hash"] works
                if row:
                    return {
                        "id": row[0],
                        "username": row[1],
                        "password_hash": row[2]
                    }
                return None
    except Exception as e:
        logging.error(f"Failed to retrieve user: {e}")
        raise