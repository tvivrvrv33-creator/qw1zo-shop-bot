from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from emojis import E

BTN_BUY    = "Купити Stars"
BTN_SELL   = "Продати Stars"
BTN_PREM   = "Telegram Premium"
BTN_CALC   = "Калькулятор"
BTN_PROF   = "Профіль"
BTN_BAL    = "Баланс"
BTN_SUPP   = "Підтримка"
BTN_INFO   = "Інформація"
BTN_PROMO  = "Акції"
BTN_GIVEAWAY = "🎉 Розіграш"

MAIN_MENU_BUTTONS = {
    BTN_BUY, BTN_SELL, BTN_PREM,
    BTN_CALC, BTN_PROF, BTN_BAL, BTN_SUPP,
    BTN_INFO, BTN_PROMO, BTN_GIVEAWAY,
}


def _kb(text: str, emoji_key: str, style: str = "success") -> KeyboardButton:
    return KeyboardButton(
        text=text,
        icon_custom_emoji_id=E.get(emoji_key, ""),
        style=style,
    )


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [_kb(BTN_BUY,  "stars",   "danger"),
             _kb(BTN_PREM, "crown",   "danger")],
            [_kb(BTN_SELL, "sell",    "success"),
             _kb(BTN_CALC, "calc",    "success"),
             _kb(BTN_BAL,  "balance", "success")],
            [_kb(BTN_PROF, "user",    "success"),
             _kb(BTN_INFO, "info",    "success"),
             _kb(BTN_PROMO, "gift",   "success")],
            [_kb(BTN_GIVEAWAY, "gift", "danger")],
            [_kb(BTN_SUPP, "support", "primary")],
        ],
        resize_keyboard=True,
    )
