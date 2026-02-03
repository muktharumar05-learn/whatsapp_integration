import logging
from datetime import datetime, timezone
from database.create_data import insert_lead, patch_lead_sentiment # Assuming these exist

class LeadService:
    @staticmethod
    async def capture_initial_contact(client: str, user_mobile: str, username: str):
        """
        Step 1: Save the lead immediately with default values.
        Ensures no lead is lost if the AI or Scraper fails.
        """
        try:
            logging.info(f"Capturing initial contact for {user_mobile}")
            # Insert with sentiment 0.0 and placeholder summary
            await insert_lead(
                client=client,
                phone_number=user_mobile,
                username=username,
                summary="Conversation in progress...",
                sentiment_label="Neutral",
                sentiment_score=0.0
            )
        except Exception as e:
            logging.error(f"Failed to capture initial lead: {e}")

    @staticmethod
    async def enrich_lead_data(user_mobile: str, summary: str, label: str, score: float):
        """
        Step 2: Update the lead with AI-generated summary and sentiment.
        """
        try:
            logging.info(f"Enriching lead data for {user_mobile}")
            await patch_lead_sentiment(
                phone_number=user_mobile,
                summary=summary,
                sentiment_label=label,
                sentiment_score=score
            )
        except Exception as e:
            logging.error(f"Failed to enrich lead: {e}")