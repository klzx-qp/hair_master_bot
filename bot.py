import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, CHANNEL_ID
from database import Database
from scheduler import setup_scheduler, restore_reminders
from handlers.user_booking import init_user_booking_handlers
from handlers.admin import init_admin_handlers
from handlers import misc as misc_handlers


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN в .env")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    db = Database()

    # Инициализация APScheduler
    setup_scheduler(bot, db)
    # Восстановление задач напоминаний из БД
    restore_reminders(db)

    # --- РЕГИСТРАЦИЯ ХЕНДЛЕРОВ (ПОРЯДОК ВАЖЕН!) ---
    
    # 1. Сначала админ (чтобы команды /admin и ввод слотов не перехватывались)
    init_admin_handlers(dp, db)
    
    # 2. Затем бронирование для пользователей
    init_user_booking_handlers(dp, db, bot, CHANNEL_ID)
    
    # 3. В самом конце — эхо-фильтр и прочие общие хендлеры
    dp.include_router(misc_handlers.router)

    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())