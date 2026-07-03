from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from emojis import e
from keyboards.main_menu import BTN_PROF, BTN_BAL
from keyboards.inline import balance_kb, cancel_kb
from database import get_user, create_order, deduct_stars_balance, get_setting
from states import WithdrawTG

router = Router()


@router.message(F.text == BTN_PROF)
async def profile_menu(msg: Message, state: FSMContext):
    await state.clear()
    user = await get_user(msg.from_user.id)
    balance = user["stars_balance"] if user else 0
    username = msg.from_user.username or "—"
    text = (
        f"{e('user','👤')} <b>Профіль</b>\n\n"
        f"👤 Ім'я: {msg.from_user.first_name}\n"
        f"🔗 Username: @{username}\n"
        f"🆔 ID: <code>{msg.from_user.id}</code>\n"
        f"{e('balance','💰')} Баланс зірок: <b>{balance} ⭐</b>"
    )
    await msg.answer(text, reply_markup=balance_kb(), parse_mode="HTML")


@router.message(F.text == BTN_BAL)
async def balance_menu(msg: Message, state: FSMContext):
    await state.clear()
    user = await get_user(msg.from_user.id)
    balance = user["stars_balance"] if user else 0
    text = (
        f"{e('balance','💰')} <b>Баланс зірок</b>\n\n"
        f"На вашому рахунку: <b>{balance} ⭐</b>\n\n"
        f"{e('telegram','✈️')} Вивести зірки напряму в Telegram (мін. 13 ⭐):"
    )
    await msg.answer(text, reply_markup=balance_kb(), parse_mode="HTML")


@router.callback_query(F.data == "profile_balance")
async def profile_balance_cb(cb: CallbackQuery):
    user = await get_user(cb.from_user.id)
    balance = user["stars_balance"] if user else 0
    await cb.answer(f"Ваш баланс: {balance} ⭐", show_alert=True)


@router.callback_query(F.data == "withdraw_tg")
async def withdraw_tg_cb(cb: CallbackQuery, state: FSMContext):
    user = await get_user(cb.from_user.id)
    balance = user["stars_balance"] if user else 0
    if balance < 13:
        await cb.answer(
            f"Недостатньо зірок. Мінімум 13 ⭐ (у вас {balance} ⭐).",
            show_alert=True,
        )
        return
    await state.set_state(WithdrawTG.waiting_amount)
    await state.update_data(balance=balance)
    await cb.message.edit_text(
        f"{e('telegram','✈️')} <b>Вивести зірки в Telegram</b>\n\n"
        f"Доступно: <b>{balance} ⭐</b>\n"
        f"Мінімум виводу: 13 ⭐\n\n"
        f"Введіть кількість зірок для виводу:",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(StateFilter(WithdrawTG.waiting_amount))
async def withdraw_tg_amount(msg: Message, state: FSMContext):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        await msg.answer(f"{e('reject','❌')} Введіть число.", reply_markup=cancel_kb(), parse_mode="HTML")
        return

    data = await state.get_data()
    balance = data.get("balance", 0)
    if amount < 13:
        await msg.answer(f"{e('reject','❌')} Мінімум 13 ⭐.", reply_markup=cancel_kb(), parse_mode="HTML")
        return
    if amount > balance:
        await msg.answer(
            f"{e('reject','❌')} Недостатньо зірок. Доступно: {balance} ⭐.",
            reply_markup=cancel_kb(), parse_mode="HTML",
        )
        return

    ok = await deduct_stars_balance(msg.from_user.id, amount)
    if not ok:
        await msg.answer(f"{e('reject','❌')} Недостатньо зірок.", parse_mode="HTML")
        await state.clear()
        return

    order_id = await create_order(
        user_id=msg.from_user.id,
        type_="withdraw_tg",
        amount=str(amount),
        price="—",
        extra=f"@{msg.from_user.username or msg.from_user.id}",
    )
    await state.clear()

    from config import ADMIN_IDS
    from keyboards.inline import withdraw_confirm_kb
    user = msg.from_user
    admin_text = (
        f"{e('telegram','✈️')} <b>Запит на вивід в TG #{order_id}</b>\n\n"
        f"👤 <a href='tg://user?id={user.id}'>{user.first_name}</a> (@{user.username or '—'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"{e('stars','⭐')} Зірок: {amount} ⭐\n"
        f"📨 Надіслати зірки: @{user.username or user.id}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await msg.bot.send_message(admin_id, admin_text,
                                       reply_markup=withdraw_confirm_kb(order_id),
                                       parse_mode="HTML")
        except Exception:
            pass

    await msg.answer(
        f"{e('check','✅')} <b>Запит #{order_id} відправлено!</b>\n\n"
        f"{amount} ⭐ списано з балансу. Адмін надішле вам зірки найближчим часом.",
        parse_mode="HTML",
    )
