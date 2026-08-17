import logging
from fastapi import FastAPI, Request, Header, HTTPException
from pydantic import BaseModel
from pybotx import Bot, BotAccountWithSecret, HandlerCollector

from express_bot.config import get_bot_settings
from express_bot.handlers import register_handlers

logger = logging.getLogger(__name__)


class NotifyRequest(BaseModel):
    chat_id: str
    text: str


def build_api(bot: Bot, internal_token: str) -> FastAPI:
    """Строит FastAPI-приложение с вебхуком для eXpress."""
    api = FastAPI(title="express-bot-api")

    @api.post("/webhook")
    async def webhook(request: Request):
        """Принимает вебхуки от eXpress."""
        try:
            raw_body = await request.json()
            logger.debug(f"Webhook payload: {raw_body}")
            await bot.async_execute_raw_bot_command(raw_body)
            return {"status": "ok"}
        except Exception as e:
            logger.exception("Webhook processing error")
            raise HTTPException(status_code=500, detail=str(e))

    @api.post("/notify")
    async def notify(
        req: NotifyRequest,
        x_internal_token: str = Header(...),
    ) -> dict:
        if x_internal_token != internal_token:
            raise HTTPException(status_code=401, detail="invalid token")
        await bot.send_message(chat_id=req.chat_id, text=req.text)
        return {"ok": True}

    @api.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return api