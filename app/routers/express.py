# app/routers/express.py
import json
import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pybotx import (
    Bot,
    BotAccountWithSecret,
    HandlerCollector,
    IncomingMessage,
)

from app.core.config import get_settings
from app.services.agent_persistent import process_message
from app.services.itilium_client import ItiliumClient

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/express", tags=["express"])

# Глобальные переменные
_itilium_client: Optional[ItiliumClient] = None
_agent_graph: Any = None

# ============================================================================
# 1. ОБРАБОТЧИКИ КОМАНД
# ============================================================================

collector = HandlerCollector()

@collector.command("/start", description="Начать работу с ассистентом")
async def start_handler(message: IncomingMessage, bot: Bot) -> None:
    await bot.answer_message(
        "👋 Привет! Я ИИ-ассистент техподдержки УИТ.\n"
        "Задай свой вопрос по 1С:ERP или любому из 82 сервисов — я помогу найти ответ или создам обращение в ITILIUM."
    )

@collector.command("/help", description="Помощь по командам")
async def help_handler(message: IncomingMessage, bot: Bot) -> None:
    await bot.answer_message(
        "📋 Доступные команды:\n"
        "/start — начать работу\n"
        "/help — эта справка\n"
        "/status {UID} — проверить статус обращения в ITILIUM\n\n"
        "Просто напиши свой вопрос — я обработаю его через RAG-поиск или создам обращение."
    )

@collector.command("/status", description="Проверить статус обращения в ITILIUM")
async def status_handler(message: IncomingMessage, bot: Bot) -> None:
    args = message.body.strip().split()
    if len(args) < 2:
        await bot.answer_message("❌ Укажите UID обращения: `/status {UID}`")
        return

    ticket_uid = args[1]
    if _itilium_client:
        try:
            detail = await _itilium_client.get_incident_detail(ticket_uid)
            status_text = detail.get("Status", "неизвестно")
            await bot.answer_message(f"🔍 Статус обращения {ticket_uid}: {status_text}")
        except Exception as e:
            await bot.answer_message(f"❌ Ошибка получения статуса: {e}")
    else:
        await bot.answer_message(
            f"🔍 Проверяю статус обращения {ticket_uid}...\n"
            "(Интеграция с ITILIUM для проверки статуса будет добавлена позже)"
        )

# ----------------------------------------------------------------------------
# ОСНОВНОЙ ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ
# ----------------------------------------------------------------------------
@collector.default_message_handler
async def default_handler(message: IncomingMessage, bot: Bot) -> None:
    user_id = str(message.user.id)
    chat_id = str(message.chat.id)
    text = message.body

    if _agent_graph is None:
        await bot.answer_message("⚠️ Агент не инициализирован. Обратитесь к администратору.")
        return

    try:
        result = await process_message(
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            platform="express",
            agent_graph=_agent_graph,
        )
        await bot.answer_message(result.get("answer", ""))
        for attachment in result.get("attachments", []):
            await bot.answer_message(attachment)
    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        await bot.answer_message("⚠️ Произошла ошибка. Попробуйте позже.")

# ============================================================================
# 2. ИНИЦИАЛИЗАЦИЯ БОТА
# ============================================================================

def create_express_bot() -> Bot:
    return Bot(
        collectors=[collector],
        bot_accounts=[
            BotAccountWithSecret(
                id=UUID(settings.EXPRESS_BOT_ID),
                host=settings.EXPRESS_CTS_HOST,
                secret_key=settings.EXPRESS_SECRET_KEY,
            ),
        ],
    )

express_bot: Optional[Bot] = None

# ============================================================================
# 3. FASTAPI ЭНДПОИНТЫ (вебхук + статус)
# ============================================================================

@router.post("/webhook")
async def webhook_handler(request: Request) -> JSONResponse:
    global express_bot
    if express_bot is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Express bot not initialized"
        )

    try:
        raw_body = await request.json()
        logger.debug(f"Webhook payload: {json.dumps(raw_body, ensure_ascii=False)[:200]}...")
        await express_bot.async_execute_raw_bot_command(raw_body)
        return JSONResponse(status_code=200, content={"status": "ok"})
    except Exception as e:
        logger.exception(f"Webhook processing error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)}
        )

@router.get("/status")
async def status_check() -> dict:
    return {
        "status": "running" if express_bot else "not_initialized",
        "bot_id": settings.EXPRESS_BOT_ID,
    }

# ============================================================================
# 4. LIFESPAN ИНТЕГРАЦИЯ
# ============================================================================

async def init_express_bot(
    itilium_client: Optional[ItiliumClient] = None,
    agent_graph: Any = None,
) -> None:
    """Инициализация бота при старте приложения."""
    global express_bot, _itilium_client, _agent_graph
    _itilium_client = itilium_client
    _agent_graph = agent_graph
    express_bot = create_express_bot()
    await express_bot.startup()
    logger.info("Express bot initialized successfully")

async def shutdown_express_bot() -> None:
    global express_bot
    if express_bot:
        await express_bot.shutdown()
        express_bot = None
        logger.info("Express bot shutdown successfully")