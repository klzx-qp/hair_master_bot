from datetime import date, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID
from database import Database
from keyboards.admin import admin_menu_kb, slots_list_kb, bookings_list_kb
from keyboards.calendar import build_month_inline_calendar
from states.admin_states import AdminStates

router = Router()
db: Database | None = None


def init_admin_handlers(router_: Router, db_: Database):
    global db
    db = db_
    router_.include_router(router)


# ---------- Вход в админ-панель ----------

# Добавляем вход через текстовую команду /admin
@router.message(F.text == "/admin")
async def command_admin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав доступа.")
        return

    await state.set_state(AdminStates.choosing_action)
    await message.answer(
        "<b>Админ-панель</b>\nВыберите действие:",
        reply_markup=admin_menu_kb(),
    )

# Оставляем существующий вход через кнопку
@router.callback_query(F.data == "menu_admin")
async def on_menu_admin(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Доступ запрещён.", show_alert=True)
        return

    await state.set_state(AdminStates.choosing_action)
    await call.message.edit_text(
        "<b>Админ-панель</b>\nВыберите действие:",
        reply_markup=admin_menu_kb(),
    )
    await call.answer()


# ---------- Добавить рабочий день ----------


@router.callback_query(AdminStates.choosing_action, F.data == "admin_add_day")
async def on_admin_add_day(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.adding_day)
    await call.message.edit_text(
        "Введите дату рабочего дня в формате <b>ГГГГ-ММ-ДД</b> (например, 2026-03-15):"
    )
    await call.answer()


@router.message(AdminStates.adding_day)
async def on_admin_add_day_date(message: Message, state: FSMContext):
    date_str = message.text.strip()
    try:
        date.fromisoformat(date_str)
    except ValueError:
        await message.answer("Некорректный формат даты. Попробуйте ещё раз.")
        return

    db.add_day(date_str)
    await state.set_state(AdminStates.choosing_action)
    await message.answer(
        f"Рабочий день {date_str} добавлен.", reply_markup=admin_menu_kb()
    )


# ---------- Добавить слот ----------


@router.callback_query(AdminStates.choosing_action, F.data == "admin_add_slot")
async def on_admin_add_slot(call: CallbackQuery, state: FSMContext):
    today = date.today()
    end_date = today + timedelta(days=30)
    days = [d for d in db.get_available_days_in_range(today.isoformat(), end_date.isoformat())]
    # Для добавления слота можем показывать календарь без фильтра, но проще использовать уже доступные
    kb = build_month_inline_calendar(
        today.year, today.month, available_dates=days, prefix="adm_slot_day"
    )
    await state.set_state(AdminStates.adding_slot_date)
    await call.message.edit_text(
        "Выберите дату, для которой хотите добавить слот:",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(AdminStates.adding_slot_date, F.data.startswith("adm_slot_day:"))
async def on_admin_choose_slot_day(call: CallbackQuery, state: FSMContext):
    _, date_str = call.data.split(":", maxsplit=1)
    await state.update_data(slot_date=date_str)
    await state.set_state(AdminStates.adding_slot_time)
    await call.message.edit_text(
        f"Выбрана дата: <b>{date_str}</b>.\n\nВведите время слота в формате <b>ЧЧ:ММ</b> (например, 14:00):"
    )
    await call.answer()


@router.message(AdminStates.adding_slot_time)
async def on_admin_add_slot_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    # простая проверка формата
    if len(time_str) != 5 or time_str[2] != ":":
        await message.answer("Некорректный формат времени. Введите в формате ЧЧ:ММ.")
        return

    data = await state.get_data()
    date_str = data["slot_date"]
    db.add_time_slot(date_str, time_str)
    await state.set_state(AdminStates.choosing_action)
    await message.answer(
        f"Слот {date_str} {time_str} добавлен.", reply_markup=admin_menu_kb()
    )


# ---------- Удалить слот ----------


@router.callback_query(AdminStates.choosing_action, F.data == "admin_delete_slot")
async def on_admin_delete_slot(call: CallbackQuery, state: FSMContext):
    today = date.today()
    end_date = today + timedelta(days=30)
    days = db.get_available_days_in_range(today.isoformat(), end_date.isoformat())
    if not days:
        await call.message.edit_text(
            "Нет дней с доступными слотами для удаления.",
            reply_markup=admin_menu_kb(),
        )
        await call.answer()
        return

    kb = build_month_inline_calendar(
        today.year, today.month, available_dates=days, prefix="adm_del_day"
    )
    await state.set_state(AdminStates.cancelling_booking_date)
    await call.message.edit_text(
        "Выберите дату, в которой хотите удалить слот:",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(AdminStates.cancelling_booking_date, F.data.startswith("adm_del_day:"))
async def on_admin_del_day_choose(call: CallbackQuery, state: FSMContext):
    _, date_str = call.data.split(":", maxsplit=1)
    slots = db.get_day_slots(date_str, only_available=False)
    if not slots:
        await call.answer("Нет слотов на эту дату.", show_alert=True)
        return

    await state.update_data(del_slot_date=date_str)
    from keyboards.admin import slots_list_kb

    kb = slots_list_kb(slots)
    await call.message.edit_text(
        f"Выберите слот для удаления ({date_str}):",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin_slot:"))
async def on_admin_slot_delete(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Доступ запрещён.", show_alert=True)
        return

    _, slot_id_str = call.data.split(":", maxsplit=1)
    slot_id = int(slot_id_str)
    db.delete_time_slot(slot_id)
    await call.message.edit_text(
        "Слот удалён.", reply_markup=admin_menu_kb()
    )
    await state.set_state(AdminStates.choosing_action)
    await call.answer()


# ---------- Закрыть день ----------


@router.callback_query(AdminStates.choosing_action, F.data == "admin_close_day")
async def on_admin_close_day(call: CallbackQuery, state: FSMContext):
    today = date.today()
    end_date = today + timedelta(days=30)
    days = db.get_available_days_in_range(today.isoformat(), end_date.isoformat())
    if not days:
        await call.message.edit_text(
            "Нет рабочих дней, которые можно закрыть.",
            reply_markup=admin_menu_kb(),
        )
        await call.answer()
        return

    kb = build_month_inline_calendar(
        today.year, today.month, available_dates=days, prefix="adm_close"
    )
    await state.set_state(AdminStates.closing_day)
    await call.message.edit_text(
        "Выберите день, который хотите полностью закрыть:",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(AdminStates.closing_day, F.data.startswith("adm_close:"))
async def on_admin_close_day_choose(call: CallbackQuery, state: FSMContext):
    _, date_str = call.data.split(":", maxsplit=1)
    db.close_day(date_str)
    await state.set_state(AdminStates.choosing_action)
    await call.message.edit_text(
        f"День {date_str} закрыт. Все слоты стали недоступны.",
        reply_markup=admin_menu_kb(),
    )
    await call.answer()


# ---------- Просмотр расписания ----------


@router.callback_query(AdminStates.choosing_action, F.data == "admin_view_schedule")
async def on_admin_view_schedule(call: CallbackQuery, state: FSMContext):
    today = date.today()
    end_date = today + timedelta(days=30)
    days = db.get_available_days_in_range(today.isoformat(), end_date.isoformat())
    kb = build_month_inline_calendar(
        today.year, today.month, available_dates=days, prefix="adm_view"
    )
    await state.set_state(AdminStates.viewing_schedule_date)
    await call.message.edit_text(
        "Выберите дату для просмотра расписания (покажем только активные записи):",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(AdminStates.viewing_schedule_date, F.data.startswith("adm_view:"))
async def on_admin_view_schedule_date(call: CallbackQuery, state: FSMContext):
    _, date_str = call.data.split(":", maxsplit=1)
    bookings = db.get_bookings_for_date(date_str)
    if not bookings:
        text = f"На {date_str} активных записей нет."
    else:
        lines = [f"<b>Записи на {date_str}:</b>"]
        for b in bookings:
            lines.append(
                f"{b['time']} — {b['name']} (тел.: {b['phone']}, TG: {b['telegram_id']})"
            )
        text = "\n".join(lines)

    await call.message.edit_text(text, reply_markup=admin_menu_kb())
    await state.set_state(AdminStates.choosing_action)
    await call.answer()


# ---------- Отменить запись клиента ----------


@router.callback_query(AdminStates.choosing_action, F.data == "admin_cancel_booking")
async def on_admin_cancel_booking(call: CallbackQuery, state: FSMContext):
    today = date.today()
    end_date = today + timedelta(days=30)
    days = db.get_available_days_in_range(today.isoformat(), end_date.isoformat())
    if not days:
        await call.message.edit_text(
            "В ближайший месяц нет рабочих дней с активными записями.",
            reply_markup=admin_menu_kb(),
        )
        await call.answer()
        return

    kb = build_month_inline_calendar(
        today.year, today.month, available_dates=days, prefix="adm_cb"
    )
    await state.set_state(AdminStates.cancelling_booking_date)
    await call.message.edit_text(
        "Выберите дату, на которую хотите отменить запись клиента:",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(AdminStates.cancelling_booking_date, F.data.startswith("adm_cb:"))
async def on_admin_cancel_booking_date(call: CallbackQuery, state: FSMContext):
    _, date_str = call.data.split(":", maxsplit=1)
    bookings = db.get_bookings_for_date(date_str)
    if not bookings:
        await call.answer("На эту дату записей нет.", show_alert=True)
        return

    await state.update_data(cancel_booking_date=date_str)
    kb = bookings_list_kb(bookings)
    await state.set_state(AdminStates.choosing_booking_to_cancel)
    await call.message.edit_text(
        f"Выберите запись для отмены ({date_str}):",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(AdminStates.choosing_booking_to_cancel, F.data.startswith("admin_booking:"))
async def on_admin_cancel_booking_choose(call: CallbackQuery, state: FSMContext):
    from scheduler import cancel_reminder

    _, booking_id_str = call.data.split(":", maxsplit=1)
    booking_id = int(booking_id_str)
    booking = db.get_booking_by_id(booking_id)
    if not booking or booking["status"] != "active":
        await call.answer("Запись не найдена или уже отменена.", show_alert=True)
        return

    slot = db.get_slot_by_id(booking["slot_id"])
    if slot:
        db.set_slot_available(slot["id"], True)

    db.cancel_booking(booking_id)
    cancel_reminder(booking_id, db)

    await call.message.edit_text(
        "Запись клиента отменена, слот снова доступен.",
        reply_markup=admin_menu_kb(),
    )
    await state.set_state(AdminStates.choosing_action)
    await call.answer()


@router.callback_query(F.data == "admin_cancel")
async def on_admin_cancel_any(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.choosing_action)
    await call.message.edit_text(
        "Действие отменено.", reply_markup=admin_menu_kb()
    )
    await call.answer()