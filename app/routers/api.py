import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.services.agent_persistent import process_message

logger = logging.getLogger("llm-service")

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

class ResumeRequest(BaseModel):
    thread_id: str
    resume_value: bool
    platform: str = "telegram"

@router.post("/process", response_model=MessageResponse)
async def process_bot_message(req: MessageRequest, request: Request):
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

@router.post("/resume")
async def resume_agent(req: ResumeRequest, request: Request):
    agent_graph = request.app.state.agent_graph
    if agent_graph is None:
        raise HTTPException(503, "Агент не инициализирован")
    config = {"configurable": {"thread_id": req.thread_id}}
    try:
        # Проверяем состояние перед resume
        state = await agent_graph.get_state(config)
        logger.info(f"Состояние перед resume: {state}")
        # Продолжаем выполнение с переданным решением
        result = await agent_graph.ainvoke(
            None,  # состояние уже сохранено
            config=config,
            resume=req.resume_value,
        )
        logger.info(f"Результат после resume: {result}")
        # Извлекаем последнее сообщение
        last_message = result["messages"][-1]
        answer = last_message.content if hasattr(last_message, "content") else str(last_message)
        return {"answer": answer}
    except Exception as e:
        logger.exception("Ошибка в /resume")
        raise HTTPException(500, str(e))