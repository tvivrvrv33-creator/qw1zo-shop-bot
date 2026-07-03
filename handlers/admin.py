import random
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from emojis import e
from keyboards.inline import admin_panel_kb, confirm_receipt_kb, giveaway_admin_kb
from states import AdminStates
from database import (
    get_pending_orders, get_order, update_order_status,
    get_all_users, set_ban, get_stats, get_setting, set_setting,
    add_log, get_logs, add_stars_balance, deduct_stars_balance, get_user,
    get_giveaway, start_giveaway, stop_giveaway, count_giveaway_entries,
    get_buy_stars_by_user, get_giveaway_entrants,
)
from config import ADMIN_IDS

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── shared logic ────────────────────────────────────────────────────────────

async def _do_confirm(cb: CallbackQuery, order_id: int):
    order = await get_order(order_id)
    if not order:
        await cb.answer("Заявку не знайдено.", show_alert=True)
        return
    if order["status"] != "pending":
        await cb.answer(f"Заявка вже оброблена: {order['status']}", show_alert=True)
        return

    await update_order_status(order_id, "confirmed")

    if order["type"] == "buy_stars":
        try:
            await add_stars_balance(order["user_id"], int(order["amount"]))
        except (ValueError, TypeError):
            pass

    await add_log(cb.from_user.id, "confirm", f"order #{order_id}")

    confirmed_label = f"\n\n{e('confirm','✅')} <b>ПІДТВЕРДЖЕНО</b> @{cb.from_user.username or cb.from_user.id}"
    try:
        await cb.message.edit_caption(
            (cb.message.caption or "") + confirmed_label,
            parse_mode="HTML",
        )
    except Exception:
        try:
            await cb.message.edit_text(
                (cb.message.text or "") + confirmed_label,
                parse_mode="HTML",
            )
        except Exception:
            pass

    await cb.answer("✅ Підтверджено!")

    type_map = {
        "buy_stars": (
            f"🎉✨ <b>Замовлення #{order_id} виконано!</b>\n\n"
            f"{e('stars','⭐')} {order['amount']} Stars щойно зараховано на ваш баланс.\n\n"
            f"Дякуємо, що обираєте <b>qw1zo shop</b>! Ми цінуємо кожного клієнта та завжди раді допомогти.\n"
            f"Питання чи нове замовлення — просто пишіть, ми на зв'язку 24/7. До нових покупок! 🚀"
        ),
        "sell_stars": (
            f"🎉✨ <b>Замовлення #{order_id} виконано!</b>\n\n"
            f"💰 Виплату {order['price']} грн успішно відправлено на вашу картку.\n\n"
            f"Дякуємо за співпрацю з <b>qw1zo shop</b>! Будемо раді бачити вас знову — продавайте зірки"
            f" вигідно та швидко саме у нас. 💫"
        ),
        "premium": (
            f"👑🎉 <b>Замовлення #{order_id} виконано!</b>\n\n"
            f"Telegram Premium успішно активовано на акаунті @{order['extra']}.\n\n"
            f"Насолоджуйтесь ексклюзивними можливостями: без реклами, унікальні стікери та реакції,"
            f" збільшені ліміти та багато іншого! ✨\n\n"
            f"Дякуємо за довіру <b>qw1zo shop</b> 💜 Якщо виникнуть питання — завжди на зв'язку!"
        ),
        "withdraw_tg": (
            f"🎉✨ <b>Вивід #{order_id} виконано!</b>\n\n"
            f"{e('stars','⭐')} {order['amount']} Stars успішно надіслано вам.\n\n"
            f"Дякуємо, що користуєтесь <b>qw1zo shop</b>! 💫"
        ),
        "withdraw_card": (
            f"🎉✨ <b>Вивід #{order_id} виконано!</b>\n\n"
            f"💰 {order['price']} грн успішно відправлено на вашу картку.\n\n"
            f"Дякуємо, що користуєтесь <b>qw1zo shop</b>! 💫"
        ),
    }
    user_msg = type_map.get(order["type"], f"✅ Заявку #{order_id} підтверджено!")
    try:
        await cb.bot.send_message(order["user_id"], user_msg, parse_mode="HTML")
    except Exception:
        pass

    if order["type"] == "premium":
        sticker_id = await get_setting("premium_sticker_id")
        if sticker_id:
            try:
                await cb.bot.send_sticker(order["user_id"], sticker_id)
            except Exception:
                pass


