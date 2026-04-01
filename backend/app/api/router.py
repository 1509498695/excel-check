"""API 路由聚合入口。"""

from fastapi import APIRouter

from backend.app.api.execute_api import router as execute_router
from backend.app.api.source_api import router as source_router


api_router = APIRouter()
api_router.include_router(source_router)
api_router.include_router(execute_router)
