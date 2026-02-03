import asyncio
from twilio.rest import Client
from dotenv import load_dotenv
import os
import yaml
import logging

load_dotenv()

# --- Load Twilio Credentials from environment variables ---
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

TWILIO_ACCOUNT_SID = os.getenv(config["Credentials"]["Twilio"]["TWILIO_ACCOUNT_SID"])
TWILIO_AUTH_TOKEN = os.getenv(config["Credentials"]["Twilio"]["TWILIO_AUTH_TOKEN"])
TWILIO_WHATSAPP_NUMBER = os.getenv(config["Credentials"]["Twilio"]["TWILIO_WHATSAPP_NUMBER"])

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

async def send_whatsapp_message(to: str, body: str):
    loop = asyncio.get_running_loop()

    def _send():
        return client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to,
            body=body,
        )
    message = await loop.run_in_executor(None, _send)
    logging.info(f"Sent WhatsApp message SID: {message.sid}")
    return message.sid