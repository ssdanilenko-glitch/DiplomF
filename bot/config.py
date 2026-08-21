"""Настройки Telegram-бота.

Бот читает свои переменные из того же .env, что и backend, но через
отдельный класс — чтобы не тащить LLM/DB-зависимости в bot-процесс.
"""

from functools import lru_cache
from typing import Annotated

from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pydantic import SecretStr, Field, field_validator

class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    telegram_proxy_url: str | None = Field(
        default=None,
        alias="TELEGRAM_PROXY_URL"
    )
    bot_token: SecretStr
    backend_url: str = "http://app:8000"
    # NoDecode — отключаем штатный JSON-парсинг list[int] для env-переменной,
    # чтобы значение "123,456" попало в наш валидатор как строка.
    bot_admin_ids: Annotated[list[int], NoDecode] = []
    request_timeout: float = 30.0
    # /notify-канал backend → bot. Токен — общий секрет.
    internal_token: SecretStr = SecretStr("change-me")
    bot_api_port: int = 9000
    # X-Admin-Token для вызовов /chats/admin/* из бота.
    admin_token: SecretStr = SecretStr("change-me-admin")
    # Telegram chat_id админ-группы для алертов. None — drain отключён.
    admin_chat_id: int | None = None
    user_role: str = "write-with-approve"

    @field_validator("bot_admin_ids", mode="before")
    @classmethod
    def _parse_ids(cls, v):
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        return v


@lru_cache
def get_bot_settings() -> BotSettings:
    return BotSettings()
