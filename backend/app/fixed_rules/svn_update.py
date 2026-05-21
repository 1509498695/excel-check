"""固定规则 SVN 更新。"""

from __future__ import annotations

from pathlib import Path

from backend.app.api.fixed_rules_schemas import FixedRulesConfig
from backend.app.api.schemas import DataSource
from backend.app.fixed_rules.config_loader import load_fixed_rules_config
from backend.app.loaders.svn_manager import update_svn_working_copy


def run_saved_fixed_rules_svn_update(
    config: FixedRulesConfig | None = None,
    *,
    user_scope: str | None = None,
    update_working_copy=update_svn_working_copy,
) -> dict[str, object]:
    """对固定规则配置中的数据源执行 SVN 更新。

    本地工作副本走 svn update；远端 URL 走 prepare_remote_svn_source 强制刷新缓存目录。
    `user_scope` 用于查询当前登录用户在某 host 上保存的凭据；未提供时退化到全局缓存。
    """
    from backend.app.loaders.svn_cache import (
        get_remote_cache_state,
        prepare_remote_svn_source,
    )

    if config is None:
        config = load_fixed_rules_config()
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
