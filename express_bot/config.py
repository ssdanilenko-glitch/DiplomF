from functools import lru_cache
from typing import Annotated, Optional
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class ExpressBotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- eXpress настройки ---
    express_bot_id: str                     # UUID бота из панели администратора
    express_cts_host: str                   # адрес CTS-сервера
    express_secret_key: SecretStr           # секретный ключ бота

    # --- Backend ---
    backend_url: str = "http://app:8000"
    request_timeout: float = 30.0

    # --- Канал backend → bot (/notify) ---
    internal_token: SecretStr = SecretStr("change-me")
    bot_api_port: int = 9001                # порт для вебхука

    # --- Админка ---
    admin_token: SecretStr = SecretStr("change-me-admin")
    bot_admin_ids: Annotated[list[str], NoDecode] = []  # user_ids (строки)

    # --- Чат для алертов ---
    admin_chat_id: Optional[str] = None     # chat_id (строка)

    @field_validator("bot_admin_ids", mode="before")
    @classmethod
    def _parse_ids(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


@lru_cache
def get_bot_settings() -> ExpressBotSettings:
    return ExpressBotSettings()