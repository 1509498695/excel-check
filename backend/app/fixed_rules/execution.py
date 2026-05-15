"""Fixed-rules execution, result persistence, and SVN update helpers."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.fixed_rules_schemas import FixedRulesConfig
from backend.app.api.schemas import DataSource
from backend.app.execution_pipeline import run_execution_pipeline
from backend.app.fixed_rules.config_migration import _parse_fixed_rules_payload
from backend.app.fixed_rules.config_validation import validate_and_normalize_fixed_rules_config
from backend.app.fixed_rules.db_service import load_fixed_rules_config_from_db
from backend.app.fixed_rules.task_tree import _get_ordered_rules, build_fixed_rules_task_tree
from backend.app.loaders.svn_manager import update_svn_working_copy
from backend.app.models import Project
from backend.app.result_store import persist_execution_result
from backend.app.utils.formatter import build_execution_response

def execute_saved_fixed_rules(
    config: FixedRulesConfig,
    selected_rule_ids: list[str] | None = None,
) -> dict[str, object]:
    """执行固定规则。如果传入 config 则直接使用，否则从文件加载。"""
    ordered_rules = _get_ordered_rules(config, selected_rule_ids=selected_rule_ids)
    if not ordered_rules:
        raise ValueError("当前没有可执行的固定规则，请先配置规则再执行。")
    task_tree = build_fixed_rules_task_tree(config, selected_rule_ids=selected_rule_ids)
    start = time.perf_counter()
    execution_artifacts = run_execution_pipeline(task_tree)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    total_rows_scanned = sum(
        len(frame) for frame in execution_artifacts["loaded_variables"].values()
    )
    return build_execution_response(
        abnormal_results=execution_artifacts["abnormal_results"],
        execution_time_ms=elapsed_ms,
        total_rows_scanned=total_rows_scanned,
        failed_sources=execution_artifacts["failed_sources"],
        msg="Execution Completed",
    )


async def execute_fixed_rules_for_project(
    db: AsyncSession,
    project_id: int,
    *,
    user_scope: str | None = None,
    selected_rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    """以项目级配置执行项目校验，落库后返回执行摘要。

    供 ``/fixed-rules/execute`` 与飞书机器人事件入口共用，确保两者执行链路、
    持久化、协议字段完全一致。

    - 配置读取失败或不存在 → 抛 ``ValueError("当前项目尚未配置固定规则")``。
    - 其余 ``FileNotFoundError`` / ``ValueError`` / ``ImportError`` /
      ``NotImplementedError`` 由调用层翻译为 4xx；本函数不吞这些异常。
    - ``user_scope`` 预留 SVN 凭据维度（与 ``run_saved_fixed_rules_svn_update``
      保持一致），当前 ``run_execution_pipeline`` 还未消费该字段，本期保持透传。
    """
    raw = await load_fixed_rules_config_from_db(db, project_id)
    if raw is None:
        raise ValueError("当前项目尚未配置固定规则")

    parsed = _parse_fixed_rules_payload(raw)
    config = validate_and_normalize_fixed_rules_config(parsed)
    task_tree = build_fixed_rules_task_tree(
        config,
        selected_rule_ids=selected_rule_ids,
    )

    start = time.perf_counter()
    execution_artifacts = run_execution_pipeline(task_tree)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    abnormal_results = execution_artifacts["abnormal_results"]
    total_rows_scanned = sum(
        len(frame) for frame in execution_artifacts["loaded_variables"].values()
    )
    failed_sources = execution_artifacts["failed_sources"]

    result_id = await persist_execution_result(
        db,
        scope_type="fixed_rules",
        project_id=project_id,
        user_id=None,
        abnormal_results=abnormal_results,
        execution_time_ms=elapsed_ms,
        total_rows_scanned=total_rows_scanned,
        failed_sources=failed_sources,
    )

    project = await db.get(Project, project_id)
    project_name = project.name if project is not None else f"项目 {project_id}"

    return {
        "result_id": result_id,
        "total_rows_scanned": total_rows_scanned,
        "failed_sources": failed_sources,
        "abnormal_results": abnormal_results,
        "execution_time_ms": elapsed_ms,
        "project_name": project_name,
    }


def run_saved_fixed_rules_svn_update(
    config: FixedRulesConfig,
    *,
    user_scope: str | None = None,
    update_working_copy: Callable[[Path], dict[str, Any]] = update_svn_working_copy,
) -> dict[str, object]:
    """对固定规则配置中的数据源执行 SVN 更新。

    本地工作副本走 svn update；远端 URL 走 prepare_remote_svn_source 强制刷新缓存目录。
    `user_scope` 用于查询当前登录用户在某 host 上保存的凭据；未提供时退化到全局缓存。
    """
    from backend.app.loaders.svn_cache import (
        get_remote_cache_state,
        prepare_remote_svn_source,
    )

    targets = _collect_svn_targets(config.sources)
    if not targets:
        raise ValueError("当前配置里没有可触发 SVN 更新的目录或远端 URL。")

    results: list[dict[str, object]] = []
    updated_paths = 0

    for target in targets:
        if target["kind"] == "working_copy":
            working_copy: Path = target["path"]  # type: ignore[assignment]
            try:
                update_result = update_working_copy(working_copy)
            except NotImplementedError:
                raise
            except (FileNotFoundError, ValueError) as exc:
                results.append(
                    {
                        "kind": "working_copy",
                        "working_copy": str(working_copy),
                        "source_id": target["source_id"],
                        "source_url": "",
                        "status": "error",
                        "output": "",
                        "used_executable": "",
                        "error": str(exc),
                    }
                )
                continue
            updated_paths += 1
            results.append(
                {
                    "kind": "working_copy",
                    "working_copy": str(working_copy),
                    "source_id": target["source_id"],
                    "source_url": "",
                    "status": "success",
                    "output": update_result["output"],
                    "used_executable": update_result["used_executable"],
                }
            )
            continue

        # remote_cache 分支
        cache_dir: Path = target["path"]  # type: ignore[assignment]
        source_obj: DataSource = target["source_obj"]  # type: ignore[assignment]
        source_url: str = target["source_url"]  # type: ignore[assignment]
        try:
            prepare_remote_svn_source(
                source_obj,
                user_scope=user_scope,
                force_refresh=True,
            )
        except NotImplementedError:
            raise
        except (FileNotFoundError, ValueError) as exc:
            results.append(
                {
                    "kind": "remote_cache",
                    "working_copy": str(cache_dir),
                    "source_id": target["source_id"],
                    "source_url": source_url,
                    "status": "error",
                    "output": "",
                    "used_executable": "",
                    "error": str(exc),
                }
            )
            continue

        state = get_remote_cache_state(source_url)
        revision = state.get("revision")
        updated_paths += 1
        results.append(
            {
                "kind": "remote_cache",
                "working_copy": str(cache_dir),
                "source_id": target["source_id"],
                "source_url": source_url,
                "status": "success",
                "output": f"已刷新缓存到 r{revision}" if revision else "已刷新缓存",
                "used_executable": "",
            }
        )

    return {
        "total_paths": len(targets),
        "updated_paths": updated_paths,
        "results": results,
    }


def _collect_svn_targets(sources: list[DataSource]) -> list[dict[str, object]]:
    """收集需要触发 SVN 更新的目标，按 (kind, target_key) 去重。

    返回结构：
        - {kind: "working_copy", path: Path, source_id, source_url=""}
        - {kind: "remote_cache", path: Path | None,  # path 可能为 None，由 prepare 时再算
           source_obj: DataSource, source_id, source_url}
    """
    from backend.app.loaders.svn_cache import (
        derive_cache_paths,
        is_remote_svn_locator,
    )

    targets: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str]] = set()

    for source in sources:
        raw_locator = (source.path or source.pathOrUrl or source.url or "").strip()
        if not raw_locator or source.type == "feishu":
            continue

        if source.type == "svn" and is_remote_svn_locator(raw_locator):
            try:
                cache_dir, _file_name, _host = derive_cache_paths(raw_locator)
            except ValueError:
                # host 不在白名单等场景：跳过，不阻塞其他数据源
                continue
            key = ("remote_cache", str(cache_dir).lower())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            targets.append(
                {
                    "kind": "remote_cache",
                    "path": cache_dir,
                    "source_obj": source,
                    "source_id": source.id,
                    "source_url": raw_locator,
                }
            )
            continue

        source_path = Path(raw_locator).expanduser().resolve(strict=False)
        working_copy = source_path if source.type == "svn" else source_path.parent
        key = ("working_copy", str(working_copy).lower())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        targets.append(
            {
                "kind": "working_copy",
                "path": working_copy,
                "source_obj": source,
                "source_id": source.id,
                "source_url": "",
            }
        )

    return targets


def _collect_working_copies(sources: list[DataSource]) -> list[Path]:
    """兼容旧调用名，仅返回本地 working_copy 路径列表。"""
    return [
        target["path"]
        for target in _collect_svn_targets(sources)
        if target["kind"] == "working_copy"
    ]
