from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import CHANNEL_LINK


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="Записаться", callback_data="menu_book"),
        ],
        [
            InlineKeyboardButton(
                text="Моя запись / Отменить", callback_data="menu_my_booking"
            ),
        ],
        [
            InlineKeyboardButton(text="Прайсы", callback_data="menu_prices"),
        ],
        [
            InlineKeyboardButton(text="Портфолио", callback_data="menu_portfolio"),
        ],
    ]
    if is_admin:
        buttons.append(
            [InlineKeyboardButton(text="Админ-панель", callback_data="menu_admin")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subscription_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подписаться", url=CHANNEL_LINK
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Проверить подписку", callback_data="check_subscription"
                )
            ],
        ]
    )


def portfolio_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Смотреть портфолио",
                    url="https://ru.pinterest.com/crystalwithluv/_created/",
                )
            ]
        ]
    )