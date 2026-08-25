import time
import asyncio
import logging
import operator
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage, ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from app.services.email_service import get_email_service

logger = logging.getLogger("llm-service")

MAX_ITERATIONS = 2
DANGEROUS_TOOLS = ["send_email"]


class PersistentAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    iteration_count: int
    tool_results: Annotated[list[dict], operator.add]
    pending_tool_call: dict | None
    pending_tool_name: str | None


def _find_first_dangerous_call(message: AnyMessage) -> tuple[ToolCall | None, str | None]:
    if not isinstance(message, AIMessage):
        return None, None
    for call in message.tool_calls:
        if call["name"] in DANGEROUS_TOOLS:
            return call, call["name"]
    return None, None


def build_agent(
    checkpointer: Any,
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str | None = None,
):
    bound_model = model.bind_tools(tools)
    tool_by_name = {t.name: t for t in tools}

    async def call_model(state: PersistentAgentState) -> dict:
        loop = asyncio.get_running_loop()
        start = loop.time()
        messages = state["messages"]
        if system_prompt:
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=system_prompt)] + messages
        response = await bound_model.ainvoke(messages)
        elapsed = loop.time() - start
        logger.info(f"⏱️ call_model: {elapsed:.2f} сек")
        return {
            "messages": [response],
            "iteration_count": state["iteration_count"] + 1,
        }

    async def execute_tool(state: PersistentAgentState) -> dict:
        loop = asyncio.get_running_loop()
        start = loop.time()
        last = state["messages"][-1]
        messages: list = []
        results: list[dict] = []
        if hasattr(last, "tool_calls"):
            for call in last.tool_calls:
                if call["name"] in DANGEROUS_TOOLS:
                    continue
                if call["name"] not in tool_by_name:
                    content = f"error: unknown tool '{call['name']}'"
                else:
                    content = str(await tool_by_name[call["name"]].ainvoke(call["args"]))
                messages.append(ToolMessage(content=content, tool_call_id=call["id"]))
                results.append({"name": call["name"], "args": call["args"], "result": content})
        elapsed = loop.time() - start
        logger.info(f"⏱️ execute_tool: {elapsed:.2f} сек")
        return {"messages": messages, "tool_results": results}

    async def prepare_dangerous_action(state: PersistentAgentState) -> dict:
        loop = asyncio.get_running_loop()
        start = loop.time()
        last = state["messages"][-1]
        call, name = _find_first_dangerous_call(last)
        if call and name:
            elapsed = loop.time() - start
            logger.info(f"⏱️ prepare_dangerous_action: {elapsed:.2f} сек")
            return {"pending_tool_call": call, "pending_tool_name": name}
        elapsed = loop.time() - start
        logger.info(f"⏱️ prepare_dangerous_action (no danger): {elapsed:.2f} сек")
        return {}

    async def confirm_and_execute(
        state: PersistentAgentState, config: RunnableConfig
    ) -> dict:
        loop = asyncio.get_running_loop()
        start = loop.time()
        tool_call = state.get("pending_tool_call")
        tool_name = state.get("pending_tool_name")
        if not tool_call or not tool_name:
            elapsed = loop.time() - start
            logger.info(f"⏱️ confirm_and_execute (no pending): {elapsed:.2f} сек")
            return {
                "messages": [
                    ToolMessage(
                        content="❌ Ошибка: нет ожидающего действия.",
                        tool_call_id="",
                    )
                ],
            }

        draft = tool_call["args"]
        role = (config.get("configurable") or {}).get("user_role", "write-with-approve")
        if role == "full":
            decision = True
        else:
            decision = interrupt({
                "type": "approve_action",
                "tool": tool_name,
                "preview": draft,
            })

        approved = decision is True or decision == "approve"
        if approved:
            if tool_name in DANGEROUS_TOOLS:
                tool_fn = tool_by_name.get(tool_name)
                if tool_fn:
                    try:
                        result = await tool_fn.ainvoke(draft)
                        content = result
                    except Exception as e:
                        content = f"❌ Ошибка выполнения {tool_name}: {e}"
                else:
                    content = f"❌ Инструмент {tool_name} не найден"
            else:
                content = f"❌ Неизвестное действие: {tool_name}"
        else:
            content = f"⛔ Действие {tool_name} отменено пользователем."

        elapsed = loop.time() - start
        logger.info(f"⏱️ confirm_and_execute: {elapsed:.2f} сек")

        return {
            "messages": [
                ToolMessage(content=content, tool_call_id=tool_call["id"])
            ],
            "tool_results": [
                {"name": tool_name, "args": draft, "result": content}
            ],
            "pending_tool_call": None,
            "pending_tool_name": None,
        }

    async def force_finish(_state: PersistentAgentState) -> dict:
        return {}

    def route_after_model(
        state: PersistentAgentState,
    ) -> Literal["execute_tool", "prepare_dangerous_action", "force_finish"]:
        if state["iteration_count"] >= MAX_ITERATIONS:
            return "force_finish"
        last = state["messages"][-1]
        if not hasattr(last, "tool_calls"):
            return "force_finish"
        calls = last.tool_calls
        if not calls:
            return "force_finish"
        if any(call["name"] in DANGEROUS_TOOLS for call in calls):
            return "prepare_dangerous_action"
        return "execute_tool"

    builder = StateGraph(PersistentAgentState)
    builder.add_node("call_model", call_model)
    builder.add_node("execute_tool", execute_tool)
    builder.add_node("prepare_dangerous_action", prepare_dangerous_action)
    builder.add_node("confirm_and_execute", confirm_and_execute)
    builder.add_node("force_finish", force_finish)

    builder.add_edge(START, "call_model")
    builder.add_conditional_edges(
        "call_model",
        route_after_model,
        {
            "execute_tool": "execute_tool",
            "prepare_dangerous_action": "prepare_dangerous_action",
            "force_finish": "force_finish",
        },
    )
    builder.add_edge("execute_tool", "call_model")
    builder.add_edge("prepare_dangerous_action", "confirm_and_execute")
    builder.add_edge("confirm_and_execute", "call_model")
    builder.add_edge("force_finish", END)

    return builder.compile(checkpointer=checkpointer)


