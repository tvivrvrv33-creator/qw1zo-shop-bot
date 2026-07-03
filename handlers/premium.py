from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from emojis import e
from keyboards.main_menu import BTN_PREM
from keyboards.inline import premium_durations, cancel_kb, confirm_receipt_kb
from states import Premium
from database import get_setting, create_order

router = Router()

DURATION_LABELS = {
    "prem_1m": "1 місяць",
    "prem_3m": "3 місяці",
    "prem_6m": "6 місяців",
    "prem_12m": "12 місяців",
}
DURATION_KEYS = {
    "prem_1m": "premium_1m",
    "prem_3m": "premium_3m",
    "prem_6m": "premium_6m",
    "prem_12m": "premium_12m",
}


@router.message(F.text == BTN_PREM)
async def premium_menu(msg: Message, state: FSMContext):
    await state.clear()
    p1 = await get_setting("premium_1m")
    p3 = await get_setting("premium_3m")
    p6 = await get_setting("premium_6m")
    p12 = await get_setting("premium_12m")
    text = (
        f"{e('crown','👑')} <b>Telegram Premium</b>\n\n"
        f"• 1 місяць — {p1} грн\n"
        f"• 3 місяці — {p3} грн\n"
        f"• 6 місяців — {p6} грн\n"
        f"• 12 місяців — {p12} грн\n\n"
        f"Оберіть термін:"
    )
    await msg.answer(text, reply_markup=premium_durations(), parse_mode="HTML")


@router.callback_query(F.data.in_(DURATION_LABELS.keys()))
async def premium_duration(cb: CallbackQuery, state: FSMContext):
    label = DURATION_LABELS[cb.data]
    price = await get_setting(DURATION_KEYS[cb.data])
    await state.update_data(duration=label, price=price)
    await state.set_state(Premium.waiting_username)
    await cb.message.edit_text(
        f"{e('crown','👑')} <b>Premium {label} — {price} грн</b>\n\n"
        f"Введіть username акаунта для активації (без @):",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
    await cb.answer()


@router.message(Premium.waiting_username)
async def premium_username(msg: Message, state: FSMContext):
    username = msg.text.strip().lstrip("@")
    await state.update_data(username=username)
    await state.set_state(Premium.waiting_receipt)
    data = await state.get_data()
    price = data.get("price", "—")
    duration = data.get("duration", "—")
    card = await get_setting("payment_card")
    await msg.answer(
        f"{e('card','💳')} <b>Premium {duration} — {price} грн</b>\n\n"
        f"Акаунт: @{username}\n"
        f"Переказ на картку: <code>{card}</code>\n\n"
        f"Надішліть скріншот квитанції:",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )


@router.message(Premium.waiting_receipt, F.photo | F.document)
async def premium_receipt(msg: Message, state: FSMContext):
    data = await state.get_data()
    duration = data.get("duration", "—")
    price = data.get("price", "—")
    username = data.get("username", "—")
    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id

    order_id = await create_order(
        user_id=msg.from_user.id, type_="premium",
        amount=duration, price=str(price),
        extra=username, receipt_file_id=file_id,
    )
    await state.clear()

    from config import ADMIN_IDS
    user = msg.from_user
    admin_text = (
        f"{e('orders','📋')} <b>Нова заявка #{order_id} — Telegram Premium</b>\n\n"
        f"👤 <a href='tg://user?id={user.id}'>{user.first_name}</a> (@{user.username or '—'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"⏳ Термін: {duration} | 💰 Сума: {price} грн\n"
        f"👤 Акаунт: @{username}"
    )
    for admin_id in ADMIN_IDS:
        try:
            if msg.photo:
                await msg.bot.send_photo(admin_id, file_id, caption=admin_text,
                                         reply_markup=confirm_receipt_kb(order_id), parse_mode="HTML")
            else:
                await msg.bot.send_document(admin_id, file_id, caption=admin_text,
                                            reply_markup=confirm_receipt_kb(order_id), parse_mode="HTML")
        except Exception:
            pass

    await msg.answer(
        f"{e('check','✅')} <b>Заявку #{order_id} отримано!</b>\n\n"
        f"Після підтвердження Premium активовано на @{username}.",
        parse_mode="HTML",
    )


@router.message(Premium.waiting_receipt)
async def premium_receipt_wrong(msg: Message):
    await msg.answer(
        f"{e('reject','❌')} Надішліть скріншот квитанції.",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
