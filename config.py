import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_CONFIG = {
    'host': 'localhost',         # Для MAMP используйте 'localhost'
    'user': 'root',              # По умолчанию пользователь в MAMP — root
    'password': 'root',          # Пароль root в MAMP
    'database': 'taxi_bot_db'    # Имя базы данных
}

TRIP_TYPES = {
    'to_ufa': 'В Уфу',
    'from_ufa': 'Из Уфы'
}

MAX_SEATS = 4
