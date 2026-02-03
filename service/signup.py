import logging
from database import initdb  
from database.create_data import insert_customers
from service.security import hash_password
from scrape.scrape import crawl_website
from rag.ingest import RagIngest

async def register_new_customer(phone, password, url, location, background_tasks):
    # 1. Validation
    if len(phone) < 12 or not phone.startswith("+") or not phone[-10:].isdigit():
        raise ValueError("Invalid phone number format. Use +1234567890")

    try:
        hashed_pw = hash_password(password) 
        
        # 2. Save Customer to DB
        # Note: If phone is UNIQUE in DB, this will raise an Exception if it exists
        await insert_customers(phone, hashed_pw, url, location)
        logging.info(f"✅ Customer {phone} saved to DB.")

        # 3. Schedule Heavy Tasks
        background_tasks.add_task(run_onboarding_sequence, url, phone)
        
        return {
            "status": "success", 
            "message": "Registration successful! Processing website data..."
        }
        
    except Exception as e:
        # Check if it's a unique constraint violation (optional but helpful)
        if "already exists" in str(e).lower():
            logging.warning(f"Signup attempt for existing user: {phone}")
            return {"status": "error", "message": "Phone number already registered."}
            
        logging.error(f"Service Layer Error during signup for {phone}: {e}")
        raise
        
async def run_onboarding_sequence(url: str, phone: str):
    """
    Orchestrates the background tasks in a specific order.
    """
    try:
        # Step 1: Wait for scraping to finish
        logging.info(f"Starting crawl for {url}...")
        #await crawl_website(url, phone, max_pages=1000)
        
        # Step 2: Only start RAG once scraping is 100% done
        logging.info(f"Crawl complete. Starting RAG for {phone}...")
        rag_ingest = RagIngest()
        await rag_ingest.ingest_directory(phone)
    
        logging.info(f"Onboarding sequence finished for {phone}")
    except Exception as e:
        logging.error(f"Background Sequence Error for {phone}: {e}")