import asyncio
import logging
import time
import uuid
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.admin.routes import router as admin_router
from app.core.config import get_settings
from app.core.exceptions import (
    LLMAuthError,
    LLMContentFilterError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.observability import setup_tracing
from app.routers import agent, documents, health, models, rag
from app.services.vector_store import VectorStore

from app.routers import express
from app.routers.express import init_express_bot, shutdown_express_bot

from app.services.itilium_client import ItiliumClient
from app.routers import api

from app.agents.tools import build_all_tools

logger = logging.getLogger("llm-service")
logging.basicConfig(level=logging.INFO)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ===== 1. Phoenix-трейсинг =====
    app.state.tracing_enabled = setup_tracing(settings)

    # ===== 2. LLM-клиент =====
    app.state.llm = AsyncOpenAI(
        api_key=settings.llm.openai_api_key.get_secret_value(),
        base_url=settings.llm.base_url,
        timeout=settings.llm.request_timeout,
        max_retries=settings.llm.max_retries,
    )

    # ===== 3. Redis (опционально) =====
    app.state.redis = None
    try:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        app.state.redis = redis_client
    except Exception as e:
        logger.warning("Redis недоступен (%s) — продолжаем без кеша", e)

    # ===== 4. PostgreSQL (опционально) =====
    app.state.async_engine = None
    app.state.session_factory = None
    try:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        app.state.async_engine = engine
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    except Exception as e:
        logger.warning("Postgres engine не создан (%s)", e)

    # ===== 5. Qdrant (векторная БД) =====
    app.state.vector_store = None
    try:
        vector_store = VectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            collection=settings.qdrant_collection,
            dim=settings.embedding_dim,
        )
        await vector_store.ensure_collection()
        app.state.vector_store = vector_store
        logger.info("Qdrant подключён: %s, коллекция %s", settings.qdrant_url, settings.qdrant_collection)
    except Exception as e:
        logger.warning("Qdrant недоступен (%s)", e)

    # ===== 6. RAG (условно, если включён в настройках) =====
    # Добавьте в .env: RAG_ENABLED=true/false
    rag_enabled = getattr(settings, "rag_enabled", False)
    app.state.ingestion_service = None
    app.state.rag_service = None

    if rag_enabled:
        try:
            from app.services.ingestion import IngestionService
            from app.services.rag import RAGService

            ingestion = IngestionService(settings)
            app.state.ingestion_service = ingestion
            if ingestion.is_collection_empty():
                await asyncio.to_thread(ingestion.ingest_all)

            rag_service = RAGService(settings)
            await asyncio.to_thread(rag_service.build)
            app.state.rag_service = rag_service
            logger.info("RAG-сервис готов (коллекция %s)", settings.rag_collection)
        except Exception as e:
            logger.warning("RAG/индексация не инициализированы (%s)", e)
    else:
        logger.info("RAG отключён настройками (RAG_ENABLED=false)")

    # ===== 7. Клиент ITILIUM =====
    app.state.itilium_client = None
    try:
        client = ItiliumClient()
        if await client.authenticate():
            app.state.itilium_client = client
            logger.info("1С:ITILIUM клиент инициализирован")
        else:
            logger.warning("1С:ITILIUM аутентификация не пройдена")
    except Exception as e:
        logger.warning("1С:ITILIUM клиент не инициализирован: %s", e)

    # ===== 8. Агент (LangGraph) =====
    system_prompt = settings.SYSTEM_PROMPT or None
    app.state.agent_graph = None
    agent_stack = AsyncExitStack()
    try:
        from langchain_openai import ChatOpenAI
        from app.services.agent_persistent import agent_lifespan

        agent_model = ChatOpenAI(
            model=settings.llm.default_model,
            base_url=settings.llm.base_url,
            temperature=0,
            api_key=settings.llm.openai_api_key.get_secret_value(),
            timeout=settings.llm.request_timeout,
        )

        # --- Функция поиска по базе знаний (если RAG включён) ---
        if rag_enabled and app.state.rag_service is not None:
            async def _search_kb(query: str) -> dict:
                return await app.state.rag_service.answer(query)
        else:
            # Заглушка, если RAG отключён
            async def _search_kb(query: str) -> dict:
                return {"answer": "RAG отключён", "sources": [], "confident": False}

        # --- Создаём все инструменты через единую фабрику ---
        agent_tools = build_all_tools(
            search_fn=_search_kb,
            itilium_client=app.state.itilium_client,
        )
        logger.info(f"🔧 Инструменты для агента: {[t.name for t in agent_tools]}")
        # --- Собираем агента ---
        app.state.agent_graph = await agent_stack.enter_async_context(
            agent_lifespan(
                backend=settings.agent_checkpointer,
                model=agent_model,
                tools=agent_tools,
                sqlite_path=settings.agent_sqlite_path,
                postgres_url=settings.database_url,
                system_prompt=system_prompt,
            )
        )
        logger.info("Персистентный агент собран (backend=%s)", settings.agent_checkpointer)
    except Exception as e:
        app.state.agent_graph = None
        logger.warning("Агентный граф не собран (%s)", e)

    # ===== 9. eXpress-бот =====
    try:
        await init_express_bot(
            itilium_client=app.state.itilium_client,
            agent_graph=app.state.agent_graph,
        )
        logger.info("eXpress бот инициализирован")
    except Exception as e:
        logger.warning("eXpress бот не инициализирован (%s)", e)

    # ===== Приложение запущено =====
    yield

    # ===== Закрытие ресурсов =====
    try:
        await shutdown_express_bot()
    except Exception as e:
        logger.warning("Ошибка при остановке eXpress бота: %s", e)

    await agent_stack.aclose()

    try:
        await app.state.llm.close()
    except Exception:
        logger.exception("ошибка при закрытии LLM-клиента")

    if app.state.redis is not None:
        try:
            await app.state.redis.close()
        except Exception:
            logger.exception("ошибка при закрытии Redis")

    if app.state.async_engine is not None:
        try:
            await app.state.async_engine.dispose()
        except Exception:
            logger.exception("ошибка при остановке engine Postgres")

    if app.state.vector_store is not None:
        try:
            await app.state.vector_store.close()
        except Exception:
            logger.exception("ошибка при закрытии Qdrant-клиента")

    if app.state.rag_service is not None:
        try:
            await app.state.rag_service.close()
        except Exception:
            logger.exception("ошибка при закрытии RAG-сервиса")

    if app.state.ingestion_service is not None:
        try:
            app.state.ingestion_service.close()
        except Exception:
            logger.exception("ошибка при закрытии индексатора")


