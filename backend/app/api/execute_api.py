"""执行入口接口。"""

from __future__ import annotations

import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException

from backend.app.api.schemas import DataSource, TaskTree, ValidationRule, VariableTag
from backend.app.loaders.feishu_reader import read_feishu_sheet
from backend.app.loaders.local_reader import load_variables_by_source
from backend.app.loaders.svn_manager import sync_svn_source
from backend.app.rules.engine_core import RULE_REGISTRY, execute_rules
from backend.app.utils.formatter import build_execution_response
from backend.config import settings


router = APIRouter(prefix="/engine", tags=["engine"])


@router.post("/execute")
def execute_engine(task_tree: TaskTree) -> dict[str, Any]:
    """按 TaskTree 串起加载、规则执行与响应组装流程。"""
    start = time.perf_counter()

    try:
        execution_artifacts = _run_execution_pipeline(task_tree)
    except (ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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


def _run_execution_pipeline(task_tree: TaskTree) -> dict[str, Any]:
    """执行完整主干流程，并返回规则执行所需的中间结果。"""
    source_map = _build_source_map(task_tree.sources)
    grouped_variables = _group_variables_by_source(task_tree.variables, source_map)
    load_result = _load_sources_concurrently(source_map, grouped_variables)
    executable_rules = _filter_executable_rules(
        _filter_rules_by_selected_ids(task_tree.rules, task_tree.selected_rule_ids),
        grouped_variables=grouped_variables,
        loaded_variables=load_result["loaded_variables"],
        failed_sources=set(load_result["failed_sources"]),
    )

    executable_task_tree = task_tree.model_copy(update={"rules": executable_rules})
    abnormal_results = execute_rules(
        executable_task_tree,
        load_result["loaded_variables"],
    )

    return {
        "loaded_variables": load_result["loaded_variables"],
        "failed_sources": load_result["failed_sources"],
        "abnormal_results": abnormal_results,
    }


def _filter_rules_by_selected_ids(
    rules: list[ValidationRule],
    selected_rule_ids: list[str] | None,
) -> list[ValidationRule]:
    """按传入的 rule_id 子集过滤本次需要执行的规则。"""
    if selected_rule_ids is None:
        return rules

    selected_rule_id_set = {
        rule_id.strip() for rule_id in selected_rule_ids if isinstance(rule_id, str) and rule_id.strip()
    }
    if not selected_rule_id_set:
        return []

    return [
        rule
        for rule in rules
        if isinstance(rule.rule_id, str) and rule.rule_id.strip() in selected_rule_id_set
    ]


def _build_source_map(sources: list[DataSource]) -> dict[str, DataSource]:
    """构建 source_id 到数据源配置的映射，并校验唯一性。"""
    source_map: dict[str, DataSource] = {}

    for source in sources:
        if source.id in source_map:
            raise ValueError(f"Duplicate source id is not allowed: '{source.id}'.")
        source_map[source.id] = source

    return source_map


def _group_variables_by_source(
    variables: list[VariableTag], source_map: dict[str, DataSource]
) -> dict[str, list[VariableTag]]:
    """按 source_id 聚合变量，并校验引用关系与 tag 唯一性。"""
    grouped_variables: dict[str, list[VariableTag]] = defaultdict(list)
    seen_tags: set[str] = set()

    for variable in variables:
        if variable.tag in seen_tags:
            raise ValueError(
                f"Duplicate variable tags are not allowed: '{variable.tag}'."
            )
        seen_tags.add(variable.tag)

        if variable.source_id not in source_map:
            raise ValueError(
                f"Variable tag '{variable.tag}' references unknown source_id "
                f"'{variable.source_id}'."
            )
        grouped_variables[variable.source_id].append(variable)

    return grouped_variables


def _load_sources_concurrently(
    source_map: dict[str, DataSource],
    grouped_variables: dict[str, list[VariableTag]],
) -> dict[str, Any]:
    """并发加载所有 source，并将失败 source 降级记录到 failed_sources。"""
    loaded_variables: dict[str, pd.DataFrame] = {}
    failed_sources: list[str] = []

    source_ids = [source_id for source_id in source_map if grouped_variables.get(source_id)]
    if not source_ids:
        return {"loaded_variables": {}, "failed_sources": []}

    with ThreadPoolExecutor(
        max_workers=settings.default_thread_pool_size
    ) as executor:
        future_map = {
            executor.submit(
                _load_single_source,
                source_map[source_id],
                grouped_variables[source_id],
            ): source_id
            for source_id in source_ids
        }

        for future in as_completed(future_map):
            source_id = future_map[future]
            try:
                source_frames = future.result()
            except ImportError as exc:
                raise ValueError(str(exc)) from exc
            except (FileNotFoundError, ValueError, NotImplementedError):
                failed_sources.append(source_id)
                continue

            overlap_tags = set(loaded_variables).intersection(source_frames)
            if overlap_tags:
                raise ValueError(
                    f"Duplicate variable tags produced while loading sources: "
                    f"{sorted(overlap_tags)}."
                )
            loaded_variables.update(source_frames)

    return {
        "loaded_variables": loaded_variables,
        "failed_sources": failed_sources,
    }


def _load_single_source(
    source: DataSource, variables_for_source: list[VariableTag]
) -> dict[str, pd.DataFrame]:
    """根据 source.type 选择对应 loader。"""
    if source.type in {"local_excel", "local_csv"}:
        return load_variables_by_source(source, variables_for_source)

    if source.type == "feishu":
        read_feishu_sheet(source=source, variables_for_source=variables_for_source)
        return {}

    if source.type == "svn":
        sync_svn_source(source=source)
        return load_variables_by_source(source, variables_for_source)

    raise ValueError(f"Unsupported source type: '{source.type}'.")


def _filter_executable_rules(
    rules: list[ValidationRule],
    *,
    grouped_variables: dict[str, list[VariableTag]],
    loaded_variables: dict[str, pd.DataFrame],
    failed_sources: set[str],
) -> list[ValidationRule]:
    """过滤依赖失败 source 的规则，保留可执行规则。"""
    tag_to_source_id = {
        variable.tag: source_id
        for source_id, variables in grouped_variables.items()
        for variable in variables
    }

    executable_rules: list[ValidationRule] = []
    for rule in rules:
        _ensure_rule_supported(rule)
        dependent_tags = _extract_rule_tags(rule)

        missing_tags = [tag for tag in dependent_tags if tag not in tag_to_source_id]
        if missing_tags:
            raise ValueError(
                f"Rule '{rule.rule_type}' references unknown tag(s): {missing_tags}."
            )

        # 只要规则依赖的任一 tag 来自失败 source，就跳过该规则。
        if any(tag_to_source_id[tag] in failed_sources for tag in dependent_tags):
            continue

        # 走到这里说明依赖 source 已成功，但 tag 仍缺失，属于结构性错误。
        unresolved_tags = [tag for tag in dependent_tags if tag not in loaded_variables]
        if unresolved_tags:
            raise ValueError(
                f"Rule '{rule.rule_type}' depends on unloaded tag(s): {unresolved_tags}."
            )

        executable_rules.append(rule)

    return executable_rules


def _ensure_rule_supported(rule: ValidationRule) -> None:
    """校验 rule_type 已注册。"""
    if rule.rule_type not in RULE_REGISTRY:
        raise ValueError(f"Unsupported rule_type: '{rule.rule_type}'.")


def _extract_rule_tags(rule: ValidationRule) -> list[str]:
    """从规则参数中提取其依赖的变量标签。

    直接复用注册表里登记好的 ``dependent_tags`` 提取器，避免在本文件维护
    和 ``rule_*`` 模块内 handler 真实依赖之间漂移的 if/elif 长链。
    """
    return RULE_REGISTRY[rule.rule_type].dependent_tags(rule)
