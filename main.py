import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands

from config import BOT_TOKEN
from database import init_db
from middlewares import ResetStateMiddleware, BanCheckMiddleware

from handlers import start, buy_stars, sell_stars, premium, calculator, profile, misc, admin, giveaway

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def start_keepalive_server():
    """Tiny HTTP server so free hosts (e.g. Render) see this as a web
    service, and a self-ping loop keeps it awake without any external
    pinging service."""
    from aiohttp import web

    async def health(request):
        return web.Response(text="qw1zo shop bot is alive")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Keepalive HTTP server started on port {port}")

    asyncio.create_task(self_ping_loop(port))


async def self_ping_loop(port: int, interval_seconds: int = 600):
    """Periodically pings this service's own public URL so Render's free
    tier does not spin it down from inactivity. Uses RENDER_EXTERNAL_URL,
    which Render sets automatically on every deployed service."""
    import aiohttp

    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    ping_url = f"{external_url.rstrip('/')}/health" if external_url else f"http://127.0.0.1:{port}/health"

    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(ping_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    logger.info(f"Self-ping {ping_url} -> {resp.status}")
        except Exception as exc:
            logger.warning(f"Self-ping failed: {exc}")


async def main():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        return

    await init_db()
    logger.info("Database initialized")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(BanCheckMiddleware())
    dp.message.middleware(ResetStateMiddleware())

    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(buy_stars.router)
    dp.include_router(sell_stars.router)
    dp.include_router(premium.router)
    dp.include_router(calculator.router)
    dp.include_router(profile.router)
    dp.include_router(giveaway.router)
    dp.include_router(misc.router)

    await bot.set_my_commands(
        [BotCommand(command="start", description="Повернутися в меню")],
        scope=BotCommandScopeDefault(),
    )
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    if os.environ.get("KEEPALIVE_SERVER", "0") == "1":
        await start_keepalive_server()

    logger.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
