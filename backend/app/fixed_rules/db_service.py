"""固定规则配置的数据库读写服务（按 project_id 隔离）。"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import FixedRulesConfigRecord


async def load_fixed_rules_config_from_db(
    db: AsyncSession,
    project_id: int,
) -> dict | None:
    """从数据库加载指定项目的固定规则配置 JSON。"""
    result = await db.execute(
        select(FixedRulesConfigRecord).where(
            FixedRulesConfigRecord.project_id == project_id
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        return None
    return json.loads(record.config_json)


async def save_fixed_rules_config_to_db(
    db: AsyncSession,
    project_id: int,
    config_dict: dict,
) -> None:
    """将固定规则配置 JSON 写入数据库。"""
    result = await db.execute(
        select(FixedRulesConfigRecord).where(
            FixedRulesConfigRecord.project_id == project_id
        )
    )
    record = result.scalar_one_or_none()
    config_str = json.dumps(config_dict, ensure_ascii=False)

    if record:
        record.config_json = config_str
    else:
        record = FixedRulesConfigRecord(
            project_id=project_id,
            config_json=config_str,
        )
    db.add(record)
    await db.commit()
