from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.agent_persistent import process_message
from app.services.itilium_client import ItiliumClient
from app.core.dependencies import get_itilium_client

router = APIRouter(prefix="/express", tags=["express-api"])

class ExpressMessageRequest(BaseModel):
    user_id: str   # в eXpress это UUID
    chat_id: str   # в eXpress это UUID
    text: str
    # Можно добавить поля, специфичные для eXpress, например, имя пользователя
    user_name: str | None = None
    user_email: str | None = None

class ExpressMessageResponse(BaseModel):
    answer: str
    attachments: list[str] = []
    action: str | None = None
    context: dict | None = None
    ticket_uid: str | None = None

@router.post("/process", response_model=ExpressMessageResponse)
async def process_express_message(
    req: ExpressMessageRequest,
    itilium: ItiliumClient = Depends(get_itilium_client),
):
    """
    Обработка сообщения из eXpress.
    """
    try:
        # Можно расширить контекст для eXpress (например, добавить имя пользователя)
        result = await process_message(
            user_id=req.user_id,
            chat_id=req.chat_id,
            text=req.text,
            platform="express",
            extra_context={"user_name": req.user_name, "user_email": req.user_email},
        )

        ticket_uid = None
        if result.get("action") == "create_ticket" and itilium:
            try:
                ticket = await itilium.add_new_incident(
                    topic=result.get("ticket_topic", f"eXpress: {req.text[:50]}"),
                    description=result.get("ticket_description", req.text),
                    service_uid=result.get("service_uid"),
                    category_uid=result.get("category_uid"),
                )
                ticket_uid = ticket.get("UID")
                result["answer"] += f"\n\n✅ Обращение #{ticket_uid} создано в 1С:ITILIUM."
            except Exception as e:
                result["answer"] += f"\n\n❌ Ошибка создания: {e}"

        return ExpressMessageResponse(
            answer=result.get("answer", ""),
            attachments=result.get("attachments", []),
            action=result.get("action"),
            context=result.get("context"),
            ticket_uid=ticket_uid,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))