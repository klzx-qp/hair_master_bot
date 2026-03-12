from datetime import date, datetime, timedelta

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
)
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID, SCHEDULE_CHANNEL_ID
from database import Database
from keyboards.common import main_menu_kb, subscription_kb
from keyboards.calendar import build_month_inline_calendar
from states.booking_states import BookingStates

router = Router()

db: Database | None = None
bot = None
channel_id = None
schedule_channel_id = None


def init_user_booking_handlers(
    router_: Router, db_: Database, bot_instance, subscription_channel_id: int
):
    global db, bot, channel_id, schedule_channel_id
    db = db_
    bot = bot_instance
    channel_id = subscription_channel_id
    schedule_channel_id = SCHEDULE_CHANNEL_ID
    router_.include_router(router)


async def _check_subscription(user_id: int) -> bool:
    """
    Проверка подписки через getChatMember.
    """
    from config import CHANNEL_ID  # чтобы быть синхронными с config

    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ("member", "administrator", "creator"):
            return True
        return False
    except Exception:
        # Если канал недоступен/бот не админ — считаем, что не подписан
        return False


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    is_admin = message.from_user.id == ADMIN_ID
    text = (
        "<b>Здравствуйте!</b>\n\n"
        "Я бот для записи на процедуры по реконструкции волос.\n"
        "Выберите нужный пункт ниже:"
    )
    await message.answer(
        text=text,
        reply_markup=main_menu_kb(is_admin=is_admin),
    )


# ---------- Меню ----------

@router.callback_query(F.data == "menu_prices")
async def on_prices(call: CallbackQuery):
    text = (
        "<b>Прайс-лист:</b>\n\n"
        "Кератин/ ботокс — от <b>10.000 тг</b> до <b>35.000 тг</b> "
        "(так же доплата за густоту и ровный срез)\n"
        "Холодное восстановление — от <b>10.000 тг</b> до <b>30.000 тг</b>\n"
        "Пилинг кожи головы — от <b>10.000 тг</b> до <b>30.000 тг</b>\n"
    )
    await call.message.edit_text(text=text, reply_markup=main_menu_kb(is_admin=(call.from_user.id == ADMIN_ID)))
    await call.answer()


@router.callback_query(F.data == "menu_portfolio")
async def on_portfolio(call: CallbackQuery):
    text = "<b>Портфолио работ</b>\n\nНажмите кнопку ниже, чтобы посмотреть примеры работ."
    from keyboards.common import portfolio_kb

    await call.message.edit_text(
        text=text,
        reply_markup=portfolio_kb(),
    )
    await call.answer()


@router.callback_query(F.data == "menu_book")
async def on_menu_book(call: CallbackQuery, state: FSMContext):
    # Проверка подписки
    if not await _check_subscription(call.from_user.id):
        await call.message.edit_text(
            "Для записи необходимо подписаться на канал",
            reply_markup=subscription_kb(),
        )
        await call.answer()
        return

    # Проверка, что нет другой активной записи
    if db.user_has_active_booking(call.from_user.id):
        booking = db.get_user_active_booking(call.from_user.id)
        text = (
            "<b>У вас уже есть активная запись:</b>\n\n"
            f"Дата: <b>{booking['date']}</b>\n"
            f"Время: <b>{booking['time']}</b>\n\n"
            "Вы можете отменить её через пункт «Моя запись / Отменить»."
        )
        await call.message.edit_text(
            text=text,
        )
        await call.answer()
        return

    today = date.today()
    end_date = today + timedelta(days=30)
    avail_days = db.get_available_days_in_range(today.isoformat(), end_date.isoformat())

    if not avail_days:
        await call.message.edit_text(
            "К сожалению, сейчас нет доступных слотов для записи. "
            "Попробуйте позже или свяжитесь с мастером.",
        )
        await call.answer()
        return

    kb = build_month_inline_calendar(
        today.year, today.month, available_dates=avail_days, prefix="cal"
    )
    await state.set_state(BookingStates.choosing_date)
    await call.message.edit_text(
        "Выберите дату для записи (доступные дни помечены точкой):",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(F.data == "check_subscription")
async def on_check_subscription(call: CallbackQuery, state: FSMContext):
    if await _check_subscription(call.from_user.id):
        await call.message.edit_text(
            "Подписка подтверждена ✅\n\nТеперь вы можете записаться на приём.",
            reply_markup=main_menu_kb(is_admin=(call.from_user.id == ADMIN_ID)),
        )
    else:
        await call.answer(
            "Подписка не найдена. Подпишитесь и попробуйте ещё раз.", show_alert=True
        )


@router.callback_query(F.data == "menu_my_booking")
async def on_menu_my_booking(call: CallbackQuery, state: FSMContext):
    booking = db.get_user_active_booking(call.from_user.id)
    if not booking:
        await call.message.edit_text(
            "У вас нет активной записи.",
            reply_markup=main_menu_kb(is_admin=(call.from_user.id == ADMIN_ID)),
        )
        await call.answer()
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Отменить запись",
                    callback_data=f"user_cancel_booking:{booking['id']}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Назад в меню", callback_data="back_to_menu"
                )
            ],
        ]
    )

    text = (
        "<b>Ваша текущая запись:</b>\n\n"
        f"Дата: <b>{booking['date']}</b>\n"
        f"Время: <b>{booking['time']}</b>\n"
        f"Имя: <b>{booking['name']}</b>\n"
        f"Телефон: <b>{booking['phone']}</b>\n"
    )
    await call.message.edit_text(text=text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "back_to_menu")
