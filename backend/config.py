"""应用配置定义。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """集中管理服务名、监听地址和运行参数。"""

    app_name: str = "excel-check-backend"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    api_v1_prefix: str = "/api/v1"
    default_thread_pool_size: int = 4
    supported_source_types: tuple[str, ...] = field(
        default_factory=lambda: ("local_excel", "local_csv", "feishu", "svn")
    )


settings = Settings()
