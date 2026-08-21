# express_bot/handlers/commands.py
import logging
from pybotx import Bot, HandlerCollector, IncomingMessage  # убрали command

logger = logging.getLogger(__name__)

def register(collector: HandlerCollector) -> None:
    @collector.command("/start", description="Начать работу")
    async def start_handler(message: IncomingMessage, bot: Bot) -> None:
        await bot.answer_message(
            "👋 Привет! Я ИИ-ассистент техподдержки УИТ.\n"
            "Задай свой вопрос по 1С:ERP или любому из 82 сервисов — я помогу найти ответ или создам обращение в ITILIUM."
        )

    @collector.command("/help", description="Помощь")
    async def help_handler(message: IncomingMessage, bot: Bot) -> None:
        await bot.answer_message(
            "📋 Доступные команды:\n"
            "/start — начать работу\n"
            "/help — эта справка\n"
            "/status {UID} — проверить статус обращения в ITILIUM\n\n"
            "Просто напиши свой вопрос — я обработаю его через RAG-поиск или создам обращение."
        )

    @collector.command("/status", description="Проверить статус обращения")
    async def status_handler(message: IncomingMessage, bot: Bot) -> None:
        args = message.body.strip().split()
        if len(args) < 2:
            await bot.answer_message("❌ Укажите UID обращения: `/status {UID}`")
            return

        ticket_uid = args[1]
        backend = bot.state.backend
        logger.info(f"✅ Обработчик /start вызван для пользователя {message.user.id}")
        if backend:
            try:
                status_info = await backend.get_ticket_status(ticket_uid)
                await bot.answer_message(
                    f"🔍 Статус обращения {ticket_uid}:\n"
                    f"• Статус: {status_info.get('status', 'неизвестен')}\n"
                    f"• Ответственный: {status_info.get('assignee', 'не назначен')}\n"
                    f"• Обновлено: {status_info.get('updated_at', '')}"
                )
            except Exception as e:
                await bot.answer_message(f"❌ Не удалось получить статус: {e}")
        else:
            await bot.answer_message("⚠️ Бэкенд недоступен.")