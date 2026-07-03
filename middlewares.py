from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from aiogram.fsm.context import FSMContext
from keyboards.main_menu import MAIN_MENU_BUTTONS


class ResetStateMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.text in MAIN_MENU_BUTTONS:
            state: FSMContext = data.get("state")
            if state:
                current = await state.get_state()
                if current is not None:
                    await state.clear()
        return await handler(event, data)


class BanCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from database import is_banned, ensure_user
        if isinstance(event, Message) and event.from_user:
            u = event.from_user
            await ensure_user(u.id, u.username or "", u.first_name or "")
            if await is_banned(u.id):
                await event.answer("🚫 Ваш акаунт заблоковано.")
                return
        return await handler(event, data)
