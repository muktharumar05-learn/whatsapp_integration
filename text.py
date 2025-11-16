import requests
import json
import yaml

with open("config.yaml", 'r') as file:
    config = yaml.safe_load(file)
    TOKEN = config['TOKEN']
    PHONE_NUMBER_ID = config['PHONE_NUMBER_ID']

def send_text(to, message):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.json()


print(send_text("+91-9611114994", "Hello from Python!"))
