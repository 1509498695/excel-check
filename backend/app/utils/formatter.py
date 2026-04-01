"""接口响应格式化工具。"""

from typing import Any


def build_execution_response(
    abnormal_results: list[dict[str, Any]] | None,
    execution_time_ms: int = 0,
    total_rows_scanned: int = 0,
    failed_sources: list[str] | None = None,
    msg: str = "Execution Completed",
) -> dict[str, Any]:
    """构建执行接口统一返回的响应结构。"""
    return {
        "code": 200,
        "msg": msg,
        "meta": {
            "execution_time_ms": execution_time_ms,
            "total_rows_scanned": total_rows_scanned,
            "failed_sources": failed_sources or [],
        },
        "data": {
            "abnormal_results": abnormal_results or [],
        },
    }