# ===== Создание приложения FastAPI =====
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="FastAPI-сервис для LLM с кешированием, стримингом и модерацией",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-LLM-Cost-USD"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
    request.state.llm_cost = 0.0
    request.state.llm_tokens = 0

    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled", extra={"request_id": request.state.request_id})
        raise

    duration_ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-LLM-Cost-USD"] = f"{request.state.llm_cost:.6f}"
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request.state.request_id,
    )
    return response


# ===== Глобальные обработчики исключений =====
_STATUS_MAP = [
    (LLMRateLimitError, 429, "llm_rate_limit"),
    (LLMAuthError, 502, "llm_auth_error"),
    (LLMTimeoutError, 504, "llm_timeout"),
    (LLMContentFilterError, 400, "content_filter"),
    (LLMError, 502, "llm_error"),
]


@app.exception_handler(LLMError)
async def handle_llm_error(request: Request, exc: LLMError):
    for cls, status, code in _STATUS_MAP:
        if isinstance(exc, cls):
            return JSONResponse(
                status_code=status,
                content={"error": {"code": code, "message": str(exc)}},
                headers={"X-Request-ID": getattr(request.state, "request_id", "")},
            )
    return JSONResponse(
        status_code=502,
        content={"error": {"code": "llm_error", "message": str(exc)}},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "fields": errors}},
        headers={"X-Request-ID": getattr(request.state, "request_id", "")},
    )


# ===== Подключение роутеров =====
app.include_router(admin_router)
app.include_router(models.router)
app.include_router(health.router)
app.include_router(rag.router)
app.include_router(documents.router)
app.include_router(agent.router)
app.include_router(express.router)
app.include_router(api.router)