import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'taxi_bot_db'
}

TRIP_TYPES = {
    'to_ufa': 'В Уфу',
    'from_ufa': 'Из Уфы'
}

MAX_SEATS = 4

# Список админов (ID Telegram)
ADMIN_IDS = [7117000356]
