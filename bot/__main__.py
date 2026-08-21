# bot/__main__.py
import asyncio
import logging
import os
import ssl

import aiohttp
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_bot_settings
from bot.handlers import register_routers
from bot.services.backend_client import BackendClient
from bot.services.http import build_http_client
from bot.web import build_api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("bot")


# ---- Кастомная сессия с прокси ----
class CustomAiohttpSession(AiohttpSession):
    def __init__(self, proxy: str, ssl_context: ssl.SSLContext):
        super().__init__()
        self._proxy = proxy
        self._ssl_context = ssl_context
        # Принудительно сбрасываем, чтобы _create_session создала новую
        self._session = None

    async def _create_session(self) -> aiohttp.ClientSession:
        log.info("✅ Создаём aiohttp-сессию с прокси: %s", self._proxy.split("@")[-1])
        connector = aiohttp.TCPConnector(ssl=self._ssl_context)
        return aiohttp.ClientSession(connector=connector, proxy=self._proxy)


async def main() -> None:
    settings = get_bot_settings()

    # Получаем прокси из переменной окружения (TELEGRAM_PROXY_URL)
    proxy_url = os.getenv("TELEGRAM_PROXY_URL")

    if proxy_url:
        log.info("Используется прокси: %s", proxy_url.split("@")[-1])
        # Отключаем проверку SSL для прокси
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        # Создаём кастомную сессию с прокси
        aiogram_session = CustomAiohttpSession(proxy=proxy_url, ssl_context=ssl_ctx)
    else:
        log.info("Прокси не задан, используется прямое подключение")
        aiogram_session = AiohttpSession()  # стандартная сессия

    # Инициализация бота
    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=aiogram_session,
    )

    dp = Dispatcher(storage=MemoryStorage())

    # HTTP-клиент для бэкенда (не для Telegram)
    http = build_http_client(settings)
    backend = BackendClient(
        http,
        user_role=settings.user_role,
    )
    dp["backend"] = backend

    register_routers(dp)

    # Web API для /notify и /health
    api = build_api(bot, settings.internal_token.get_secret_value())
    config = uvicorn.Config(
        api,
        host="0.0.0.0",
        port=settings.bot_api_port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    log.info(
        "Bot starting (backend=%s, notify-port=%s, admin_chat_id=%s)",
        settings.backend_url,
        settings.bot_api_port,
        settings.admin_chat_id,
    )

    try:
        await asyncio.gather(
            dp.start_polling(bot),
            server.serve(),
            # drain_alerts(bot, backend, settings.admin_chat_id),  # отключено для чистоты
        )
    finally:
        await backend.aclose()
        # Закрываем сессию, если она была создана
        if hasattr(aiogram_session, "_session") and aiogram_session._session:
            await aiogram_session._session.close()
        log.info("Bot stopped gracefully.")


if __name__ == "__main__":
    asyncio.run(main())