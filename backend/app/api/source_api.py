"""数据源能力查询接口。"""

from typing import Any

from fastapi import APIRouter

from backend.config import settings


router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/capabilities")
def get_source_capabilities() -> dict[str, Any]:
    """返回当前后端已声明的数据源能力清单。"""
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "source_types": list(settings.supported_source_types),
            "implemented": False,
        },
    }
