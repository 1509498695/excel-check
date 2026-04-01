"""FastAPI 服务启动入口。"""

from pathlib import Path
import sys
from typing import Any

import uvicorn
from fastapi import FastAPI


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.api.router import api_router
from backend.config import settings


def create_app() -> FastAPI:
    """创建并装配 FastAPI 应用实例。"""
    application = FastAPI(title=settings.app_name)
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
