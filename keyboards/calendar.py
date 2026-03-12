from datetime import date, timedelta
from calendar import monthrange

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_month_inline_calendar(
    year: int, month: int, available_dates: list[str] | None = None, prefix: str = "cal"
) -> InlineKeyboardMarkup:
    """
    Простенький календарь на месяц.
    available_dates: список строк 'YYYY-MM-DD', которые доступны (подсвечиваем).
    prefix: префикс в callback_data ('cal' для клиента, 'adm_day' для админа и т.п.)
    """
    if available_dates is None:
        available_dates = []

    kb: list[list[InlineKeyboardButton]] = []

    kb.append(
        [
            InlineKeyboardButton(
                text=f"{year}-{month:02d}", callback_data="ignore"
            )
        ]
    )

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.append(
        [InlineKeyboardButton(text=d, callback_data="ignore") for d in week_days]
    )

    first_weekday, days_in_month = monthrange(year, month)
    # monthrange: Пн=0 ... Вс=6, но нам надо, чтобы Пн был первым столбцом
    current_row: list[InlineKeyboardButton] = []
    # Пустые ячейки до первого дня
    for _ in range((first_weekday - 0) % 7):
        current_row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))

    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        d_str = d.isoformat()
        label = str(day)
        if d_str in available_dates:
            label = f"•{day}"
        current_row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=f"{prefix}:{d_str}",
            )
        )
        if len(current_row) == 7:
            kb.append(current_row)
            current_row = []
    if current_row:
        while len(current_row) < 7:
            current_row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
        kb.append(current_row)

    # Навигация по месяцам (max на 1 месяц вперёд/назад)
    current = date(year, month, 1)
    prev_month = current - timedelta(days=1)
    next_month = current + timedelta(days=31)
    kb.append(
        [
            InlineKeyboardButton(
                text="«", callback_data=f"{prefix}_prev:{prev_month.year}-{prev_month.month}"
            ),
            InlineKeyboardButton(
                text="»", callback_data=f"{prefix}_next:{next_month.year}-{next_month.month}"
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=kb)