async def on_back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "Главное меню:",
        reply_markup=main_menu_kb(is_admin=(call.from_user.id == ADMIN_ID)),
    )
    await call.answer()


@router.callback_query(F.data.startswith("user_cancel_booking:"))
async def on_user_cancel_booking(call: CallbackQuery):
    from scheduler import cancel_reminder

    _, booking_id_str = call.data.split(":")
    booking_id = int(booking_id_str)
    booking = db.get_booking_by_id(booking_id)
    if not booking or booking["status"] != "active":
        await call.answer("Запись уже была отменена или не найдена.", show_alert=True)
        return

    # Снова освободим слот
    slot = db.get_slot_by_id(booking["slot_id"])
    if slot:
        db.set_slot_available(slot["id"], True)

    db.cancel_booking(booking_id)
    cancel_reminder(booking_id, db)

    await call.message.edit_text(
        "Ваша запись отменена. Слот снова доступен для других клиентов.",
        reply_markup=main_menu_kb(is_admin=(call.from_user.id == ADMIN_ID)),
    )
    await call.answer()


# ---------- FSM бронирования ----------


@router.callback_query(BookingStates.choosing_date, F.data.startswith("cal:"))
async def on_choose_date(call: CallbackQuery, state: FSMContext):
    _, date_str = call.data.split(":", maxsplit=1)
    slots = db.get_day_slots(date_str, only_available=True)
    if not slots:
        await call.answer("На этот день нет доступных слотов.", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    kb_buttons = [
        [
            InlineKeyboardButton(
                text=s["time"], callback_data=f"time:{s['id']}"
            )
        ]
        for s in slots
    ]
    kb_buttons.append(
        [
            InlineKeyboardButton(
                text="Выбрать другую дату",
                callback_data="menu_book",
            )
        ]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    await state.update_data(selected_date=date_str)
    await state.set_state(BookingStates.choosing_time)

    await call.message.edit_text(
        f"Вы выбрали дату: <b>{date_str}</b>\n\nВыберите время:",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(BookingStates.choosing_date, F.data.startswith("cal_"))
async def on_calendar_nav(call: CallbackQuery, state: FSMContext):
    from datetime import datetime as dt
    import re
    from datetime import date as date_cls, timedelta as td

    today = date.today()
    end_date = today + timedelta(days=30)
    avail_days = db.get_available_days_in_range(
        today.isoformat(), end_date.isoformat()
    )

    # cal_prev:YYYY-MM
    kind, ym = call.data.split(":", maxsplit=1)
    _, direction = kind.split("_", maxsplit=1)
    year_str, month_str = ym.split("-")
    year = int(year_str)
    month = int(month_str)

    if direction == "prev":
        base = date(year, month, 15) - timedelta(days=31)
    else:
        base = date(year, month, 15) + timedelta(days=31)

    kb = build_month_inline_calendar(
        base.year, base.month, available_dates=avail_days, prefix="cal"
    )
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer()


@router.callback_query(BookingStates.choosing_time, F.data.startswith("time:"))
async def on_choose_time(call: CallbackQuery, state: FSMContext):
    _, slot_id_str = call.data.split(":")
    slot_id = int(slot_id_str)
    slot = db.get_slot_by_id(slot_id)
    if not slot or not slot["is_available"]:
        await call.answer("Этот слот уже недоступен. Выберите другой.", show_alert=True)
        return

    await state.update_data(slot_id=slot_id, slot_time=slot["time"], slot_date=slot["date"])
    await state.set_state(BookingStates.entering_name)

    await call.message.edit_text(
        f"Вы выбрали дату <b>{slot['date']}</b> и время <b>{slot['time']}</b>.\n\n"
        "Введите, пожалуйста, ваше имя:",
    )
    await call.answer()


@router.message(BookingStates.entering_name)
async def on_enter_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Имя не может быть пустым. Введите ещё раз:")
        return

    await state.update_data(name=name)
    await state.set_state(BookingStates.entering_phone)
    await message.answer("Отлично! Теперь введите номер телефона:")


@router.message(BookingStates.entering_phone)
async def on_enter_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if len(phone) < 5:
        await message.answer("Похоже на некорректный номер. Введите ещё раз:")
        return

    await state.update_data(phone=phone)
    data = await state.get_data()
    date_str = data["slot_date"]
    time_str = data["slot_time"]
    name = data["name"]

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить", callback_data="confirm_booking"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отменить", callback_data="cancel_booking_flow"
                )
            ],
        ]
    )

    text = (
        "<b>Проверьте данные записи:</b>\n\n"
        f"Дата: <b>{date_str}</b>\n"
        f"Время: <b>{time_str}</b>\n"
        f"Имя: <b>{name}</b>\n"
        f"Телефон: <b>{phone}</b>\n\n"
        "Если всё верно — подтвердите запись."
    )

    await state.set_state(BookingStates.confirming)
    await message.answer(text, reply_markup=kb)


