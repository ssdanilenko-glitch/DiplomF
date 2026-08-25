#!/usr/bin/env python
"""
Скрипт для тестирования отправки письма через Yandex SMTP.

Использует настройки из .env: yandex_email, yandex_app_password, exchange_recipient_email.
Запуск:
    python test_email.py [получатель] [тема] [текст]

Если аргументы не указаны, использует получателя из .env и стандартные тему/текст.
"""

import asyncio
import logging
import sys
from app.services.email_service import get_email_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def send_test_email(to: str | None = None, subject: str = "Тестовое письмо", body: str = "Привет! Это тестовое письмо от ИИ-агента.") -> bool:
    """Отправляет тестовое письмо."""
    email_service = get_email_service()

    # Если получатель не указан, используем из настроек
    if not to:
        to = email_service.recipient_email
        if not to:
            logger.error("Получатель не указан и не задан в настройках (exchange_recipient_email).")
            return False

    logger.info(f"Отправка письма на {to} ...")
    success = await email_service.send_message(
        subject=subject,
        body=body,
        recipient=to,
        is_html=False
    )

    if success:
        logger.info("✅ Письмо успешно отправлено!")
    else:
        logger.error("❌ Не удалось отправить письмо. Проверьте логи выше.")
    return success


def main():
    # Парсим аргументы командной строки
    args = sys.argv[1:]
    to = args[0] if len(args) > 0 else None
    subject = args[1] if len(args) > 1 else "Тестовое письмо от ИИ-агента"
    body = args[2] if len(args) > 2 else "Привет! Это тестовое письмо. Если вы его получили, значит почтовый сервис работает корректно."

    result = asyncio.run(send_test_email(to, subject, body))
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()