async def _do_reject(cb: CallbackQuery, order_id: int):
    order = await get_order(order_id)
    if not order:
        await cb.answer("Заявку не знайдено.", show_alert=True)
        return
    if order["status"] != "pending":
        await cb.answer(f"Заявка вже оброблена: {order['status']}", show_alert=True)
        return

    await update_order_status(order_id, "rejected")

    if order["type"] in ("withdraw_card", "withdraw_tg"):
        try:
            await add_stars_balance(order["user_id"], int(order["amount"]))
        except (ValueError, TypeError):
            pass

    await add_log(cb.from_user.id, "reject", f"order #{order_id}")

    rejected_label = f"\n\n{e('reject','❌')} <b>ВІДХИЛЕНО</b>"
    try:
        await cb.message.edit_caption(
            (cb.message.caption or "") + rejected_label,
            parse_mode="HTML",
        )
    except Exception:
        try:
            await cb.message.edit_text(
                (cb.message.text or "") + rejected_label,
                parse_mode="HTML",
            )
        except Exception:
            pass

    await cb.answer("❌ Відхилено!")
    try:
        await cb.bot.send_message(
            order["user_id"],
            f"❌ Заявку #{order_id} відхилено. Зверніться до підтримки якщо вважаєте це помилкою.",
        )
    except Exception:
        pass


