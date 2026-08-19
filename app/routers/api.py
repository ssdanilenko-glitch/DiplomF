# app/routers/api.py
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from app.services.agent_persistent import process_with_ticket
from app.services.itilium_client import ItiliumClient

router = APIRouter(prefix="/api", tags=["bot-api"])

class MessageRequest(BaseModel):
    user_id: str
    chat_id: str
    text: str
    platform: str = "telegram"

class MessageResponse(BaseModel):
    answer: str
    attachments: list[str] = []
    action: str | None = None
    context: dict | None = None
    ticket_uid: str | None = None

async def get_itilium_client(request: Request) -> ItiliumClient:
    return request.app.state.itilium_client

@router.post("/process", response_model=MessageResponse)
async def process_bot_message(
    req: MessageRequest,
    itilium: ItiliumClient = Depends(get_itilium_client),
):
    try:
        result = await process_with_ticket(
            user_id=req.user_id,
            chat_id=req.chat_id,
            text=req.text,
            platform=req.platform,
            itilium_client=itilium,
        )
        return MessageResponse(
            answer=result.get("answer", ""),
            attachments=result.get("attachments", []),
            action=result.get("action"),
            context=result.get("context"),
            ticket_uid=result.get("ticket_uid"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))