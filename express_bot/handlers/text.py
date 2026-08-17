# express_bot/handlers/text.py
from pybotx import Bot, HandlerCollector, IncomingMessage, default_handler
import httpx

BACKEND_URL = "http://app:8000/api/process"

def register(collector: HandlerCollector):
    @collector.default_handler
    async def text_handler(message: IncomingMessage, bot: Bot):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                BACKEND_URL,
                json={
                    "user_id": str(message.user.id),
                    "chat_id": str(message.chat.id),
                    "text": message.body,
                    "platform": "express",
                },
                timeout=30.0,
            )
            data = resp.json()
            await bot.answer_message(data["answer"])
            for att in data.get("attachments", []):
                await bot.answer_message(att)