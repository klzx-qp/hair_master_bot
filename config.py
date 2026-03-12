import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администратора (число)
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

# Канал, куда отправляется расписание (отдельный служебный канал)
SCHEDULE_CHANNEL_ID = int(os.getenv("SCHEDULE_CHANNEL_ID", "-1001234567890"))

# Канал для обязательной подписки
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1001234567890"))
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/your_channel_link")

# Таймзона для напоминаний (можете поменять)
TIMEZONE = "Asia/Almaty"

# Путь к базе данных
DB_PATH = "database.sqlite3"