from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from emojis import e
from keyboards.main_menu import BTN_BUY
from keyboards.inline import buy_stars_packages, cancel_kb, confirm_receipt_kb
from states import BuyStars
from database import get_setting, create_order

router = Router()

PACKAGES = {
    "buy_15": (15, 20),
    "buy_21": (21, 30),
    "buy_26": (26, 40),
    "buy_50": (50, 45),
}


@router.message(F.text == BTN_BUY)
async def buy_stars_menu(msg: Message, state: FSMContext):
    await state.clear()
    rate = float(await get_setting("buy_rate") or "0.84")
    lines = "\n".join(
        f"• {stars} ⭐ = {price} грн" for stars, price in PACKAGES.values()
    )
    text = (
        f"{e('stars','⭐')} <b>Купити Stars</b>\n\n"
        f"{lines}\n"
        f"• Своя кількість (від 51 ⭐): {rate} грн/⭐\n\n"
        f"Оберіть пакет:"
    )
    await msg.answer(text, reply_markup=buy_stars_packages(), parse_mode="HTML")


@router.callback_query(F.data.in_(PACKAGES.keys()))
async def buy_package(cb: CallbackQuery, state: FSMContext):
    stars, price = PACKAGES[cb.data]
    card = await get_setting("payment_card")
    await state.update_data(stars=stars, price=price)
    await state.set_state(BuyStars.waiting_receipt)
    text = (
        f"{e('card','💳')} <b>Замовлення: {stars} ⭐ за {price} грн</b>\n\n"
        f"Переказ на картку:\n"
        f"<code>{card}</code>\n\n"
        f"Після оплати надішліть скріншот квитанції:"
    )
    await cb.message.edit_text(text, reply_markup=cancel_kb(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "buy_custom")
async def buy_custom_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(BuyStars.waiting_custom_amount)
    rate = float(await get_setting("buy_rate") or "0.84")
    await cb.message.edit_text(
        f"{e('stars','⭐')} Введіть кількість зірок (мінімум 51):\n"
        f"Ціна: {rate} грн за 1 ⭐",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(BuyStars.waiting_custom_amount)
async def buy_custom_amount(msg: Message, state: FSMContext):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        await msg.answer(
            f"{e('reject','❌')} Введіть число (наприклад: 100)",
            reply_markup=cancel_kb(), parse_mode="HTML",
        )
        return
    if amount < 51:
        await msg.answer(
            f"{e('reject','❌')} Мінімум 51 ⭐",
            reply_markup=cancel_kb(), parse_mode="HTML",
        )
        return
    rate = float(await get_setting("buy_rate") or "0.84")
    price = round(amount * rate, 2)
    card = await get_setting("payment_card")
    await state.update_data(stars=amount, price=price)
    await state.set_state(BuyStars.waiting_receipt)
    text = (
        f"{e('card','💳')} <b>Замовлення: {amount} ⭐ за {price} грн</b>\n\n"
        f"Переказ на картку:\n"
        f"<code>{card}</code>\n\n"
        f"Після оплати надішліть скріншот квитанції:"
    )
    await msg.answer(text, reply_markup=cancel_kb(), parse_mode="HTML")


@router.message(BuyStars.waiting_receipt, F.photo | F.document)
async def buy_receipt(msg: Message, state: FSMContext):
    data = await state.get_data()
    stars = data.get("stars", 0)
    price = data.get("price", 0)
    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id

    order_id = await create_order(
        user_id=msg.from_user.id,
        type_="buy_stars",
        amount=str(stars),
        price=str(price),
        receipt_file_id=file_id,
    )
    await state.clear()

    from config import ADMIN_IDS
    bot = msg.bot
    user = msg.from_user
    admin_text = (
        f"{e('orders','📋')} <b>Нова заявка #{order_id} — Купити Stars</b>\n\n"
        f"👤 <a href='tg://user?id={user.id}'>{user.first_name}</a> (@{user.username or '—'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"⭐ Кількість: {stars} ⭐\n"
        f"💰 Сума: {price} грн"
    )
    for admin_id in ADMIN_IDS:
        try:
            if msg.photo:
                await bot.send_photo(admin_id, file_id, caption=admin_text,
                                     reply_markup=confirm_receipt_kb(order_id), parse_mode="HTML")
            else:
                await bot.send_document(admin_id, file_id, caption=admin_text,
                                        reply_markup=confirm_receipt_kb(order_id), parse_mode="HTML")
        except Exception:
            pass

    await msg.answer(
        f"{e('check','✅')} <b>Заявку #{order_id} отримано!</b>\n\n"
        f"Очікуйте підтвердження. Після підтвердження {stars} ⭐ зараховано на ваш баланс.",
        parse_mode="HTML",
    )


@router.message(BuyStars.waiting_receipt)
async def buy_receipt_wrong(msg: Message):
    await msg.answer(
        f"{e('reject','❌')} Надішліть скріншот квитанції (фото або файл).",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
