from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from emojis import e
from keyboards.main_menu import BTN_SUPP, BTN_INFO, BTN_PROMO
from database import get_setting

router = Router()


@router.message(F.text == BTN_SUPP)
async def support(msg: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написати в підтримку", url="https://t.me/qw1zo")]
    ])
    await msg.answer(
        f"{e('support','📞')} <b>Підтримка</b>\n\n"
        f"Натисніть кнопку нижче щоб написати нам:",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.message(F.text == BTN_INFO)
async def info(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        f"{e('info','ℹ️')} <b>Про qw1zo shop</b>\n\n"
        f"⭐ Купівля Telegram Stars від 15 ⭐\n"
        f"💸 Продаж Telegram Stars від 500 ⭐\n"
        f"👑 Telegram Premium — 1/3/6/12 місяців\n"
        f"📱 Віртуальні номери 8+ країн\n\n"
        f"Гарантія повернення коштів при проблемах\n"
        f"Підтримка: @qw1zo",
        parse_mode="HTML",
    )


@router.message(F.text == BTN_PROMO)
async def promo(msg: Message, state: FSMContext):
    await state.clear()
    promo_text = await get_setting("promo_text")
    await msg.answer(
        f"{e('gift','🎁')} <b>Акції та знижки</b>\n\n{promo_text}",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cancel")
async def cancel_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        f"{e('cancel','❌')} Скасовано.",
        parse_mode="HTML",
    )
    await cb.answer()
