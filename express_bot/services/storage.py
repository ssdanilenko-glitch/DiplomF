# express_bot/services/storage.py
import json
import logging
from typing import Optional, Any, Dict
import redis.asyncio as redis
from express_bot.config import get_bot_settings

logger = logging.getLogger(__name__)
settings = get_bot_settings()


class StateStorage:
    """Хранилище состояний бота на Redis"""

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self._client: Optional[redis.Redis] = None
        self.ttl = settings.state_ttl

    async def connect(self) -> None:
        """Подключение к Redis"""
        try:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=settings.redis_timeout,
            )
            await self._client.ping()
            logger.info("✅ Подключение к Redis установлено")
        except Exception as e:
            logger.exception("❌ Ошибка подключения к Redis")
            raise

    async def close(self) -> None:
        """Закрытие соединения"""
        if self._client:
            await self._client.close()
            logger.info("🔌 Соединение с Redis закрыто")

    async def set_state(self, user_id: str, state: str, data: Dict[str, Any] = None) -> None:
        """Установить состояние для пользователя"""
        key = f"express_bot:state:{user_id}"
        value = json.dumps({
            "state": state,
            "data": data or {},
            "created_at": None  # можно добавить timestamp
        })
        await self._client.setex(key, self.ttl, value)
        logger.debug(f"Состояние для {user_id} сохранено: {state}")

    async def get_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получить состояние пользователя"""
        key = f"express_bot:state:{user_id}"
        value = await self._client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Ошибка декодирования состояния для {user_id}")
                return None
        return None

    async def clear_state(self, user_id: str) -> None:
        """Очистить состояние пользователя"""
        key = f"express_bot:state:{user_id}"
        await self._client.delete(key)
        logger.debug(f"Состояние для {user_id} очищено")

    async def set_pending_thread(self, user_id: str, thread_id: str) -> None:
        """Сохранить thread_id для ожидающего подтверждения"""
        # Используем отдельный ключ для pending
        key = f"express_bot:pending:{user_id}"
        await self._client.setex(key, self.ttl, thread_id)
        logger.debug(f"Pending thread для {user_id}: {thread_id}")

    async def get_pending_thread(self, user_id: str) -> Optional[str]:
        """Получить thread_id ожидающего подтверждения"""
        key = f"express_bot:pending:{user_id}"
        value = await self._client.get(key)
        return value

    async def clear_pending_thread(self, user_id: str) -> None:
        """Очистить pending thread"""
        key = f"express_bot:pending:{user_id}"
        await self._client.delete(key)
        logger.debug(f"Pending thread для {user_id} очищен")