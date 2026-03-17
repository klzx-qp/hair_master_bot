from aiogram.fsm.state import StatesGroup, State


class AdminStates(StatesGroup):
    choosing_action = State()

    # Состояния для добавления дня и времени (теперь совпадают с admin.py)
    waiting_for_date = State()
    waiting_for_slots = State()

    # Остальные состояния (оставляем для совместимости)
    adding_day = State()
    adding_slot_date = State()
    adding_slot_time = State()

    closing_day = State()
    viewing_schedule_date = State()

    cancelling_booking_date = State()
    choosing_booking_to_cancel = State()