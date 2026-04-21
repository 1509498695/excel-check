"""接口响应格式化工具。"""

from typing import Any


def build_execution_response(
    abnormal_results: list[dict[str, Any]] | None,
    execution_time_ms: int = 0,
    total_rows_scanned: int = 0,
    failed_sources: list[str] | None = None,
    msg: str = "Execution Completed",
    *,
    result_id: int | None = None,
    page: int | None = None,
    size: int | None = None,
    total: int | None = None,
    result_list: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """构建执行接口统一返回的响应结构。"""
    if (
        result_id is None
        and page is None
        and size is None
        and total is None
        and result_list is None
    ):
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

    current_page = page or 1
    current_size = size or len(result_list or abnormal_results or []) or 0
    current_list = result_list if result_list is not None else (abnormal_results or [])
    total_results = total if total is not None else len(abnormal_results or [])
    meta: dict[str, Any] = {
        "execution_time_ms": execution_time_ms,
        "total_rows_scanned": total_rows_scanned,
        "failed_sources": failed_sources or [],
    }
    if result_id is not None:
        meta["result_id"] = result_id

    return {
        "code": 200,
        "msg": msg,
        "meta": meta,
        "data": {
            "abnormal_results": current_list,
            "total": total_results,
            "list": current_list,
            "page": current_page,
            "size": current_size,
        },
    }
