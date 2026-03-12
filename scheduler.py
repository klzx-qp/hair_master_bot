from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from config import TIMEZONE
from database import Database

scheduler: AsyncIOScheduler | None = None
_bot: Bot | None = None
_db: Database | None = None


def setup_scheduler(bot: Bot, db: Database) -> AsyncIOScheduler:
    global scheduler, _bot, _db
    _bot = bot
    _db = db
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.start()
    return scheduler


async def reminder_job(telegram_id: int, date_str: str, time_str: str):
    if _bot is None:
        return
    text = (
        f"Напоминаем, что вы записаны на наращивание ресниц "
        f"завтра в <b>{time_str}</b>.\n"
        f"Ждём вас ❤️"
    )
    await _bot.send_message(chat_id=telegram_id, text=text)


def schedule_reminder(
    booking_id: int,
    telegram_id: int,
    appointment_dt: datetime,
    date_str: str,
    time_str: str,
    db: Database,
):
    """
    Создаёт напоминание за 24 часа до визита.
    Если до визита меньше 24 часов, напоминание не создаётся.
    """
    if scheduler is None:
        return

    now = datetime.now(appointment_dt.tzinfo) if appointment_dt.tzinfo else datetime.now()
    delta = appointment_dt - now
    if delta < timedelta(hours=24):
        return

    reminder_time = appointment_dt - timedelta(hours=24)
    job_id = f"reminder_{booking_id}"

    scheduler.add_job(
        reminder_job,
        "date",
        id=job_id,
        run_date=reminder_time,
        args=(telegram_id, date_str, time_str),
        replace_existing=True,
    )

    db.attach_reminder(booking_id, job_id, reminder_time.isoformat())


def cancel_reminder(booking_id: int, db: Database):
    if scheduler is None:
        return
    booking = db.get_booking_by_id(booking_id)
    if booking and booking["reminder_job_id"]:
        job_id = booking["reminder_job_id"]
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
        db.clear_reminder(booking_id)


def restore_reminders(db: Database):
    """
    Восстанавливаем задачи после перезапуска бота.
    """
    if scheduler is None:
        return

    now_iso = datetime.utcnow().isoformat()
    rows = db.get_future_bookings_with_reminders(now_iso)
    for row in rows:
        appointment_dt = datetime.fromisoformat(row["appointment_datetime"])
        reminder_time = datetime.fromisoformat(row["reminder_time"])
        if reminder_time <= datetime.utcnow():
            continue

        job_id = row["reminder_job_id"]
        scheduler.add_job(
            reminder_job,
            "date",
            id=job_id,
            run_date=reminder_time,
            args=(row["telegram_id"], row["date"], row["time"]),
            replace_existing=True,
        )