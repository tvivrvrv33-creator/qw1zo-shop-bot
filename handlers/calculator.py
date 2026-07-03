from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from emojis import e
from keyboards.main_menu import BTN_CALC
from database import get_setting

router = Router()


@router.message(F.text == BTN_CALC)
async def calculator(msg: Message, state: FSMContext):
    await state.clear()
    buy_rate = float(await get_setting("buy_rate") or "0.84")
    sell_rate = float(await get_setting("sell_rate") or "0.40")

    examples_buy = "\n".join(
        f"  {s} ⭐ = {round(s * buy_rate, 2)} грн"
        for s in [51, 100, 200, 500, 1000]
    )
    examples_sell = "\n".join(
        f"  {s} ⭐ = {round(s * sell_rate, 2)} грн"
        for s in [500, 1000, 2000, 5000]
    )

    text = (
        f"{e('calc','🧮')} <b>Калькулятор цін</b>\n\n"
        f"<b>Купити Stars</b> ({buy_rate} грн/⭐):\n{examples_buy}\n\n"
        f"<b>Продати Stars</b> ({sell_rate} грн/⭐):\n{examples_sell}\n\n"
        f"Пакети зі знижкою:\n"
        f"  15 ⭐ = 20 грн | 21 ⭐ = 30 грн\n"
        f"  26 ⭐ = 40 грн | 50 ⭐ = 40 грн"
    )
    await msg.answer(text, parse_mode="HTML")
