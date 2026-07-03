from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from emojis import E


def _btn(
    text: str,
    callback_data: str,
    emoji_key: str | None = None,
    style: str | None = None,
) -> InlineKeyboardButton:
    kwargs: dict = {"text": text, "callback_data": callback_data}
    if emoji_key and E.get(emoji_key):
        kwargs["icon_custom_emoji_id"] = E[emoji_key]
    if style:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)


def buy_stars_packages() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("15 ⭐ — 20 грн", "buy_15", "stars", "success"),
         _btn("21 ⭐ — 30 грн", "buy_21", "stars", "success")],
        [_btn("26 ⭐ — 40 грн", "buy_26", "stars", "success"),
         _btn("50 ⭐ — 45 грн", "buy_50", "stars", "success")],
        [_btn("✏️ Своя кількість (від 51 ⭐)", "buy_custom", "cart", "success")],
        [_btn("❌ Скасувати", "cancel", "cancel")],
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("❌ Скасувати", "cancel", "cancel")]
    ])


def confirm_receipt_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ Підтвердити", f"confirm_{order_id}", "confirm", "success"),
         _btn("❌ Відхилити", f"reject_{order_id}", "reject", "danger")],
    ])


def balance_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✈️ Вивести зірки в Telegram", "withdraw_tg", "telegram", "success")],
    ])


def sell_stars_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("500 ⭐ → 200 грн", "sell_500", "sell", "success"),
         _btn("✏️ Своя кількість", "sell_custom", "cart", "success")],
        [_btn("❌ Скасувати", "cancel", "cancel")],
    ])


def premium_durations() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("1 місяць", "prem_1m", "crown", "success"),
         _btn("3 місяці", "prem_3m", "crown", "success")],
        [_btn("6 місяців", "prem_6m", "crown", "success"),
         _btn("12 місяців", "prem_12m", "crown", "success")],
        [_btn("❌ Скасувати", "cancel", "cancel")],
    ])


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📋 Нові заявки", "adm_orders", "orders", "primary"),
         _btn("📊 Статистика", "adm_stats", "stats", "primary")],
        [_btn("👥 Користувачі", "adm_users", "users", "primary"),
         _btn("📢 Розсилка", "adm_broadcast", "broadcast", "primary")],
        [_btn("💳 Змінити картку", "adm_card", "card", "primary"),
         _btn("💱 Змінити курс", "adm_rate", "rate", "primary")],
        [_btn("👑 Ціни Premium", "adm_prem_price", "premium_p", "primary")],
        [_btn("🎁 Акції", "adm_promo", "gift", "primary")],
        [_btn("📤 Куди переказ. зірки", "adm_sell_destination", "sell", "primary"),
         _btn("🎟 Стікер Premium", "adm_premium_sticker", "crown", "primary")],
        [_btn("➕ Нарахувати зірки", "adm_addstars", "stars", "success"),
         _btn("➖ Зняти зірки", "adm_removestars", "stars", "danger")],
        [_btn("🎉 Розіграш", "adm_giveaway", "gift", "primary")],
        [_btn("🚫 Бан", "adm_ban", "ban", "danger"),
         _btn("✅ Розбан", "adm_unban", "unban", "success")],
        [_btn("📜 Журнал дій", "adm_log", "log", "primary")],
    ])


def giveaway_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✏️ Задати суму / вартість участі", "adm_giveaway_set", "gift", "primary")],
        [_btn("🏆 Обрати переможців автоматично", "adm_giveaway_winners", "gift", "success")],
        [_btn("🛑 Зупинити розіграш", "adm_giveaway_stop", "cancel", "danger")],
        [_btn("⬅️ Назад", "adm_back", "back")],
    ])


def giveaway_participate_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🎉 Взяти участь", "giveaway_join", "gift", "success")],
    ])


def withdraw_confirm_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ Підтвердити виплату", f"wpay_{order_id}", "confirm", "success"),
         _btn("❌ Відхилити", f"wreject_{order_id}", "reject", "danger")],
    ])
