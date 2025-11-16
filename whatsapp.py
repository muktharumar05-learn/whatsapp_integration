from fastapi import FastAPI
import requests
import yaml

app = FastAPI()

with open("config.yaml", 'r') as file:
    config = yaml.safe_load(file)
    TOKEN = config['TOKEN']
    PHONE_NUMBER_ID = config['PHONE_NUMBER_ID']

BASE_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
HEADERS = {
    "Authorization": f"Bearer " + TOKEN,
    "Content-Type": "application/json"
}

def send_whatsapp_message(payload):
    return requests.post(BASE_URL, json=payload, headers=HEADERS).json()


@app.post("/send/text")
def send_text_api(to: str, message: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    return send_whatsapp_message(payload)


@app.post("/send/image")
def send_image_api(to: str, url: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": url}
    }
    return send_whatsapp_message(payload)


@app.post("/send/document")
def send_doc_api(to: str, url: str, filename: str = "file.pdf"):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": {"link": url, "filename": filename}
    }
    return send_whatsapp_message(payload)


@app.post("/send/template")
def send_template_api(to: str, template: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": "en_US"}
        }
    }
    return send_whatsapp_message(payload)
