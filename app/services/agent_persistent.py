"""Персистентный ReAct-агент: чекпоинтер + человек в цикле для опасных действий.

Поддерживает несколько опасных инструментов (send_email, create_itilium_ticket).
Опасные инструменты проходят через HIL-гейт: сначала prepare_dangerous_action,
затем confirm_and_execute с interrupt().

Бэкенд чекпоинтера выбирается через `AGENT_CHECKPOINTER`: `memory` | `sqlite` |
`postgres`. Схему чекпоинтера ведёт `setup()`.
"""

import operator
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from app.services.itilium_client import ItiliumClient

MAX_ITERATIONS = 3
DANGEROUS_TOOLS = ["send_email", "create_itilium_ticket"]

# Реальный side-effect отправки: async-callable, инжектируется в фабрику.
SendEmailFn = Callable[[dict], Awaitable[None]]


class PersistentAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    iteration_count: int
    tool_results: Annotated[list[dict], operator.add]
    pending_tool_call: dict | None   # tool_call, ожидающий подтверждения
    pending_tool_name: str | None    # имя опасного инструмента


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Отправляет письмо клиенту. Опасное действие — требует подтверждения человека."""
    return "queued-for-approval"


def _find_first_dangerous_call(message: AnyMessage) -> tuple[dict | None, str | None]:
    """Находит первый вызов опасного инструмента в сообщении."""
    for call in message.tool_calls:
        if call["name"] in DANGEROUS_TOOLS:
            return call, call["name"]
    return None, None


def build_agent(
    checkpointer: Any,
    model: BaseChatModel,
    tools: list[BaseTool],
    send_email_fn: SendEmailFn,
    itilium_client: ItiliumClient | None = None,
    system_prompt: str | None = None,
):
    """Компилирует персистентный ReAct-граф с HIL-гейтом для опасных инструментов.

    `tools` — безопасные инструменты (multiply, search_knowledge_base).
    Опасные инструменты (send_email, create_itilium_ticket) добавляются отдельно
    и проходят через HIL-ветку.
    """
    # Собираем все инструменты: безопасные + опасные
    all_tools = [*tools, send_email]
    # create_itilium_ticket добавляем, только если есть клиент
    if itilium_client is not None:
        from app.agents.tools import build_create_ticket_tool
        create_ticket_tool = build_create_ticket_tool(itilium_client)
        all_tools.append(create_ticket_tool)

    bound_model = model.bind_tools(all_tools)
    tool_by_name = {t.name: t for t in tools}  # только безопасные

    async def call_model(state: PersistentAgentState) -> dict:
        messages = state["messages"]
        # Добавляем системный промпт, если задан и ещё не добавлен
        if system_prompt:
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=system_prompt)] + messages

        response = await bound_model.ainvoke(messages)
        return {
            "messages": [response],
            "iteration_count": state["iteration_count"] + 1,
        }

    async def execute_tool(state: PersistentAgentState) -> dict:
        """Выполняет безопасные инструменты. Опасные пропускает."""
        last = state["messages"][-1]
        messages: list = []
        results: list[dict] = []
        for call in last.tool_calls:
            if call["name"] in DANGEROUS_TOOLS:
                continue  # опасные идут через HIL
            if call["name"] not in tool_by_name:
                content = f"error: unknown tool '{call['name']}'"
            else:
                content = str(await tool_by_name[call["name"]].ainvoke(call["args"]))
            messages.append(ToolMessage(content=content, tool_call_id=call["id"]))
            results.append(
                {"name": call["name"], "args": call["args"], "result": content}
            )
        return {"messages": messages, "tool_results": results}

    async def prepare_dangerous_action(state: PersistentAgentState) -> dict:
        """Сохраняет первый опасный tool_call в состояние."""
        last = state["messages"][-1]
        call, name = _find_first_dangerous_call(last)
        if call and name:
            return {
                "pending_tool_call": call,
                "pending_tool_name": name,
            }
        return {}

    async def confirm_and_execute(
        state: PersistentAgentState, config: RunnableConfig
    ) -> dict:
        """Запрашивает подтверждение и выполняет опасное действие."""
        tool_call = state.get("pending_tool_call")
        tool_name = state.get("pending_tool_name")

        if not tool_call or not tool_name:
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

        # HIL: запрос подтверждения
        if role == "full":
            decision = True
        else:
            decision = interrupt({
                "type": "approve_action",
                "tool": tool_name,
                "preview": draft,
            })

        approved = decision is True or decision == "approve"

        # Выполнение
        if approved:
            if tool_name == "send_email":
                await send_email_fn(draft)
                content = f"✅ письмо отправлено: {draft.get('subject', '')}"
            elif tool_name == "create_itilium_ticket":
                if itilium_client is None:
                    content = "❌ Клиент ITILIUM недоступен."
                else:
                    try:
                        ticket = await itilium_client.add_new_incident(
                            topic=draft.get("topic"),
                            description=draft.get("description"),
                            service_uid=draft.get("service_uid"),
                            category_uid=draft.get("category_uid"),
                        )
                        uid = ticket.get("UID")
                        content = f"✅ Обращение #{uid} создано в 1С:ITILIUM."
                    except Exception as e:
                        content = f"❌ Ошибка создания обращения: {e}"
            else:
                content = f"❌ Неизвестное действие: {tool_name}"
        else:
            content = f"⛔ Действие {tool_name} отменено пользователем."

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

    async def force_finish(state: PersistentAgentState) -> dict:
        return {}

    def route_after_model(
        state: PersistentAgentState,
    ) -> Literal["execute_tool", "prepare_dangerous_action", "force_finish"]:
        if state["iteration_count"] >= MAX_ITERATIONS:
            return "force_finish"
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None)
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
    """AsyncPostgresSaver работает на psycopg (v3): `postgresql://`, без `+asyncpg`."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@asynccontextmanager
