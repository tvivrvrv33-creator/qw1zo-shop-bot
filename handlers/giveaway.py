from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from emojis import e
from keyboards.main_menu import BTN_GIVEAWAY
from keyboards.inline import giveaway_participate_kb
from database import (
    get_giveaway, get_user, deduct_stars_balance,
    has_entered_giveaway, add_giveaway_entry, count_giveaway_entries,
)

router = Router()


async def _giveaway_text(user_id: int) -> tuple[str, bool]:
    g = await get_giveaway()
    participants = await count_giveaway_entries(g["round"])
    if not g["active"]:
        return (
            f"{e('gift','🎉')} <b>Розіграш</b>\n\n"
            f"Наразі активних розіграшів немає. Слідкуйте за оновленнями!",
            False,
        )
    already_joined = await has_entered_giveaway(g["round"], user_id)
    text = (
        f"{e('gift','🎉')} <b>Розіграш</b>\n\n"
        f"🏆 Приз: <b>{g['prize']} ⭐</b>\n"
        f"🎟 Вартість участі: <b>{g['entry_cost']} ⭐</b>\n"
        f"👥 Учасників: {participants}\n"
    )
    if already_joined:
        text += "\n✅ Ви вже берете участь у цьому розіграші. Успіху!"
    return (text, not already_joined)


@router.message(F.text == BTN_GIVEAWAY)
async def giveaway_menu(msg: Message, state: FSMContext):
    await state.clear()
    text, can_join = await _giveaway_text(msg.from_user.id)
    await msg.answer(
        text,
        reply_markup=giveaway_participate_kb() if can_join else None,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "giveaway_join")
async def giveaway_join(cb: CallbackQuery):
    g = await get_giveaway()
    if not g["active"]:
        await cb.answer("Розіграш вже завершено або не активний.", show_alert=True)
        return

    if await has_entered_giveaway(g["round"], cb.from_user.id):
        await cb.answer("Ви вже берете участь у цьому розіграші.", show_alert=True)
        return

    entry_cost = int(g["entry_cost"]) if g["entry_cost"].isdigit() else 0
    user = await get_user(cb.from_user.id)
    balance = user["stars_balance"] if user else 0
    if entry_cost > 0 and balance < entry_cost:
        await cb.answer(
            f"Недостатньо зірок для участі. Потрібно {entry_cost} ⭐ (у вас {balance} ⭐).",
            show_alert=True,
        )
        return

    if entry_cost > 0:
        ok = await deduct_stars_balance(cb.from_user.id, entry_cost)
        if not ok:
            await cb.answer("Недостатньо зірок для участі.", show_alert=True)
            return

    added = await add_giveaway_entry(g["round"], cb.from_user.id)
    if not added:
        if entry_cost > 0:
            from database import add_stars_balance
            await add_stars_balance(cb.from_user.id, entry_cost)
        await cb.answer("Ви вже берете участь у цьому розіграші.", show_alert=True)
        return

    await cb.answer(f"🎉 Ви берете участь у розіграші! Списано {entry_cost} ⭐.", show_alert=True)
    text, can_join = await _giveaway_text(cb.from_user.id)
    await cb.message.edit_text(
        text,
        reply_markup=giveaway_participate_kb() if can_join else None,
        parse_mode="HTML",
    )
