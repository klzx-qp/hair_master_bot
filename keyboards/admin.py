from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Добавить рабочий день", callback_data="admin_add_day"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Добавить слот", callback_data="admin_add_slot"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Удалить слот", callback_data="admin_delete_slot"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Закрыть день", callback_data="admin_close_day"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Просмотр расписания", callback_data="admin_view_schedule"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отменить запись клиента",
                    callback_data="admin_cancel_booking",
                )
            ],
        ]
    )


def slots_list_kb(slots) -> InlineKeyboardMarkup:
    buttons = []
    for s in slots:
        text = f"{s['time']}"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"admin_slot:{s['id']}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="Отмена", callback_data="admin_cancel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def bookings_list_kb(bookings) -> InlineKeyboardMarkup:
    buttons = []
    for b in bookings:
        text = f"{b['time']} - {b['user_name'] or b['name']}"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=text, callback_data=f"admin_booking:{b['id']}"
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton(text="Отмена", callback_data="admin_cancel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)