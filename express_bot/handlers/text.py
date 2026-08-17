import logging
from pybotx import Bot, HandlerCollector, IncomingMessage, default_handler

logger = logging.getLogger(__name__)


def register(collector: HandlerCollector) -> None:
    @collector.default_handler
    async def text_handler(message: IncomingMessage, bot: Bot) -> None:
        """Обрабатывает все текстовые сообщения (кроме команд)."""
        user_id = str(message.user.id)
        chat_id = str(message.chat.id)
        text = message.body

        logger.info(f"eXpress message from {user_id} in {chat_id}: {text[:100]}...")

        # Получаем backend-клиент из состояния бота
        backend = bot.state.get("backend")
        if not backend:
            await bot.answer_message("⚠️ Бэкенд недоступен.")
            return

        try:
            # Отправляем запрос в backend (единый API)
            response = await backend.process_message(
                user_id=user_id,
                chat_id=chat_id,
                text=text,
                platform="express",
            )

            # Отправляем ответ
            answer = response.get("answer", "Ответ не получен.")
            await bot.answer_message(answer)

            # Если есть вложения — отправляем их отдельно (пока как текст)
            for attachment in response.get("attachments", []):
                await bot.answer_message(attachment)

        except Exception as e:
            logger.exception("Error processing message")
            await bot.answer_message("⚠️ Произошла ошибка. Попробуйте позже.")