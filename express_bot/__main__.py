import asyncio
import logging
from uuid import UUID

import uvicorn
from pybotx import Bot, BotAccountWithSecret, HandlerCollector
from httpx import AsyncClient

from express_bot.config import get_bot_settings
from express_bot.handlers import register_handlers
from express_bot.services.backend import BackendClient
from express_bot.web import build_api
from express_bot.services.storage import StateStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("express_bot")


async def main() -> None:
    settings = get_bot_settings()

    # Коллектор обработчиков
    collector = HandlerCollector()
    register_handlers(collector)

    # Создаём бота eXpress
    bot = Bot(
        collectors=[collector],
        bot_accounts=[
            BotAccountWithSecret(
                id=UUID(settings.express_bot_id),
                cts_url=settings.express_cts_host,  # <-- исправлено
                secret_key=settings.express_secret_key.get_secret_value(),
            ),
        ],
    )
    # HTTP-клиент для бэкенда
    http_client = AsyncClient()
    backend = BackendClient(http_client)

    # Сохраняем backend в состоянии бота для доступа из обработчиков
    bot.state.backend = backend

    # FastAPI-приложение с вебхуком
    api = build_api(bot, settings.internal_token.get_secret_value())

    config = uvicorn.Config(
        api,
        host="0.0.0.0",
        port=settings.bot_api_port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    log.info(
        "eXpress bot starting (backend=%s, webhook-port=%s)",
        settings.backend_url,
        settings.bot_api_port,
    )

    # Инициализация хранилища (опционально)
    try:
        storage = StateStorage()
        await storage.connect()
        bot.state.storage = storage
        log.info("Redis подключён")
    except Exception as e:
        log.warning(f"Redis не подключён: {e}. Функции состояний (подтверждения) будут недоступны.")
        bot.state.storage = None


    try:
        # Запускаем инициализацию бота и веб-сервер
        await asyncio.gather(
            bot.startup(),   # подключаемся к CTS
            server.serve(),
        )
    finally:
        await bot.shutdown()
        await http_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())