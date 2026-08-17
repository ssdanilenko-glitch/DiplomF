# app/routers/api.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.agent_persistent import process_message
from app.services.itilium_client import ItiliumClient
from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["bot-api"])

class MessageRequest(BaseModel):
    user_id: str
    chat_id: str
    text: str
    platform: str = "telegram"  # "telegram" или "express"

class MessageResponse(BaseModel):
    answer: str
    attachments: list[str] = []
    action: str | None = None
    context: dict | None = None
    ticket_uid: str | None = None

@router.post("/process", response_model=MessageResponse)
async def process_bot_message(
    req: MessageRequest,
    itilium: ItiliumClient = Depends(lambda: get_app_state().itilium_client),
):
    """
    Единая точка входа для всех ботов.
    """
    try:
        # 1. Вызов основной логики агента
        result = await process_message(
            user_id=req.user_id,
            chat_id=req.chat_id,
            text=req.text,
            platform=req.platform,
        )

        # 2. Если агент решил, что нужно создать обращение — создаём его в ITILIUM
        ticket_uid = None
        if result.get("action") == "create_ticket" and itilium:
            try:
                ticket = await itilium.add_new_incident(
                    topic=result.get("ticket_topic", f"Обращение от {req.user_id}"),
                    description=result.get("ticket_description", req.text),
                    service_uid=result.get("service_uid"),
                    category_uid=result.get("category_uid"),
                )
                ticket_uid = ticket.get("UID")
                # Добавляем информацию о созданном обращении в ответ
                result["answer"] += f"\n\n✅ Обращение #{ticket_uid} создано в 1С:ITILIUM."
            except Exception as e:
                result["answer"] += f"\n\n❌ Не удалось создать обращение: {e}"

        return MessageResponse(
            answer=result.get("answer", ""),
            attachments=result.get("attachments", []),
            action=result.get("action"),
            context=result.get("context"),
            ticket_uid=ticket_uid,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_app_state():
    # Вспомогательная функция для получения app.state (реализуйте через dependency)
    pass