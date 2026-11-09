"""FastAPI 应用工厂。

无状态、可水平扩展；在 lifespan 中初始化 MySQL(异步)、Redis、Milvus、
LLMProvider、LangGraph checkpointer/store，并编译多 Agent 图。
"""

from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app import models  # noqa: F401  确保 create_all 前模型已注册
from app.agents.graph import build_agent
from app.agents.tools import TOOLS
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.redis import close_redis, get_redis
from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.llm.embeddings import get_embeddings
from app.llm.provider import LLMProvider
from app.memory.checkpoint import enter_memory
from app.middleware.request_id import RequestIDMiddleware
from app.retrieval.milvus import ensure_collection

logger = get_logger(__name__)


def _setup_otel(app: FastAPI) -> None:
    """可选 OTel 埋点（Jaeger / OTLP）；失败不影响启动。"""
    if not settings.OTEL_ENABLED:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": "trullex-backend"}))
        exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OTel 埋点已启用", endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OTel 初始化失败", error=str(exc))


async def _seed_admin() -> None:
    """首次启动时若默认管理员不存在则自动创建（账号/密码来自环境变量）。"""
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.models.user import User

    try:
        async with async_session_factory() as session:
            exists = await session.execute(
                select(User).where(User.username == settings.ADMIN_USERNAME)
            )
            if exists.scalar_one_or_none() is not None:
                return
            session.add(
                User(
                    username=settings.ADMIN_USERNAME,
                    email=settings.ADMIN_EMAIL,
                    full_name="系统管理员",
                    hashed_password=hash_password(settings.ADMIN_PASSWORD),
                    role="admin",
                    is_active=True,
                )
            )
            await session.commit()
        logger.info("已创建默认管理员账号", username=settings.ADMIN_USERNAME)
    except Exception as exc:  # noqa: BLE001
        logger.warning("默认管理员创建失败", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(settings.LOG_LEVEL)
    logger.info("途律 · TruLex后端启动中")

    # 1) MySQL：异步引擎 + 建表（无状态服务，靠表结构收敛，生产建议改用 Alembic）
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MySQL 初始化失败", error=str(exc))

    # 1.1) 首次启动种子管理员（默认 admin / admin123456，可用环境变量覆盖）
    await _seed_admin()

    # 2) Redis
    try:
        get_redis()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis 初始化失败", error=str(exc))

    # 3) Milvus collection（维度固定 1024）
    try:
        ensure_collection()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Milvus 初始化失败", error=str(exc))

    # 4) LLMProvider 与 Embedding
    llm = LLMProvider()
    app.state.embeddings = get_embeddings()

    # 5) LangGraph checkpointer / store（短期 + 长期记忆）
    stack = AsyncExitStack()
    checkpointer = store = None
    try:
        checkpointer, store = await enter_memory(stack)
    except Exception as exc:  # noqa: BLE001
        logger.warning("记忆层初始化失败", error=str(exc))
        await stack.aclose()
        stack = AsyncExitStack()

    # 6) 编译多 Agent 图
    agent = build_agent(llm=llm, tools=TOOLS, checkpointer=checkpointer, store=store)

    app.state.llm = llm
    app.state.agent = agent
    app.state.exit_stack = stack

    logger.info("后端启动完成")
    yield

    logger.info("后端开始关停")
    try:
        await engine.dispose()
    except Exception:  # noqa: BLE001
        pass
    try:
        await close_redis()
    except Exception:  # noqa: BLE001
        pass
    try:
        await stack.aclose()
    except Exception:  # noqa: BLE001
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="途律 · TruLex",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 请求 ID 中间件
    app.add_middleware(RequestIDMiddleware)

    # 健康检查
    @app.get("/healthz", tags=["system"])
    async def healthz() -> dict:
        return {"status": "ok", "service": "trullex-backend"}

    # Prometheus 指标
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    # 业务路由
    app.include_router(api_router)

    # OTel 埋点
    _setup_otel(app)

    return app


app: FastAPI = create_app()
