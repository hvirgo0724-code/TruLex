"""全局配置：从环境变量读取（与 docker-compose / .env.example 的键名严格一致）。"""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ===== LLM（DashScope 兼容 OpenAI 协议）=====
    API_KEY: str = "sk-xxxxxxxxxxxxxxxx"
    BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL_NAME: str = "qwen-plus"

    # ===== Embedding =====
    EMBEDDING_MODEL: str = "qwen3.7-text-embedding"
    EMBEDDING_DIM: int = 1024
    EMBEDDING_CHUNK_SIZE: int = 10

    # ===== 关系数据库 MySQL（业务数据，async aiomysql）=====
    MYSQL_URL: str = "mysql+aiomysql://legal:legal@mysql:3306/legal"

    # ===== 智能体记忆库 PostgreSQL（LangGraph 长期/短期，同步）=====
    DB_URI: str = "postgresql+psycopg2://legal:legal@postgres:5432/legal_memory"

    # ===== 缓存 / 会话 / 限流 Redis =====
    REDIS_URL: str = "redis://redis:6379/0"

    # ===== 向量库 Milvus =====
    MILVUS_URI: str = "http://milvus:19530"
    MILVUS_COLLECTION: str = "legal_knowledge"
    MILVUS_DIM: int = 1024

    # ===== 图数据库 Neo4j =====
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "legal123456"

    # ===== 认证 JWT =====
    JWT_SECRET: str = "change-me-to-a-long-random-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # ===== 初始管理员（首次启动时自动创建，可通过环境变量覆盖）=====
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@legal.local"
    ADMIN_PASSWORD: str = "admin123456"

    # ===== CORS =====
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080"

    # ===== 可观测性 =====
    LOG_LEVEL: str = "INFO"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://jaeger:4317"
    OTEL_ENABLED: bool = True

    # ===== 限流 =====
    RATE_LIMIT_PER_MINUTE: int = 60

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()