"""AI provider credential loading helpers."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import AiProviderCredentialRecord
from backend.app.security.crypto import decrypt_secret


class AiProviderNotConfigured(ValueError):
    """当前用户尚未配置 AI 供应商。"""


class AiProviderInvalid(ValueError):
    """当前用户的 AI 凭据无法解密。"""


async def load_user_credential(
    db: AsyncSession,
    user_id: int,
) -> AiProviderCredentialRecord:
    """Load the current user's AI credential record."""
    result = await db.execute(
        select(AiProviderCredentialRecord).where(AiProviderCredentialRecord.user_id == user_id)
    )
    credential = result.scalar_one_or_none()
    if credential is None:
        raise AiProviderNotConfigured("请先在个人设置中配置 AI 模型。")
    return credential


def decrypt_credential_key(credential: AiProviderCredentialRecord) -> str:
    """Decrypt a provider API key and normalize the domain error."""
    try:
        return decrypt_secret(credential.encrypted_api_key)
    except ValueError as exc:
        raise AiProviderInvalid("AI 凭据已损坏，请重新填写 API Key。") from exc


def parse_extra_headers(raw_json: str) -> dict[str, str]:
    """Parse persisted provider extra headers."""
    try:
        parsed = json.loads(raw_json or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}
