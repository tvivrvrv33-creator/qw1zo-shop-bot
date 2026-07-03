from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from emojis import e
from keyboards.main_menu import BTN_SELL
from keyboards.inline import sell_stars_kb, cancel_kb, confirm_receipt_kb
from states import SellStars
from database import get_setting, create_order

router = Router()


@router.message(F.text == BTN_SELL)
async def sell_stars_menu(msg: Message, state: FSMContext):
    await state.clear()
    rate = await get_setting("sell_rate") or "0.40"
    text = (
        f"{e('sell','💸')} <b>Продати Stars</b>\n\n"
        f"Мінімум: 500 ⭐\n"
        f"Курс: {rate} грн за 1 ⭐ (500 ⭐ = {round(500 * float(rate))} грн)\n\n"
        f"Оберіть кількість:"
    )
    await msg.answer(text, reply_markup=sell_stars_kb(), parse_mode="HTML")


@router.callback_query(F.data == "sell_500")
async def sell_500_cb(cb: CallbackQuery, state: FSMContext):
    await state.update_data(stars=500)
    await state.set_state(SellStars.waiting_card)
    await cb.message.edit_text(
        f"{e('card','💳')} Введіть номер вашої картки для виплати:",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "sell_custom")
async def sell_custom_cb(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SellStars.waiting_amount)
    await cb.message.edit_text(
        f"{e('sell','💸')} Введіть кількість зірок (мінімум 500):",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
    await cb.answer()


@router.message(SellStars.waiting_amount)
async def sell_custom_amount(msg: Message, state: FSMContext):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        await msg.answer(f"{e('reject','❌')} Введіть число.", reply_markup=cancel_kb(), parse_mode="HTML")
        return
    if amount < 500:
        await msg.answer(f"{e('reject','❌')} Мінімум 500 ⭐.", reply_markup=cancel_kb(), parse_mode="HTML")
        return
    await state.update_data(stars=amount)
    await state.set_state(SellStars.waiting_card)
    await msg.answer(
        f"{e('card','💳')} Введіть номер вашої картки для виплати:",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )


@router.message(SellStars.waiting_card)
async def sell_card(msg: Message, state: FSMContext):
    card = msg.text.strip()
    await state.update_data(card=card)
    await state.set_state(SellStars.waiting_receipt)
    data = await state.get_data()
    stars = data.get("stars", 500)
    rate = float(await get_setting("sell_rate") or "0.40")
    payout = round(stars * rate, 2)
    destination = await get_setting("sell_stars_destination") or "@qw1zo"
    await msg.answer(
        f"{e('sell','💸')} <b>Продаж {stars} ⭐ — {payout} грн</b>\n\n"
        f"Виплата на картку: <code>{card}</code>\n\n"
        f"1️⃣ Перекажіть {stars} ⭐ подарунком на акаунт {destination}\n"
        f"2️⃣ Надішліть сюди скріншот переказу зірок як підтвердження:",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )


@router.message(SellStars.waiting_receipt, F.photo | F.document)
async def sell_receipt(msg: Message, state: FSMContext):
    data = await state.get_data()
    stars = data.get("stars", 500)
    card = data.get("card", "—")
    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    rate = float(await get_setting("sell_rate") or "0.40")
    payout = round(stars * rate, 2)

    order_id = await create_order(
        user_id=msg.from_user.id, type_="sell_stars",
        amount=str(stars), price=str(payout),
        extra=card, receipt_file_id=file_id,
    )
    await state.clear()

    from config import ADMIN_IDS
    user = msg.from_user
    admin_text = (
        f"{e('orders','📋')} <b>Нова заявка #{order_id} — Продати Stars</b>\n\n"
        f"👤 <a href='tg://user?id={user.id}'>{user.first_name}</a> (@{user.username or '—'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"⭐ Зірок: {stars} | 💰 Виплата: {payout} грн\n"
        f"💳 Картка: <code>{card}</code>"
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
        f"Після підтвердження {payout} грн виплачено на картку.",
        parse_mode="HTML",
    )


@router.message(SellStars.waiting_receipt)
async def sell_receipt_wrong(msg: Message):
    await msg.answer(
        f"{e('reject','❌')} Надішліть скріншот квитанції (фото або файл).",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