# ─── admin panel ─────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.clear()
    await msg.answer(
        f"{e('shield','🛡️')} <b>Адмін-панель</b>\n\nОберіть дію:",
        reply_markup=admin_panel_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_orders")
async def adm_orders(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    orders = await get_pending_orders()
    if not orders:
        await cb.answer("Немає нових заявок.", show_alert=True)
        return
    await cb.answer()
    type_map = {
        "buy_stars":    "⭐ Купити Stars",
        "sell_stars":   "💸 Продати Stars",
        "premium":      "👑 Premium",
        "withdraw_tg":  "✈️ Вивід в TG",
        "withdraw_card":"💳 Вивід на картку",
    }
    for o in orders[:10]:
        type_label = type_map.get(o["type"], o["type"])
        text = (
            f"{e('orders','📋')} <b>Заявка #{o['id']}</b>\n"
            f"Тип: {type_label}\n"
            f"🆔 Користувач: <code>{o['user_id']}</code>\n"
            f"Кількість: {o['amount']}\n"
            f"Сума: {o['price']} грн\n"
            f"Дод. інфо: {o['extra'] or '—'}\n"
            f"Дата: {o['created_at']}"
        )
        try:
            if o["receipt_file_id"]:
                await cb.message.answer_photo(
                    o["receipt_file_id"], caption=text,
                    reply_markup=confirm_receipt_kb(o["id"]),
                    parse_mode="HTML",
                )
            else:
                await cb.message.answer(
                    text, reply_markup=confirm_receipt_kb(o["id"]),
                    parse_mode="HTML",
                )
        except Exception:
            await cb.message.answer(
                text, reply_markup=confirm_receipt_kb(o["id"]),
                parse_mode="HTML",
            )


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_order(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    order_id = int(cb.data.split("_")[1])
    await _do_confirm(cb, order_id)


@router.callback_query(F.data.startswith("reject_"))
async def reject_order(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    order_id = int(cb.data.split("_")[1])
    await _do_reject(cb, order_id)


@router.callback_query(F.data.startswith("wpay_"))
async def wpay_order(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    order_id = int(cb.data.split("_")[1])
    await _do_confirm(cb, order_id)


@router.callback_query(F.data.startswith("wreject_"))
async def wreject_order(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    order_id = int(cb.data.split("_")[1])
    await _do_reject(cb, order_id)


# ─── stats ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_stats")
async def adm_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    stats = await get_stats()
    buyers = await get_buy_stars_by_user()

    if buyers:
        buyer_lines = []
        for i, b in enumerate(buyers, start=1):
            uname = f"@{b['username']}" if b["username"] else "—"
            spent = b["total_spent"] or 0
            buyer_lines.append(
                f"{i}. {uname} (<code>{b['user_id']}</code>) — "
                f"{e('stars','⭐')} {b['total_stars']} за {round(spent, 2)} грн "
                f"({b['orders_count']} замовл.)"
            )
        buyers_block = "\n".join(buyer_lines)
    else:
        buyers_block = "Поки що ніхто не купував."

    text = (
        f"{e('stats','📊')} <b>Статистика</b>\n\n"
        f"👥 Всього користувачів: {stats['total_users']}\n"
        f"⏳ Заявок в очікуванні: {stats['pending']}\n"
        f"{e('confirm','✅')} Підтверджених: {stats['confirmed']}\n"
        f"{e('reject','❌')} Відхилених: {stats['rejected']}\n\n"
        f"{e('stars','⭐')} <b>Топ покупців Stars:</b>\n{buyers_block}"
    )
    await cb.message.edit_text(text, reply_markup=admin_panel_kb(), parse_mode="HTML")
    await cb.answer()


# ─── users ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_users")
async def adm_users(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    users = await get_all_users()
    lines = []
    for u in users[:20]:
        status = "🚫" if u["is_banned"] else "✅"
        lines.append(f"{status} <code>{u['user_id']}</code> @{u['username'] or '—'} | ⭐{u['stars_balance']}")
    text = f"{e('users','👥')} <b>Користувачі ({len(users)} всього)</b>\n\n" + "\n".join(lines)
    if len(users) > 20:
        text += f"\n\n...та ще {len(users) - 20}"
    await cb.message.edit_text(text, reply_markup=admin_panel_kb(), parse_mode="HTML")
    await cb.answer()


# ─── broadcast ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    await state.set_state(AdminStates.waiting_broadcast)
    await cb.message.edit_text(
        f"{e('broadcast','📢')} <b>Розсилка</b>\n\nВведіть текст повідомлення:",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_broadcast)
async def adm_broadcast_send(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    users = await get_all_users()
    sent = 0
    for u in users:
        if u["is_banned"]:
            continue
        try:
            await msg.bot.send_message(u["user_id"], msg.text, parse_mode="HTML")
            sent += 1
        except Exception:
            pass
    await state.clear()
    await add_log(msg.from_user.id, "broadcast", f"sent to {sent} users")
    await msg.answer(
        f"{e('check','✅')} Розсилку відправлено {sent} користувачам.",
        parse_mode="HTML",
    )


# ─── settings ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_card")
async def adm_card_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    current = await get_setting("payment_card")
    await state.set_state(AdminStates.waiting_new_card)
    await cb.message.edit_text(
        f"{e('card','💳')} Поточна картка: <code>{current}</code>\n\nВведіть новий номер картки:",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_new_card)
async def adm_card_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await set_setting("payment_card", msg.text.strip())
    await state.clear()
    await add_log(msg.from_user.id, "change_card", msg.text.strip())
    await msg.answer(
        f"{e('check','✅')} Картку змінено: <code>{msg.text.strip()}</code>",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_rate")
async def adm_rate_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    buy = await get_setting("buy_rate")
    sell = await get_setting("sell_rate")
    await state.set_state(AdminStates.waiting_sell_rate)
    await cb.message.edit_text(
        f"{e('rate','💱')} Поточні курси:\n"
        f"• Купівля: {buy} грн/⭐\n"
        f"• Продаж: {sell} грн/⭐\n\n"
        f"Введіть новий курс КУПІВЛІ (грн/⭐):",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_sell_rate)
async def adm_buy_rate_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        rate = float(msg.text.strip().replace(",", "."))
    except ValueError:
        await msg.answer("❌ Введіть число (наприклад: 0.84)")
        return
    await set_setting("buy_rate", str(rate))
    await state.set_state(AdminStates.waiting_buy_rate)
    await msg.answer(
        f"{e('check','✅')} Курс купівлі: {rate} грн/⭐\n\nТепер введіть курс ПРОДАЖУ (грн/⭐):",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_buy_rate)
async def adm_sell_rate_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        rate = float(msg.text.strip().replace(",", "."))
    except ValueError:
        await msg.answer("❌ Введіть число (наприклад: 0.40)")
        return
    await set_setting("sell_rate", str(rate))
    await state.clear()
    await add_log(msg.from_user.id, "change_rate", f"sell={rate}")
    await msg.answer(
        f"{e('check','✅')} Курси оновлено!",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_prem_price")
async def adm_prem_price(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    p1 = await get_setting("premium_1m")
    p3 = await get_setting("premium_3m")
    p6 = await get_setting("premium_6m")
    p12 = await get_setting("premium_12m")
    await state.set_state(AdminStates.waiting_premium_prices)
    await cb.message.edit_text(
        f"{e('crown','👑')} Поточні ціни Premium:\n"
        f"1м={p1}, 3м={p3}, 6м={p6}, 12м={p12} грн\n\n"
        f"Введіть нові ціни через кому (1м,3м,6м,12м):\n"
        f"Приклад: <code>120,320,600,1100</code>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_premium_prices)
async def adm_prem_price_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        parts = [p.strip() for p in msg.text.split(",")]
        assert len(parts) == 4
        p1, p3, p6, p12 = [float(p) for p in parts]
    except Exception:
        await msg.answer("❌ Введіть 4 ціни через кому: 120,320,600,1100")
        return
    await set_setting("premium_1m", str(p1))
    await set_setting("premium_3m", str(p3))
    await set_setting("premium_6m", str(p6))
    await set_setting("premium_12m", str(p12))
    await state.clear()
    await add_log(msg.from_user.id, "change_premium_prices", msg.text)
    await msg.answer(
        f"{e('check','✅')} Ціни Premium оновлено!",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )


# ─── ban/unban ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_ban")
async def adm_ban_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    await state.set_state(AdminStates.waiting_ban_id)
    await cb.message.edit_text(
        f"{e('ban','🚫')} Введіть Telegram ID для бану:",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_ban_id)
async def adm_ban_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введіть числовий ID")
        return
    await set_ban(uid, True)
    await state.clear()
    await add_log(msg.from_user.id, "ban", str(uid))
    await msg.answer(
        f"{e('ban','🚫')} Користувача <code>{uid}</code> заблоковано.",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )
    try:
        await msg.bot.send_message(uid, "🚫 Ваш акаунт заблоковано.")
    except Exception:
        pass


@router.callback_query(F.data == "adm_unban")
async def adm_unban_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    await state.set_state(AdminStates.waiting_unban_id)
    await cb.message.edit_text(
        f"{e('unban','✅')} Введіть Telegram ID для розбану:",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_unban_id)
async def adm_unban_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введіть числовий ID")
        return
    await set_ban(uid, False)
    await state.clear()
    await add_log(msg.from_user.id, "unban", str(uid))
    await msg.answer(
        f"{e('unban','✅')} Користувача <code>{uid}</code> розблоковано.",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )
    try:
        await msg.bot.send_message(uid, "✅ Ваш акаунт розблоковано. Вітаємо назад!")
    except Exception:
        pass


# ─── back ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_back")
async def adm_back(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    await state.clear()
    await cb.message.edit_text(
        f"{e('shield','🛡️')} <b>Адмін-панель</b>\n\nОберіть дію:",
        reply_markup=admin_panel_kb(),
        parse_mode="HTML",
    )
    await cb.answer()


# ─── promo / акції ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_promo")
async def adm_promo_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    current = await get_setting("promo_text")
    await state.set_state(AdminStates.waiting_promo_text)
    await cb.message.edit_text(
        f"{e('gift','🎁')} <b>Поточний текст акцій:</b>\n\n{current}\n\n"
        f"Введіть новий текст акцій (підтримується HTML-розмітка):",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_promo_text)
async def adm_promo_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await set_setting("promo_text", msg.html_text or msg.text)
    await state.clear()
    await add_log(msg.from_user.id, "change_promo", "updated promo text")
    await msg.answer(
        f"{e('check','✅')} Текст акцій оновлено!",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )


# ─── sell stars destination ────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_sell_destination")
async def adm_sell_destination_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    current = await get_setting("sell_stars_destination") or "@qw1zo"
    await state.set_state(AdminStates.waiting_sell_destination)
    await cb.message.edit_text(
        f"{e('sell','💸')} <b>Поточний акаунт для переказу зірок:</b> {current}\n\n"
        f"Введіть новий username (наприклад @qw1zo), куди клієнти мають переказувати зірки"
        f" при продажу:",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_sell_destination)
async def adm_sell_destination_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    dest = msg.text.strip()
    if not dest.startswith("@"):
        dest = f"@{dest}"
    await set_setting("sell_stars_destination", dest)
    await state.clear()
    await add_log(msg.from_user.id, "change_sell_destination", dest)
    await msg.answer(
        f"{e('check','✅')} Акаунт для переказу зірок оновлено: {dest}",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )


# ─── premium confirmation sticker ──────────────────────────────────────────────

@router.callback_query(F.data == "adm_premium_sticker")
async def adm_premium_sticker_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    current = await get_setting("premium_sticker_id")
    status = "встановлено ✅" if current else "не встановлено"
    await state.set_state(AdminStates.waiting_premium_sticker)
    await cb.message.edit_text(
        f"{e('crown','👑')} <b>Стікер при підтвердженні Premium:</b> {status}\n\n"
        f"Надішліть сюди стікер, який бот буде надсилати клієнту разом із повідомленням"
        f" про активацію Premium. Або надішліть /clear, щоб прибрати стікер.",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_premium_sticker, F.sticker)
async def adm_premium_sticker_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await set_setting("premium_sticker_id", msg.sticker.file_id)
    await state.clear()
    await add_log(msg.from_user.id, "change_premium_sticker", "updated premium sticker")
    await msg.answer(
        f"{e('check','✅')} Стікер для Premium збережено!",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )


@router.message(AdminStates.waiting_premium_sticker, F.text == "/clear")
async def adm_premium_sticker_clear(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await set_setting("premium_sticker_id", "")
    await state.clear()
    await add_log(msg.from_user.id, "change_premium_sticker", "cleared premium sticker")
    await msg.answer(
        f"{e('check','✅')} Стікер для Premium прибрано!",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )


@router.message(AdminStates.waiting_premium_sticker)
async def adm_premium_sticker_wrong(msg: Message):
    await msg.answer(f"{e('reject','❌')} Надішліть стікер або /clear.")


# ─── stars balance management ──────────────────────────────────────────────────

@router.callback_query(F.data == "adm_addstars")
async def adm_addstars_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    await state.set_state(AdminStates.waiting_addstars_id)
    await cb.message.edit_text(
        f"{e('stars','⭐')} <b>Нарахувати зірки</b>\n\nВведіть Telegram ID користувача:",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_addstars_id)
async def adm_addstars_id(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введіть числовий ID")
        return
    await state.update_data(target_id=uid)
    await state.set_state(AdminStates.waiting_addstars_amount)
    await msg.answer("Введіть кількість зірок для нарахування:")


@router.message(AdminStates.waiting_addstars_amount)
async def adm_addstars_amount(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        amount = int(msg.text.strip())
        assert amount > 0
    except (ValueError, AssertionError):
        await msg.answer("❌ Введіть додатне число")
        return
    data = await state.get_data()
    uid = data.get("target_id")
    await add_stars_balance(uid, amount)
    await state.clear()
    await add_log(msg.from_user.id, "add_stars", f"user={uid} amount={amount}")
    await msg.answer(
        f"{e('check','✅')} Нараховано {amount} ⭐ користувачу <code>{uid}</code>.",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )
    try:
        await msg.bot.send_message(uid, f"{e('stars','⭐')} Вам нараховано {amount} ⭐ на баланс.", parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data == "adm_removestars")
async def adm_removestars_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    await state.set_state(AdminStates.waiting_removestars_id)
    await cb.message.edit_text(
        f"{e('stars','⭐')} <b>Зняти зірки</b>\n\nВведіть Telegram ID користувача:",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_removestars_id)
async def adm_removestars_id(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введіть числовий ID")
        return
    user = await get_user(uid)
    balance = user["stars_balance"] if user else 0
    await state.update_data(target_id=uid)
    await state.set_state(AdminStates.waiting_removestars_amount)
    await msg.answer(f"Поточний баланс: {balance} ⭐\n\nВведіть кількість зірок для зняття:")


@router.message(AdminStates.waiting_removestars_amount)
async def adm_removestars_amount(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        amount = int(msg.text.strip())
        assert amount > 0
    except (ValueError, AssertionError):
        await msg.answer("❌ Введіть додатне число")
        return
    data = await state.get_data()
    uid = data.get("target_id")
    ok = await deduct_stars_balance(uid, amount)
    await state.clear()
    if not ok:
        await msg.answer(
            f"{e('reject','❌')} У користувача недостатньо зірок для зняття.",
            reply_markup=admin_panel_kb(), parse_mode="HTML",
        )
        return
    await add_log(msg.from_user.id, "remove_stars", f"user={uid} amount={amount}")
    await msg.answer(
        f"{e('check','✅')} Знято {amount} ⭐ у користувача <code>{uid}</code>.",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )
    try:
        await msg.bot.send_message(uid, f"{e('stars','⭐')} З вашого балансу знято {amount} ⭐.", parse_mode="HTML")
    except Exception:
        pass


# ─── giveaway / розіграш ────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_giveaway")
async def adm_giveaway_menu(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    await state.clear()
    g = await get_giveaway()
    participants = await count_giveaway_entries(g["round"])
    status = "🟢 Активний" if g["active"] else "🔴 Не активний"
    await cb.message.edit_text(
        f"{e('gift','🎉')} <b>Розіграш</b>\n\n"
        f"Статус: {status}\n"
        f"Сума розіграшу: {g['prize']} ⭐\n"
        f"Вартість участі: {g['entry_cost']} ⭐\n"
        f"Учасників: {participants}",
        reply_markup=giveaway_admin_kb(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "adm_giveaway_set")
async def adm_giveaway_set_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    await state.set_state(AdminStates.waiting_giveaway_settings)
    await cb.message.edit_text(
        f"{e('gift','🎉')} Введіть суму розіграшу та вартість участі через кому:\n\n"
        f"Приклад: <code>500,10</code> — розіграш на 500 ⭐, участь коштує 10 ⭐\n\n"
        f"Це запустить новий розіграш (список учасників скинеться).",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_giveaway_settings)
async def adm_giveaway_set_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    try:
        parts = [p.strip() for p in msg.text.split(",")]
        assert len(parts) == 2
        prize = int(parts[0])
        entry_cost = int(parts[1])
        assert prize > 0 and entry_cost >= 0
    except Exception:
        await msg.answer("❌ Введіть два додатних числа через кому: сума,вартість_участі")
        return
    await start_giveaway(str(prize), str(entry_cost))
    await state.clear()
    await add_log(msg.from_user.id, "start_giveaway", f"prize={prize} entry_cost={entry_cost}")
    await msg.answer(
        f"{e('check','✅')} Розіграш запущено!\n\n"
        f"Сума: {prize} ⭐\nВартість участі: {entry_cost} ⭐",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_giveaway_stop")
async def adm_giveaway_stop_cb(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    await stop_giveaway()
    await add_log(cb.from_user.id, "stop_giveaway", "")
    await cb.message.edit_text(
        f"{e('check','✅')} Розіграш зупинено.",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data == "adm_giveaway_winners")
async def adm_giveaway_winners_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    g = await get_giveaway()
    participants = await count_giveaway_entries(g["round"])
    if participants == 0:
        await cb.answer("У розіграші ще немає учасників.", show_alert=True)
        return
    await state.update_data(giveaway_round=g["round"], giveaway_participants=participants)
    await state.set_state(AdminStates.waiting_giveaway_winners_count)
    await cb.message.edit_text(
        f"{e('gift','🏆')} Учасників у розіграші: <b>{participants}</b>\n\n"
        f"Скільки переможців обрати?",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_giveaway_winners_count)
async def adm_giveaway_winners_save(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    data = await state.get_data()
    round_ = data.get("giveaway_round")
    try:
        count = int(msg.text.strip())
        assert count > 0
    except Exception:
        await msg.answer("❌ Введіть додатне ціле число.")
        return

    entrants = await get_giveaway_entrants(round_)
    if not entrants:
        await state.clear()
        await msg.answer("У розіграші немає учасників.", reply_markup=admin_panel_kb())
        return

    count = min(count, len(entrants))
    winners = random.sample(entrants, count)
    await state.clear()
    await stop_giveaway()
    await add_log(msg.from_user.id, "giveaway_winners", f"round={round_} winners={winners}")

    lines = []
    for uid in winners:
        u = await get_user(uid)
        label = f"@{u['username']}" if u and u.get("username") else f"ID {uid}"
        lines.append(f"🏆 {label} (<code>{uid}</code>)")
    winners_text = "\n".join(lines)

    await msg.answer(
        f"{e('check','✅')} <b>Переможців обрано!</b>\n\n{winners_text}\n\n"
        f"Розіграш автоматично зупинено.",
        reply_markup=admin_panel_kb(), parse_mode="HTML",
    )

    for uid in winners:
        try:
            await msg.bot.send_message(
                uid,
                f"{e('gift','🎉')} <b>Вітаємо! Ви перемогли у розіграші!</b>\n\n"
                f"Найближчим часом з вами зв'яжеться адміністратор для отримання призу.",
                parse_mode="HTML",
            )
        except Exception:
            pass


# ─── log ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_log")
async def adm_log(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("❌ Немає доступу", show_alert=True)
    logs = await get_logs(20)
    if not logs:
        await cb.answer("Журнал порожній.", show_alert=True)
        return
    lines = [
        f"[{l['created_at'][:16]}] <code>{l['admin_id']}</code>: {l['action']} {l['details']}"
        for l in logs
    ]
    text = f"{e('log','📜')} <b>Журнал дій (останні 20)</b>\n\n" + "\n".join(lines)
    await cb.message.edit_text(text, reply_markup=admin_panel_kb(), parse_mode="HTML")
    await cb.answer()
