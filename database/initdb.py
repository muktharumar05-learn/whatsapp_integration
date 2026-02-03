import os
import logging
from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool

DB_URL = os.getenv("DATABASE_URL")

# Internal variable
_pool: AsyncConnectionPool | None = None

def get_pool() -> AsyncConnectionPool:
    """
    Access the initialized pool. 
    Use this instead of importing the variable directly.
    """
    if _pool is None:
        raise RuntimeError("❌ DB pool is not initialized. Call init_pool() first.")
    return _pool

async def init_pool():
    global _pool

    if _pool is None:
        _pool = AsyncConnectionPool(
            DB_URL,
            min_size=1,
            max_size=10,
        )
        logging.info("✅ Database pool initialized")
        logging.info(f"pool: {_pool}")

async def close_pool():
    global _pool

    if _pool:
        await _pool.close()
        _pool = None
        logging.info("🛑 Database pool closed")

async def init_db():
    """
    Create required tables.
    Expects init_pool() to have been called by the lifespan.
    """
    pool = get_pool() # Use the getter to ensure we have the live pool
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # 1. Leads Table
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS leads (
                        id SERIAL PRIMARY KEY,
                        client TEXT NOT NULL,
                        phone_number TEXT UNIQUE NOT NULL,
                        username TEXT,
                        summary TEXT,
                        sentiment_label TEXT,
                        sentiment_score REAL,
                        is_contacted BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                logging.info("Leads table ensured.")
                
                # 2. Customers Table
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS customers (
                        id SERIAL PRIMARY KEY,
                        phone_number TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        website_url TEXT NOT NULL,
                        location TEXT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                logging.info("Customers table ensured.")
                
            await conn.commit()
        logging.info("Database initialized successfully")

    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        raise