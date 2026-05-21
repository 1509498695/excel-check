"""固定规则数据源运行时绑定校验。"""

from __future__ import annotations

from pathlib import Path

from backend.app.api.fixed_rules_schemas import FixedRulesConfigIssue
from backend.app.api.schemas import DataSource
from backend.app.fixed_rules.config_common import _append_config_issue
from backend.app.loaders.local_reader import read_source_metadata


def _validate_source_runtime_bindings(
    sources: list[DataSource],
    *,
    metadata_cache: dict[str, dict[str, object]],
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
) -> None:
    """把数据源级别的运行时校验前置，确保空变量池场景也能捕获失效路径。"""
    for source in sources:
        if source.type == "local_csv":
            message = f"CSV 数据源“{source.id}”已不再支持，请删除后改用 Excel 或 SVN Excel。"
            if config_issues is None:
                raise ValueError(message)
            _append_config_issue(
                config_issues,
                issue_keys,
                source_id=source.id,
                message=message,
            )
            metadata_cache[source.id] = {"sheets": [], "__unsupported_csv__": True}
            continue

        if source.type != "local_excel":
            continue

        raw_locator = (source.pathOrUrl or source.path or "").strip()
        if not raw_locator:
            continue

        source_path = Path(raw_locator).expanduser().resolve(strict=False)
        if not source_path.exists():
            message = (
                f"数据源“{source.id}”的本地路径已失效：{source_path}。"
                "请到“数据源接入管理”中修复路径后再保存或执行。"
            )
            if config_issues is None:
                raise ValueError(message)
            _append_config_issue(
                config_issues,
                issue_keys,
                source_id=source.id,
                message=message,
            )
            metadata_cache[source.id] = {"sheets": [], "__missing__": True}
            continue

        if source.type == "local_excel" and source.id not in metadata_cache:
            try:
                metadata_cache[source.id] = read_source_metadata(source)
            except FileNotFoundError:
                message = (
                    f"数据源“{source.id}”的本地路径已失效：{source_path}。"
                    "请到“数据源接入管理”中修复路径后再保存或执行。"
                )
                if config_issues is None:
                    raise ValueError(message)
                _append_config_issue(
                    config_issues,
                    issue_keys,
                    source_id=source.id,
                    message=message,
                )
                metadata_cache[source.id] = {"sheets": [], "__missing__": True}
