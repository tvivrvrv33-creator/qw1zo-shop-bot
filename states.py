from aiogram.fsm.state import State, StatesGroup


class BuyStars(StatesGroup):
    waiting_custom_amount = State()
    waiting_receipt = State()


class SellStars(StatesGroup):
    waiting_amount = State()
    waiting_card = State()
    waiting_receipt = State()


class Premium(StatesGroup):
    waiting_username = State()
    waiting_receipt = State()


class WithdrawTG(StatesGroup):
    waiting_amount = State()


class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_new_card = State()
    waiting_ban_id = State()
    waiting_unban_id = State()
    waiting_sell_rate = State()
    waiting_buy_rate = State()
    waiting_premium_prices = State()
    waiting_promo_text = State()
    waiting_addstars_id = State()
    waiting_addstars_amount = State()
    waiting_removestars_id = State()
    waiting_removestars_amount = State()
    waiting_giveaway_settings = State()
    waiting_giveaway_winners_count = State()
    waiting_sell_destination = State()
    waiting_premium_sticker = State()