@router.callback_query(BookingStates.confirming, F.data == "cancel_booking_flow")
async def on_cancel_booking_flow(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "Создание записи отменено.",
        reply_markup=main_menu_kb(is_admin=(call.from_user.id == ADMIN_ID)),
    )
    await call.answer()


@router.callback_query(BookingStates.confirming, F.data == "confirm_booking")
async def on_confirm_booking(call: CallbackQuery, state: FSMContext):
    from scheduler import schedule_reminder

    data = await state.get_data()
    slot_id = data["slot_id"]
    slot = db.get_slot_by_id(slot_id)
    if not slot or not slot["is_available"]:
        await call.answer(
            "Этот слот уже занят или недоступен. Попробуйте выбрать другой.",
            show_alert=True,
        )
        await state.clear()
        return

    if db.user_has_active_booking(call.from_user.id):
        await call.answer(
            "У вас уже есть активная запись. Сначала отмените её.",
            show_alert=True,
        )
        await state.clear()
        return

    # appointment_datetime — берём локально без таймзоны
    date_str = slot["date"]
    time_str = slot["time"]
    appointment_dt = datetime.fromisoformat(f"{date_str}T{time_str}:00")

    booking_id = db.create_booking(
        telegram_id=call.from_user.id,
        username=call.from_user.username,
        name=data["name"],
        phone=data["phone"],
        slot_id=slot_id,
        appointment_dt=appointment_dt,
    )
    if not booking_id:
        await call.answer(
            "Не удалось создать запись (возможно, у вас уже есть активная).",
            show_alert=True,
        )
        await state.clear()
        return

    # Планируем напоминание
    schedule_reminder(
        booking_id=booking_id,
        telegram_id=call.from_user.id,
        appointment_dt=appointment_dt,
        date_str=date_str,
        time_str=time_str,
        db=db,
    )

    # Сообщение администратору
    text_admin = (
        "<b>Новая запись!</b>\n\n"
        f"Дата: <b>{date_str}</b>\n"
        f"Время: <b>{time_str}</b>\n"
        f"Имя: <b>{data['name']}</b>\n"
        f"Телефон: <b>{data['phone']}</b>\n"
        f"Telegram ID: <code>{call.from_user.id}</code>\n"
        f"Username: @{call.from_user.username or 'нет'}"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text_admin)
    except Exception:
        pass

    # Сообщение в канал расписания
    text_channel = (
        "<b>Запись клиента:</b>\n\n"
        f"Дата: <b>{date_str}</b>\n"
        f"Время: <b>{time_str}</b>\n"
        f"Имя: <b>{data['name']}</b>\n"
        f"Телефон: <b>{data['phone']}</b>\n"
    )
    try:
        await bot.send_message(chat_id=schedule_channel_id, text=text_channel)
    except Exception:
        pass

    await state.clear()
    await call.message.edit_text(
        "Ваша запись успешно создана! ✨\n\n"
        f"Дата: <b>{date_str}</b>\n"
        f"Время: <b>{time_str}</b>\n",
        reply_markup=main_menu_kb(is_admin=(call.from_user.id == ADMIN_ID)),
    )
    await call.answer()