async def agent_lifespan(
    backend: Literal["memory", "sqlite", "postgres"],
    model: BaseChatModel,
    tools: list[BaseTool],
    send_email_fn: SendEmailFn,
    *,
    sqlite_path: str = "var/agent_checkpoints.sqlite",
    postgres_url: str = "",
    itilium_client: ItiliumClient | None = None,
    system_prompt: str | None = None,
) -> AsyncIterator[Any]:
    """Поднимает нужный чекпоинтер и отдаёт скомпилированный граф."""
    if backend == "memory":
        yield build_agent(
            InMemorySaver(),
            model,
            tools,
            send_email_fn,
            itilium_client=itilium_client,
            system_prompt=system_prompt,
        )
    elif backend == "sqlite":
        from pathlib import Path
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(sqlite_path) as saver:
            await saver.setup()
            yield build_agent(
                saver,
                model,
                tools,
                send_email_fn,
                itilium_client=itilium_client,
                system_prompt=system_prompt,
            )
    elif backend == "postgres":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(
            _psycopg_uri(postgres_url)
        ) as saver:
            await saver.setup()
            yield build_agent(
                saver,
                model,
                tools,
                send_email_fn,
                itilium_client=itilium_client,
                system_prompt=system_prompt,
            )
    else:
        raise ValueError(f"неизвестный AGENT_CHECKPOINTER: {backend!r}")


# ============================================================================
# Единая точка входа для обработки сообщений (вызов агента)
# ============================================================================

# app/services/agent_persistent.py (фрагмент функции process_message)

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
        }

    config = {
        "configurable": {
            "thread_id": f"{platform}_{user_id}_{chat_id}",
            "user_role": "write-with-approve",
        }
    }

    try:
        # Инициализируем полное состояние агента
        result = await agent_graph.ainvoke(
            {
                "messages": [{"role": "user", "content": text}],
                "iteration_count": 0,           # <-- добавляем
                "tool_results": [],             # <-- добавляем
                "pending_tool_call": None,      # <-- добавляем
                "pending_tool_name": None,      # <-- добавляем
            },
            config=config,
        )
        last_message = result["messages"][-1]
        answer = last_message.content if hasattr(last_message, "content") else str(last_message)
        return {
            "answer": answer,
            "attachments": [],
            "action": None,
            "context": None,
            "ticket_uid": None,
        }
    except Exception as e:
        return {
            "answer": f"❌ Ошибка при обработке запроса: {e}",
            "attachments": [],
            "action": None,
            "context": None,
            "ticket_uid": None,
        }
