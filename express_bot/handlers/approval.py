# express_bot/handlers/approval.py
import logging
from pybotx import Bot, HandlerCollector, IncomingMessage  # ✅ Убрали command

logger = logging.getLogger(__name__)


def register(collector: HandlerCollector) -> None:
    @collector.command("/approve", description="Подтвердить или отклонить действие")  # ✅ collector.command
    async def approve_handler(message: IncomingMessage, bot: Bot) -> None:
        args = message.body.strip().split()
        if len(args) < 2:
            await bot.answer_message("Использование: /approve {yes|no}")
            return

        decision_text = args[1].lower()
        if decision_text not in ("yes", "no"):
            await bot.answer_message("Неверная команда. Используйте /approve yes или /approve no")
            return

        user_id = str(message.user.id)

        storage = bot.state.storage if hasattr(bot.state, 'storage') else None
        if not storage:
            await bot.answer_message("❌ Хранилище состояний недоступно.")
            return

        thread_id = await storage.get_pending_thread(user_id)
        if not thread_id:
            await bot.answer_message("❌ Нет активного запроса на подтверждение.")
            return

        resume_value = (decision_text == "yes")
        backend = bot.state.backend if hasattr(bot.state, 'backend') else None
        if not backend:
            await bot.answer_message("❌ Бэкенд недоступен.")
            return

        try:
            result = await backend.resume_agent(thread_id, resume_value)
            await bot.answer_message(result.get("answer", "Действие выполнено."))
            await storage.clear_pending_thread(user_id)
        except Exception as e:
            logger.exception("Resume error")
            await bot.answer_message(f"❌ Ошибка при подтверждении: {e}")