from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from emojis import e
from keyboards.main_menu import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(msg: Message):
    name = msg.from_user.first_name or "друже"
    text = (
        f"{e('stars','⭐')} <b>qw1zo shop</b> — ваш надійний магазин:\n\n"
        f"⭐ Купівля та продаж Telegram Stars\n"
        f"👑 Telegram Premium підписка\n"
        f"📱 Віртуальні номери телефонів\n\n"
        f"Вітаємо, <b>{name}</b>!\n"
        f"Оберіть потрібний пункт у меню нижче:"
    )
    await msg.answer(text, reply_markup=main_menu(), parse_mode="HTML")
