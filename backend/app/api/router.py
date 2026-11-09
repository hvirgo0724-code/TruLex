"""API 路由聚合（前缀 /api/v1）。"""

from fastapi import APIRouter

from app.api import admin, auth, chat, contract, document, knowledge

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(contract.router)
api_router.include_router(knowledge.router)
api_router.include_router(document.router)
api_router.include_router(admin.router)