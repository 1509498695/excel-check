"""应用配置定义。"""

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """集中管理服务名、监听地址、数据库、JWT 和运行参数。"""

    app_name: str = "excel-check-backend"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    api_v1_prefix: str = "/api/v1"
    default_thread_pool_size: int = 4
    backend_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    runtime_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent / ".runtime"
    )
    fixed_rules_config_path: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent
        / ".runtime"
        / "fixed-rules"
        / "default.json"
    )
    svn_executable: str = field(
        default_factory=lambda: (os.getenv("SVN_EXECUTABLE") or "svn").strip()
        or "svn"
    )
    supported_source_types: tuple[str, ...] = field(
        default_factory=lambda: ("local_excel", "local_csv", "feishu", "svn")
    )
    svn_cache_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent
        / ".runtime"
        / "svn-cache"
    )
    svn_credentials_path: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent
        / ".runtime"
        / "svn-credentials.json"
    )
    svn_credentials_key_path: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent
        / ".runtime"
        / ".svn-key"
    )
    svn_cache_ttl_seconds: int = 60
    svn_url_allowlist: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            host.strip()
            for host in (os.getenv("SVN_URL_ALLOWLIST") or "samosvn").split(",")
            if host.strip()
        )
        or ("samosvn",)
    )
    svn_list_timeout_seconds: int = 30
    svn_subprocess_timeout_seconds: int = 600

    # --- 数据库 ---
    db_url: str = field(
        default_factory=lambda: os.getenv("DB_URL") or "sqlite+aiosqlite:///"
        + str(
            Path(__file__).resolve().parent / ".runtime" / "excel_check.db"
        )
    )

    # --- JWT ---
    jwt_secret_key: str = field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY")
        or secrets.token_urlsafe(32)
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 小时

    # --- 超级管理员 ---
    default_super_admin_username: str = "admin"
    default_super_admin_password: str = "123456"


settings = Settings()
