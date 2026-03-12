from aiogram import Router
from aiogram.types import Message

router = Router()


@router.message()
async def fallback(message: Message):
    await message.answer(
        "Пожалуйста, используйте кнопки меню или команду /start."
    )