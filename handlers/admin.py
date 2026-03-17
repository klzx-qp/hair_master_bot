from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

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

@router.message(Command("admin"))
async def command_admin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await state.set_state(AdminStates.choosing_action)
    await message.answer(
        "<b>Админ-панель</b>\nВыберите действие:", 
        reply_markup=admin_menu_kb()
    )

@router.callback_query(F.data == "menu_admin")
async def on_menu_admin(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Доступ запрещён.", show_alert=True)
        return
    await state.set_state(AdminStates.choosing_action)
    await call.message.edit_text(
        "<b>Админ-панель</b>\nВыберите действие:", 
        reply_markup=admin_menu_kb()
    )
    await call.answer()

# ---------- Добавление рабочего дня ----------

@router.callback_query(AdminStates.choosing_action, F.data == "admin_add_day")
async def on_admin_add_day(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_date)
    await call.message.edit_text(
        "Введите дату рабочего дня в формате <b>ГГГГ-ММ-ДД</b>\n"
        "Например: <code>2026-03-20</code>"
    )
    await call.answer()

@router.message(AdminStates.waiting_for_date)
async def process_admin_date(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    date_str = message.text.strip()
    if len(date_str) != 10 or date_str[4] != "-" or date_str[7] != "-":
        await message.answer("❌ Неверный формат! Введите дату точно как: 2026-03-20")
        return
    
    await state.update_data(chosen_date=date_str)
    await state.set_state(AdminStates.waiting_for_slots)
    await message.answer(
        f"✅ Дата <b>{date_str}</b> принята.\n\n"
        f"Теперь введите время через пробел.\n"
        f"Пример: <code>10:00 12:30 15:00 18:00</code>"
    )

@router.message(AdminStates.waiting_for_slots)
async def process_admin_slots(message: Message, state: FSMContext):
    global db
    if message.from_user.id != ADMIN_ID:
        return

    data = await state.get_data()
    date_str = data.get("chosen_date")
    slots = message.text.strip().split()

    if not slots:
        await message.answer("Вы не ввели время. Попробуйте еще раз через пробел.")
        return

    try:
        cur = db.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO work_days (date) VALUES (?)", (date_str,))
        cur.execute("SELECT id FROM work_days WHERE date = ?", (date_str,))
        day_id = cur.fetchone()[0]

        for s in slots:
            cur.execute(
                "INSERT INTO time_slots (day_id, time, is_available) VALUES (?, ?, 1)", 
                (day_id, s)
            )
        
        db.conn.commit()
        await state.clear()
        await message.answer(
            f"🎉 Готово! На <b>{date_str}</b> добавлено слотов: {len(slots)}.",
            reply_markup=admin_menu_kb()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка базы данных: {e}")

# ---------- Просмотр расписания (Исправленный) ----------

@router.callback_query(AdminStates.choosing_action, F.data == "admin_view_schedule")
async def on_admin_view_schedule(call: CallbackQuery, state: FSMContext):
    global db
    if call.from_user.id != ADMIN_ID:
        return

    try:
        cur = db.conn.cursor()
        # Запрос: берем дату, время и имя клиента для всех записей
        cur.execute("""
            SELECT b.booking_date, b.booking_time, b.user_name
            FROM bookings b
            ORDER BY b.booking_date ASC, b.booking_time ASC
        """)
        bookings = cur.fetchall()

        if not bookings:
            await call.message.edit_text(
                "📅 <b>Ваше расписание пока пусто.</b>",
                reply_markup=admin_menu_kb()
            )
            return

        text = "<b>📅 Список всех записей:</b>\n\n"
        for b_date, b_time, name in bookings:
            text += f"▫️ <code>{b_date}</code> в <code>{b_time}</code> — <b>{name}</b>\n"

        await call.message.edit_text(text, reply_markup=admin_menu_kb())
        
    except Exception as e:
        await call.answer(f"Ошибка при чтении базы: {e}", show_alert=True)
    
    await call.answer()