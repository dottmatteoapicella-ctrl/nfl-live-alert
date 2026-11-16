
import os
import requests

token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]

url = f"https://api.telegram.org/bot{token}/sendMessage"

response = requests.post(
    url,
    data={
        "chat_id": chat_id,
        "text": "🏈 TEST NFL\n\n✅ Collegamento Telegram funzionante!",
    },
    timeout=20,
)

response.raise_for_status()
print("Messaggio Telegram NFL inviato correttamente!")