def _psycopg_uri(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@asynccontextmanager
async def agent_lifespan(
    backend: Literal["memory", "sqlite", "postgres"],
    model: BaseChatModel,
    tools: list[BaseTool],
    *,
    sqlite_path: str = "var/agent_checkpoints.sqlite",
    postgres_url: str = "",
    system_prompt: str | None = None,
) -> AsyncIterator[Any]:
    if backend == "memory":
        yield build_agent(InMemorySaver(), model, tools, system_prompt=system_prompt)
    elif backend == "sqlite":
        from pathlib import Path
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(sqlite_path) as saver:
            await saver.setup()
            yield build_agent(saver, model, tools, system_prompt=system_prompt)
    elif backend == "postgres":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        async with AsyncPostgresSaver.from_conn_string(_psycopg_uri(postgres_url)) as saver:
            await saver.setup()
            yield build_agent(saver, model, tools, system_prompt=system_prompt)
    else:
        raise ValueError(f"неизвестный AGENT_CHECKPOINTER: {backend!r}")

# ============================================================================
# Единая точка входа для обработки сообщений
# ============================================================================

async def process_message(
        user_id: str,
        chat_id: str,
        text: str,
        platform: str = "telegram",
        agent_graph: Any = None,
) -> dict:
    if agent_graph is None:
        return {
            "answer": "❌ Агент не инициализирован. Обратитесь к администратору.",
            "attachments": [],
            "action": None,
            "context": None,
            "ticket_uid": None,
            "need_approval": False,
            "thread_id": None,
        }

    config = {
        "configurable": {
            "thread_id": f"{platform}_{user_id}_{chat_id}_{int(time.time())}",
            "user_role": "write-with-approve",
        }
    }

    try:
        result = await agent_graph.ainvoke(
            {
                "messages": [{"role": "user", "content": text}],
                "iteration_count": 0,
                "tool_results": [],
                "pending_tool_call": None,
                "pending_tool_name": None,
            },
            config=config,
        )

        # Проверяем, есть ли прерывание
        if "__interrupt__" in result:
            thread_id = config["configurable"]["thread_id"]
            last_message = result["messages"][-1]
            answer = last_message.content if hasattr(last_message, "content") else str(last_message)
            return {
                "answer": answer or "Требуется подтверждение действия.",
                "attachments": [],
                "action": None,
                "context": None,
                "ticket_uid": None,
                "need_approval": True,
                "thread_id": thread_id,
            }

        # Берём последнее сообщение
        last_message = result["messages"][-1]
        answer = last_message.content if hasattr(last_message, "content") else str(last_message)

        return {
            "answer": answer,
            "attachments": [],
            "action": None,
            "context": None,
            "ticket_uid": None,
            "need_approval": False,
            "thread_id": None,
        }
    except Exception as e:
        logger.exception("🔥 Ошибка в process_message:")
        return {
            "answer": f"❌ Ошибка при обработке запроса: {e}",
            "attachments": [],
            "action": None,
            "context": None,
            "ticket_uid": None,
            "need_approval": False,
            "thread_id": None,
        }