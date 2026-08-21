from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.services.agent_persistent import process_message

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

@router.post("/process", response_model=MessageResponse)
async def process_bot_message(
    req: MessageRequest,
    request: Request,
):
    agent_graph = request.app.state.agent_graph
    if agent_graph is None:
        raise HTTPException(503, "Агент не инициализирован")

    try:
        result = await process_message(
            user_id=req.user_id,
            chat_id=req.chat_id,
            text=req.text,
            platform=req.platform,
            agent_graph=agent_graph,
        )
        return MessageResponse(**result)
    except Exception as e:
        raise HTTPException(500, detail=str(e))