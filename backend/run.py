"""FastAPI 服务启动入口。"""

from contextlib import asynccontextmanager
from pathlib import Path
import sys
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.api.router import api_router
from backend.app.database import init_db
from backend.config import settings


@asynccontextmanager
async def lifespan(application: FastAPI):
    """应用生命周期：启动时初始化数据库表。"""
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    yield


def create_app() -> FastAPI:
    """创建并装配 FastAPI 应用实例。"""
    application = FastAPI(title=settings.app_name, lifespan=lifespan)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()


@app.get("/health", tags=["system"])
def health_check() -> dict[str, Any]:
    """返回服务健康状态，供部署探针与联调环境快速检查。"""
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "status": "healthy",
            "service": settings.app_name,
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
